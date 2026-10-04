"""Frozen-output evaluator benchmarks backed by OpenRouter.

The module deliberately keeps benchmark configuration independent from runtime
environment defaults. A benchmark names each evaluator model and routing policy
explicitly, while credentials stay in ``OPENROUTER_API_KEY``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Iterable, Mapping, TypeVar

import requests

from .benchmark_trace_export import benchmark_score_values, build_benchmark_trace_overlay
from .frozen_samples import (
    FrozenFablesSample,
    FrozenGEvalSample,
    FrozenStructuredJudgeSample,
    extract_fables_samples,
    extract_geval_samples,
    extract_structured_judge_samples,
    load_fables_samples,
    load_geval_samples,
    load_structured_judge_samples,
    split_ragas_score_groups,
)


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_PROVIDER_PREFERENCE_KEYS = frozenset(
    {
        "order",
        "allow_fallbacks",
        "require_parameters",
        "data_collection",
        "zdr",
        "enforce_distillable_text",
        "only",
        "ignore",
        "quantizations",
        "sort",
        "preferred_min_throughput",
        "preferred_max_latency",
        "max_price",
    }
)
_BENCHMARK_SCORE_NAMES = frozenset(
    {
        "geval_coherence_normalized",
        "fables_faithfulness",
        "ragas_standard_faithfulness",
        "ragas_answer_relevancy",
        "ragas_context_relevance",
    }
)
_Result = TypeVar("_Result")


@dataclass(frozen=True)
class OpenRouterModelInfo:
    """The catalogue fields needed to make a benchmark eligibility decision."""

    model_id: str
    supported_parameters: frozenset[str]
    pricing: Mapping[str, Any]
    name: str = ""
    context_length: int | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "OpenRouterModelInfo":
        model_id = str(payload.get("id") or "").strip()
        if not model_id:
            raise ValueError("OpenRouter model payload does not contain an id")
        raw_parameters = payload.get("supported_parameters") or []
        if not isinstance(raw_parameters, list):
            raw_parameters = []
        pricing = payload.get("pricing") or {}
        if not isinstance(pricing, Mapping):
            pricing = {}
        raw_context = payload.get("context_length")
        context_length = int(raw_context) if isinstance(raw_context, (int, float)) else None
        return cls(
            model_id=model_id,
            supported_parameters=frozenset(str(item) for item in raw_parameters),
            pricing=dict(pricing),
            name=str(payload.get("name") or ""),
            context_length=context_length,
        )

    @property
    def is_free(self) -> bool:
        """True only when all billable request, prompt, and completion fields are zero."""
        billable_keys = ("prompt", "completion", "request", "image", "web_search")
        observed = [self.pricing[key] for key in billable_keys if key in self.pricing]
        if not observed:
            return False
        try:
            return all(float(value) == 0.0 for value in observed)
        except (TypeError, ValueError):
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.model_id,
            "name": self.name,
            "supported_parameters": sorted(self.supported_parameters),
            "pricing": dict(self.pricing),
            "context_length": self.context_length,
        }


def validate_model_for_run(
    model: OpenRouterModelInfo,
    required_parameters: set[str] | frozenset[str],
    require_free: bool,
) -> list[str]:
    """Return every deterministic reason a model cannot start this benchmark."""
    errors: list[str] = []
    if model.model_id == "openrouter/free":
        errors.append("openrouter/free is non-deterministic and cannot be benchmarked")
    if require_free and not model.is_free:
        errors.append(f"model {model.model_id!r} is not free according to OpenRouter pricing")
    missing = sorted(set(required_parameters) - set(model.supported_parameters))
    if missing:
        errors.append(
            f"model {model.model_id!r} is missing required supported_parameters: {', '.join(missing)}"
        )
    return errors


@dataclass(frozen=True)
class EvaluatorTarget:
    """One explicit LLM-as-a-judge target in a benchmark configuration."""

    identifier: str
    model: str
    temperature: float
    require_free: bool
    required_parameters: frozenset[str]
    provider_preferences: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvaluatorTarget":
        identifier = str(value.get("id") or "").strip()
        model = str(value.get("model") or "").strip()
        if not identifier or not model:
            raise ValueError("each evaluator requires non-empty id and model")
        if model == "openrouter/free":
            raise ValueError("openrouter/free cannot be used in a reproducible benchmark")
        preferences = value.get("provider_preferences") or {}
        if not isinstance(preferences, Mapping):
            raise ValueError(f"evaluator {identifier!r} provider_preferences must be an object")
        unknown = sorted(set(preferences) - _PROVIDER_PREFERENCE_KEYS)
        if unknown:
            raise ValueError(
                f"evaluator {identifier!r} has unsupported OpenRouter provider_preferences: "
                f"{', '.join(unknown)}"
            )
        raw_required = value.get("required_parameters") or []
        if not isinstance(raw_required, list) or not all(isinstance(x, str) for x in raw_required):
            raise ValueError(f"evaluator {identifier!r} required_parameters must be a string list")
        temperature = float(value.get("temperature", 0.0))
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(f"evaluator {identifier!r} temperature must be in [0, 2]")
        return cls(
            identifier=identifier,
            model=model,
            temperature=temperature,
            require_free=bool(value.get("require_free", False)),
            required_parameters=frozenset(raw_required),
            provider_preferences=dict(preferences),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["required_parameters"] = sorted(self.required_parameters)
        result["provider_preferences"] = dict(self.provider_preferences)
        return result


@dataclass(frozen=True)
class RagasEmbeddingTarget:
    """Explicit embedding endpoint used by the RAGAS Answer Relevancy metric."""

    model: str
    require_free: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RagasEmbeddingTarget":
        model = str(value.get("embedding_model") or "").strip()
        if not model:
            raise ValueError("ragas.embedding_model is required when metric 'ragas' is selected")
        if model == "openrouter/free":
            raise ValueError("ragas.embedding_model cannot be openrouter/free")
        return cls(model=model, require_free=bool(value.get("require_free", False)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkExecutionConfig:
    """Concurrency controls for independent evaluator targets."""

    parallel: bool = True
    max_concurrency: int = 3

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BenchmarkExecutionConfig":
        parallel = value.get("parallel", True)
        max_concurrency = value.get("max_concurrency", 3)
        if not isinstance(parallel, bool):
            raise ValueError("execution.parallel must be a boolean")
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool) or max_concurrency < 1:
            raise ValueError("execution.max_concurrency must be a positive integer")
        return cls(parallel=parallel, max_concurrency=max_concurrency)


@dataclass(frozen=True)
class LangfuseBenchmarkConfig:
    """Optional trace and score reporting for external benchmark runs."""

    enabled: bool = False
    mode: str = "local_export"
    session_id_template: str = "benchmark:{source_trace_id}"
    trace_name_prefix: str = "BenchmarkEvaluation"
    score_config_ids: Mapping[str, str] | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LangfuseBenchmarkConfig":
        enabled = value.get("enabled", False)
        mode = value.get("mode", "local_export")
        session_id_template = value.get("session_id_template", "benchmark:{source_trace_id}")
        trace_name_prefix = value.get("trace_name_prefix", "BenchmarkEvaluation")
        score_config_ids = value.get("score_config_ids") or {}
        if not isinstance(enabled, bool):
            raise ValueError("langfuse.enabled must be a boolean")
        if mode not in {"local_export", "source_trace", "separate_trace"}:
            raise ValueError("langfuse.mode must be local_export, source_trace, or separate_trace")
        if mode != "local_export" and not enabled:
            raise ValueError("langfuse.enabled must be true when langfuse.mode writes to Langfuse")
        if not isinstance(session_id_template, str) or "{source_trace_id}" not in session_id_template:
            raise ValueError("langfuse.session_id_template must include {source_trace_id}")
        if not isinstance(trace_name_prefix, str) or not trace_name_prefix.strip():
            raise ValueError("langfuse.trace_name_prefix must be a non-empty string")
        if not isinstance(score_config_ids, Mapping) or not all(
            isinstance(name, str) and isinstance(config_id, str) and config_id.strip()
            for name, config_id in score_config_ids.items()
        ):
            raise ValueError("langfuse.score_config_ids must map score names to non-empty ids")
        unknown = sorted(set(score_config_ids) - _BENCHMARK_SCORE_NAMES)
        if unknown:
            raise ValueError("langfuse.score_config_ids contains unsupported score names: " + ", ".join(unknown))
        return cls(
            enabled=enabled,
            mode=mode,
            session_id_template=session_id_template,
            trace_name_prefix=trace_name_prefix.strip(),
            score_config_ids=dict(score_config_ids),
        )


@dataclass(frozen=True)
class BenchmarkConfig:
    """Validated benchmark file contents."""

    evaluators: tuple[EvaluatorTarget, ...]
    metrics: tuple[str, ...]
    ragas_embedding: RagasEmbeddingTarget | None
    execution: BenchmarkExecutionConfig
    langfuse: LangfuseBenchmarkConfig
    source: Mapping[str, Any]
    raw_digest: str

    @classmethod
    def from_json(cls, path: Path) -> "BenchmarkConfig":
        raw = path.read_bytes()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid benchmark JSON at {path}: {exc}") from exc
        if not isinstance(value, Mapping):
            raise ValueError("benchmark config root must be an object")
        evaluators_value = value.get("evaluators")
        if not isinstance(evaluators_value, list) or not evaluators_value:
            raise ValueError("benchmark config requires a non-empty evaluators list")
        evaluators = tuple(EvaluatorTarget.from_mapping(item) for item in evaluators_value)
        ids = [item.identifier for item in evaluators]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluator ids must be unique")
        metrics_value = value.get("metrics", ["fables"])
        if not isinstance(metrics_value, list) or not all(isinstance(item, str) for item in metrics_value):
            raise ValueError("metrics must be a string list")
        unsupported_metrics = set(metrics_value) - {"geval", "fables", "ragas"}
        if unsupported_metrics:
            raise ValueError(
                "currently supported frozen metrics: geval, fables, ragas; unsupported: "
                + ", ".join(sorted(unsupported_metrics))
            )
        ragas_value = value.get("ragas") or {}
        if not isinstance(ragas_value, Mapping):
            raise ValueError("ragas must be an object")
        ragas_embedding = (
            RagasEmbeddingTarget.from_mapping(ragas_value) if "ragas" in metrics_value else None
        )
        execution_value = value.get("execution") or {}
        if not isinstance(execution_value, Mapping):
            raise ValueError("execution must be an object")
        langfuse_value = value.get("langfuse") or {}
        if not isinstance(langfuse_value, Mapping):
            raise ValueError("langfuse must be an object")
        source = value.get("source") or {}
        if not isinstance(source, Mapping):
            raise ValueError("source must be an object")
        return cls(
            evaluators=evaluators,
            metrics=tuple(metrics_value),
            ragas_embedding=ragas_embedding,
            execution=BenchmarkExecutionConfig.from_mapping(execution_value),
            langfuse=LangfuseBenchmarkConfig.from_mapping(langfuse_value),
            source=dict(source),
            raw_digest=hashlib.sha256(raw).hexdigest(),
        )


class OpenRouterModelInspector:
    """Read-only OpenRouter catalogue client used before any inference call."""

    def __init__(self, models_url: str = OPENROUTER_MODELS_URL, timeout_seconds: float = 30.0):
        self.models_url = models_url
        self.timeout_seconds = timeout_seconds

    def inspect(self, model_id: str) -> OpenRouterModelInfo:
        response = requests.get(self.models_url, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data") if isinstance(payload, Mapping) else None
        if not isinstance(rows, list):
            raise ValueError("OpenRouter models response does not contain a data list")
        for row in rows:
            if isinstance(row, Mapping) and row.get("id") == model_id:
                return OpenRouterModelInfo.from_payload(row)
        endpoint_response = requests.get(
            f"{self.models_url.rstrip('/')}/{model_id}/endpoints",
            timeout=self.timeout_seconds,
        )
        endpoint_response.raise_for_status()
        endpoint_payload = endpoint_response.json()
        detail = endpoint_payload.get("data") if isinstance(endpoint_payload, Mapping) else None
        endpoints = detail.get("endpoints") if isinstance(detail, Mapping) else None
        if not isinstance(detail, Mapping) or not isinstance(endpoints, list) or not endpoints:
            raise ValueError(f"model {model_id!r} was not found in the OpenRouter catalogue")
        first_endpoint = endpoints[0] if isinstance(endpoints[0], Mapping) else {}
        architecture = detail.get("architecture")
        raw_context = architecture.get("context_length") if isinstance(architecture, Mapping) else None
        raw_parameters = {
            str(parameter)
            for endpoint in endpoints
            if isinstance(endpoint, Mapping)
            for parameter in (endpoint.get("supported_parameters") or [])
            if isinstance(parameter, str)
        }
        pricing = first_endpoint.get("pricing") if isinstance(first_endpoint, Mapping) else {}
        return OpenRouterModelInfo(
            model_id=str(detail.get("id") or model_id),
            name=str(detail.get("name") or ""),
            context_length=int(raw_context) if isinstance(raw_context, (int, float)) else None,
            supported_parameters=frozenset(raw_parameters),
            pricing=dict(pricing) if isinstance(pricing, Mapping) else {},
        )


def build_manifest(
    config: BenchmarkConfig,
    inspected_models: Mapping[str, OpenRouterModelInfo],
    sample_count: int,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": config.raw_digest,
        "metrics": list(config.metrics),
        "dry_run": dry_run,
        "sample_count": sample_count,
        "execution": asdict(config.execution),
        "langfuse": {
            "enabled": config.langfuse.enabled,
            "mode": config.langfuse.mode,
            "session_id_template": config.langfuse.session_id_template,
            "trace_name_prefix": config.langfuse.trace_name_prefix,
            "score_config_names": sorted(config.langfuse.score_config_ids or {}),
        },
        "evaluators": [
            {
                **target.to_dict(),
                "catalogue": inspected_models[target.identifier].to_dict(),
            }
            for target in config.evaluators
        ],
    }
    if config.ragas_embedding:
        manifest["ragas_embedding"] = {
            **config.ragas_embedding.to_dict(),
            "catalogue": inspected_models["ragas_embedding"].to_dict(),
        }
    return manifest


async def run_with_execution(
    coroutines: Iterable[Awaitable[_Result]], execution: BenchmarkExecutionConfig
) -> list[_Result]:
    """Run independent evaluator targets sequentially or with bounded parallelism."""
    queued = list(coroutines)
    if not execution.parallel:
        return [await coroutine for coroutine in queued]
    semaphore = asyncio.Semaphore(execution.max_concurrency)

    async def _bounded(coroutine: Awaitable[_Result]) -> _Result:
        async with semaphore:
            return await coroutine

    return list(await asyncio.gather(*(_bounded(coroutine) for coroutine in queued)))


async def evaluate_fables_sample(
    sample: FrozenFablesSample,
    target: EvaluatorTarget,
    *,
    api_key: str,
    base_url: str,
    observer: Any = None,
    site_url: str = "",
    app_name: str = "Story-Based Learning AI Benchmark",
) -> dict[str, Any]:
    """Evaluate one frozen sample without Langfuse side effects."""
    from openai import AsyncOpenAI
    from workflows.story_agent.agents.critic.eval_ragas import RagasEvaluator

    headers = {"X-Title": app_name}
    if site_url:
        headers["HTTP-Referer"] = site_url
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers)
    evaluator = RagasEvaluator(
        ragas_llm=None,
        embeddings=None,
        openai_client=client,
        model_name=target.model,
        langfuse=observer,
        openrouter_provider_preferences=dict(target.provider_preferences),
    )
    started = datetime.now(timezone.utc).isoformat()
    try:
        scores = await evaluator.run(
            answer=sample.story,
            contexts=list(sample.contexts),
            trace_id=sample.trace_id or sample.source_observation_id,
            question="Pembuatan cerita dari teks berikut: frozen evaluation replay",
            fables_replay_only=True,
        )
        return {
            "status": "completed" if scores else "failed",
            "started_at": started,
            "scores": scores,
            "error": None if scores else "FABLES returned no scores",
        }
    except Exception as exc:  # Result row preserves failure instead of inventing a score.
        return {"status": "failed", "started_at": started, "scores": {}, "error": str(exc)}
    finally:
        await client.close()


async def evaluate_ragas_sample(
    sample: FrozenFablesSample,
    target: EvaluatorTarget,
    embedding: RagasEmbeddingTarget,
    *,
    api_key: str,
    base_url: str,
    observer: Any = None,
    site_url: str = "",
    app_name: str = "Story-Based Learning AI Benchmark",
) -> dict[str, Any]:
    """Run the repository's existing RAGAS and FABLES pipeline once, without Langfuse writes."""
    from openai import AsyncOpenAI
    from ragas.embeddings import OpenAIEmbeddings
    from ragas.llms import llm_factory
    from workflows.story_agent.agents.critic.eval_ragas import RagasEvaluator

    headers = {"X-Title": app_name}
    if site_url:
        headers["HTTP-Referer"] = site_url
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers)
    ragas_llm = llm_factory(
        target.model,
        provider="openai",
        client=client,
        max_tokens=8192,
        temperature=target.temperature,
    )
    embeddings = OpenAIEmbeddings(client=client, model=embedding.model)
    evaluator = RagasEvaluator(
        ragas_llm=ragas_llm,
        embeddings=embeddings,
        openai_client=client,
        model_name=target.model,
        langfuse=observer,
        openrouter_provider_preferences=dict(target.provider_preferences),
    )
    started = datetime.now(timezone.utc).isoformat()
    try:
        scores = await evaluator.run(
            answer=sample.story,
            contexts=list(sample.contexts),
            trace_id=sample.trace_id or sample.source_observation_id,
            question=sample.question or "frozen evaluation replay",
        )
        groups = split_ragas_score_groups(scores)
        return {
            "status": "completed" if groups["ragas"] and groups["fables"] else "failed",
            "started_at": started,
            "score_groups": groups,
            "error": None if groups["ragas"] and groups["fables"] else "RAGAS returned incomplete scores",
        }
    except Exception as exc:
        return {
            "status": "failed",
            "started_at": started,
            "score_groups": {"ragas": {}, "fables": {}},
            "error": str(exc),
        }
    finally:
        await client.close()


async def evaluate_geval_sample(
    sample: FrozenGEvalSample,
    target: EvaluatorTarget,
    *,
    api_key: str,
    base_url: str,
    observer: Any = None,
    site_url: str = "",
    app_name: str = "Story-Based Learning AI Benchmark",
) -> dict[str, Any]:
    """Run the existing DeepEval G-Eval wrapper without Langfuse side effects."""
    from langchain_openai import ChatOpenAI
    from workflows.story_agent.agents.critic.eval_geval import GEvalEvaluator

    headers = {"X-Title": app_name}
    if site_url:
        headers["HTTP-Referer"] = site_url
    llm_kwargs: dict[str, Any] = {
        "model": target.model,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": target.temperature,
        "default_headers": headers,
    }
    if target.provider_preferences:
        llm_kwargs["extra_body"] = {"provider": dict(target.provider_preferences)}
    evaluator = GEvalEvaluator(ChatOpenAI(**llm_kwargs), langfuse=observer, model_name=target.model)
    started = datetime.now(timezone.utc).isoformat()
    try:
        scores = await evaluator.run(
            story_text=sample.story,
            trace_id=sample.trace_id or sample.source_observation_id,
            question=sample.question,
        )
        return {
            "status": "completed" if scores.get("geval_coherence") is not None else "failed",
            "started_at": started,
            "scores": scores,
            "error": None if scores.get("geval_coherence") is not None else "G-Eval returned no score",
        }
    except Exception as exc:
        return {"status": "failed", "started_at": started, "scores": {}, "error": str(exc)}


async def evaluate_structured_judge_sample(
    sample: FrozenStructuredJudgeSample,
    target: EvaluatorTarget,
    *,
    api_key: str,
    base_url: str,
    site_url: str = "",
    app_name: str = "Story-Based Learning AI Benchmark",
) -> dict[str, Any]:
    """Re-run a saved structured rubric with the exact historical prompt and story."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from workflows.story_agent.agents.critic.models import (
        LLMEducationalEvaluation,
        LLMCoherenceEvaluation,
    )

    schema = {
        "educational": LLMEducationalEvaluation,
        "coherence": LLMCoherenceEvaluation,
    }.get(sample.metric)
    if schema is None:
        raise ValueError(f"unsupported structured judge metric: {sample.metric}")
    headers = {"X-Title": app_name}
    if site_url:
        headers["HTTP-Referer"] = site_url
    llm_kwargs: dict[str, Any] = {
        "model": target.model,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": target.temperature,
        "default_headers": headers,
    }
    if target.provider_preferences:
        llm_kwargs["extra_body"] = {"provider": dict(target.provider_preferences)}
    llm = ChatOpenAI(**llm_kwargs).with_structured_output(schema, method="function_calling")
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = await llm.ainvoke(
            [
                SystemMessage(content=sample.system_prompt),
                HumanMessage(content=sample.story),
            ]
        )
        output = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        return {"status": "completed", "started_at": started, "scores": output, "error": None}
    except Exception as exc:
        return {"status": "failed", "started_at": started, "scores": {}, "error": str(exc)}


async def smoke_test_tool_round_trip(
    target: EvaluatorTarget,
    *,
    api_key: str,
    base_url: str,
    site_url: str = "",
    app_name: str = "Story-Based Learning AI Benchmark",
) -> dict[str, Any]:
    """Execute an explicit two-step client-tool loop after a free-model preflight."""
    from openai import AsyncOpenAI

    headers = {"X-Title": app_name}
    if site_url:
        headers["HTTP-Referer"] = site_url
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers)
    tool = {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Return the supplied text unchanged.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
        },
    }
    request: dict[str, Any] = {
        "model": target.model,
        "messages": [{"role": "user", "content": "Call echo with the exact text: benchmark"}],
        "tools": [tool],
        "tool_choice": {"type": "function", "function": {"name": "echo"}},
        "temperature": target.temperature,
    }
    if target.provider_preferences:
        request["extra_body"] = {"provider": dict(target.provider_preferences)}
    try:
        first = await client.chat.completions.create(**request)
        message = first.choices[0].message
        calls = message.tool_calls or []
        if len(calls) != 1:
            return {"status": "failed", "error": "model did not return exactly one tool call"}
        call = calls[0]
        final = await client.chat.completions.create(
            model=target.model,
            messages=[
                {"role": "user", "content": "Call echo with the exact text: benchmark"},
                message.model_dump(exclude_none=True),
                {"role": "tool", "tool_call_id": call.id, "content": '{"text":"benchmark"}'},
            ],
            tools=[tool],
            temperature=target.temperature,
            extra_body={"provider": dict(target.provider_preferences)}
            if target.provider_preferences
            else None,
        )
        return {
            "status": "completed",
            "tool_name": call.function.name,
            "final_content": final.choices[0].message.content or "",
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        await client.close()


def require_openrouter_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("OPENROUTER_API_KEY is required for non-dry benchmark execution")
    return key


def run_async(coro: Any) -> Any:
    """Run a command-line coroutine outside an existing event loop."""
    return asyncio.run(coro)
