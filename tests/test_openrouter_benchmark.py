import asyncio
import json

import pytest

from evaluation.openrouter_benchmark import (
    BenchmarkConfig,
    BenchmarkExecutionConfig,
    build_benchmark_trace_overlay,
    OpenRouterModelInfo,
    OpenRouterModelInspector,
    benchmark_score_values,
    extract_fables_samples,
    extract_geval_samples,
    extract_structured_judge_samples,
    run_with_execution,
    split_ragas_score_groups,
    validate_model_for_run,
)


def test_free_model_with_required_capabilities_is_accepted():
    model = OpenRouterModelInfo.from_payload(
        {
            "id": "nvidia/nemotron-free",
            "supported_parameters": ["tools", "structured_outputs"],
            "pricing": {"prompt": "0", "completion": "0", "request": "0"},
        }
    )

    assert validate_model_for_run(
        model, required_parameters={"tools", "structured_outputs"}, require_free=True
    ) == []


def test_model_inspector_reads_embedding_only_available_from_endpoint(monkeypatch):
    """Prevent RAGAS embeddings from being rejected when absent from /models."""

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, timeout):
        if url == "https://example.test/models":
            return Response({"data": [{"id": "openai/gpt-4o-mini"}]})
        assert url == "https://example.test/models/openai/text-embedding-3-small/endpoints"
        return Response(
            {
                "data": {
                    "id": "openai/text-embedding-3-small",
                    "name": "OpenAI: text-embedding-3-small",
                    "architecture": {"context_length": 8192},
                    "endpoints": [
                        {
                            "pricing": {"prompt": "0.00000002", "completion": "0"},
                            "supported_parameters": [],
                        }
                    ],
                }
            }
        )

    monkeypatch.setattr("evaluation.openrouter_benchmark.requests.get", fake_get)

    model = OpenRouterModelInspector("https://example.test/models").inspect(
        "openai/text-embedding-3-small"
    )

    assert model.model_id == "openai/text-embedding-3-small"
    assert model.pricing == {"prompt": "0.00000002", "completion": "0"}


def test_validation_rejects_router_alias_paid_or_missing_capability():
    model = OpenRouterModelInfo.from_payload(
        {
            "id": "example/model",
            "supported_parameters": ["tools"],
            "pricing": {"prompt": "0.1", "completion": "0", "request": "0"},
        }
    )

    errors = validate_model_for_run(
        model, required_parameters={"structured_outputs"}, require_free=True
    )

    assert "is not free" in " ".join(errors)
    assert "structured_outputs" in " ".join(errors)


def test_config_rejects_non_deterministic_free_router_alias(tmp_path):
    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        json.dumps(
            {
                "evaluators": [
                    {
                        "id": "bad-router",
                        "model": "openrouter/free",
                        "require_free": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="openrouter/free"):
        BenchmarkConfig.from_json(config_path)


def test_config_accepts_the_three_existing_evaluator_groups(tmp_path):
    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        json.dumps(
            {
                "metrics": ["geval", "fables", "ragas"],
                "ragas": {
                    "embedding_model": "qwen/qwen3-embedding-8b:free",
                    "require_free": True,
                },
                "evaluators": [{"id": "judge", "model": "nvidia/nemotron-free"}],
            }
        ),
        encoding="utf-8",
    )

    config = BenchmarkConfig.from_json(config_path)

    assert config.metrics == ("geval", "fables", "ragas")
    assert config.ragas_embedding.model == "qwen/qwen3-embedding-8b:free"
    assert config.ragas_embedding.require_free is True


def test_benchmark_defaults_to_parallel_execution_and_disabled_langfuse(tmp_path):
    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        json.dumps({"evaluators": [{"id": "judge", "model": "nvidia/nemotron-free"}]}),
        encoding="utf-8",
    )

    config = BenchmarkConfig.from_json(config_path)

    assert config.execution.parallel is True
    assert config.execution.max_concurrency == 3
    assert config.langfuse.enabled is False
    assert config.langfuse.mode == "local_export"


def test_benchmark_accepts_explicit_langfuse_score_config_mapping(tmp_path):
    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        json.dumps(
            {
                "evaluators": [{"id": "judge", "model": "nvidia/nemotron-free"}],
                "execution": {"parallel": False, "max_concurrency": 1},
                "langfuse": {
                    "enabled": True,
                    "mode": "source_trace",
                    "session_id_template": "benchmark:{source_trace_id}",
                    "trace_name_prefix": "BenchmarkEvaluation",
                    "score_config_ids": {"geval_coherence_normalized": "cfg-geval"},
                },
            }
        ),
        encoding="utf-8",
    )

    config = BenchmarkConfig.from_json(config_path)

    assert config.execution.parallel is False
    assert config.langfuse.enabled is True
    assert config.langfuse.mode == "source_trace"
    assert config.langfuse.session_id_template == "benchmark:{source_trace_id}"
    assert config.langfuse.score_config_ids == {"geval_coherence_normalized": "cfg-geval"}


def test_benchmark_score_values_excludes_internal_and_detail_scores():
    values = benchmark_score_values(
        "geval",
        {
            "geval_coherence_normalized": 0.7,
            "geval_coherence_fluency": 4,
            "geval_coherence_reason": "detail evaluasi",
        },
    )

    assert values == {"geval_coherence_normalized": 0.7}


def test_benchmark_score_values_renames_ragas_result_keys_for_langfuse():
    """Prevent completed RAGAS metrics from disappearing from evaluator trace badges."""
    values = benchmark_score_values(
        "ragas",
        {"answer_relevancy": 0.6, "context_relevance": 0.75, "debug": "ignore"},
    )

    assert values == {
        "ragas_answer_relevancy": 0.6,
        "ragas_context_relevance": 0.75,
    }


@pytest.mark.asyncio
async def test_default_parallel_execution_starts_independent_targets_together():
    started: set[str] = set()
    all_started = asyncio.Event()
    release = asyncio.Event()

    async def run_target(identifier: str) -> str:
        started.add(identifier)
        if len(started) == 2:
            all_started.set()
        await release.wait()
        return identifier

    execution = asyncio.create_task(
        run_with_execution(
            [run_target("first"), run_target("second")], BenchmarkExecutionConfig()
        )
    )
    await asyncio.wait_for(all_started.wait(), timeout=1)
    release.set()

    assert await execution == ["first", "second"]


def test_config_requires_an_explicit_embedding_model_for_ragas(tmp_path):
    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        json.dumps(
            {
                "metrics": ["ragas"],
                "evaluators": [{"id": "judge", "model": "nvidia/nemotron-free"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ragas.embedding_model"):
        BenchmarkConfig.from_json(config_path)


def test_extract_fables_samples_reads_frozen_story_and_contexts():
    rows = [
        {
            "id": "observation-1",
            "traceId": "trace-1",
            "name": "fables_verify_all_claims",
            "input": json.dumps(
                {
                    "model": "google/gemini-2.5-flash",
                    "user_input": "Cerita beku.",
                    "contexts": ["Sumber A", "Sumber B"],
                }
            ),
        },
        {"id": "other", "name": "unrelated"},
    ]

    samples = extract_fables_samples(rows)

    assert len(samples) == 1
    assert samples[0].source_observation_id == "observation-1"
    assert samples[0].story == "Cerita beku."
    assert samples[0].contexts == ("Sumber A", "Sumber B")
    assert samples[0].source_evaluator_model == "google/gemini-2.5-flash"


def test_extract_fables_samples_keeps_source_root_observation_id():
    rows = [
        {
            "id": "root-1",
            "traceId": "trace-1",
            "name": "StoryGenerationWorkflow",
        },
        {
            "id": "observation-1",
            "traceId": "trace-1",
            "parentObservationId": "critic-1",
            "name": "fables_verify_all_claims",
            "input": {
                "user_input": "Cerita beku.",
                "contexts": ["Sumber A"],
            },
        },
    ]

    samples = extract_fables_samples(rows)

    assert samples[0].source_root_observation_id == "root-1"


def test_extract_fables_samples_recovers_missing_contexts_from_ragas_trace():
    rows = [
        {
            "id": "ragas-context",
            "traceId": "trace-2",
            "name": "ragas_context_relevance",
            "input": json.dumps({"contexts": ["Recovered source"]}),
        },
        {
            "id": "fables-missing-context",
            "traceId": "trace-2",
            "name": "fables_verify_all_claims",
            "input": json.dumps(
                {"model": "google/gemini-2.5-flash", "user_input": "Cerita dua.", "contexts": []}
            ),
        },
    ]

    samples = extract_fables_samples(rows)

    assert len(samples) == 1
    assert samples[0].contexts == ("Recovered source",)
    assert samples[0].context_origin == "ragas_context_relevance"


def test_extract_fables_samples_recovers_question_from_ragas_trace():
    rows = [
        {
            "id": "ragas-evaluation",
            "traceId": "trace-3",
            "name": "ragas_evaluation",
            "input": {"user_input": "Pembuatan cerita dari teks berikut: Jelaskan air."},
        },
        {
            "id": "fables-3",
            "traceId": "trace-3",
            "name": "fables_verify_all_claims",
            "input": json.dumps(
                {"user_input": "Cerita air.", "contexts": ["Air menguap karena panas."]}
            ),
        },
    ]

    samples = extract_fables_samples(rows)

    assert samples[0].question == "Jelaskan air."


def test_extract_fables_samples_reads_current_workflow_fables_observation():
    """Current workflow traces keep FABLES metadata separate from story and contexts."""
    rows = [
        {
            "id": "root-4",
            "traceId": "trace-4",
            "name": "StoryGenerationWorkflow",
        },
        {
            "id": "critic-4",
            "traceId": "trace-4",
            "parentObservationId": "root-4",
            "name": "critic_agent",
            "input": {"story_content": "Cerita peluncuran."},
        },
        {
            "id": "ragas-question-4",
            "traceId": "trace-4",
            "name": "ragas_evaluation",
            "input": {"user_input": "Pembuatan cerita dari teks berikut: Kapan roket meluncur?"},
        },
        {
            "id": "ragas-context-4",
            "traceId": "trace-4",
            "name": "ragas_context_relevance",
            "input": {"contexts": ["Roket meluncur pukul enam."]},
        },
        {
            "id": "fables-summary-4",
            "traceId": "trace-4",
            "parentObservationId": "ragas-question-4",
            "name": "fables_faithfulness",
            "input": {"model": "deepseek/deepseek-v4.1-flash"},
        },
    ]

    samples = extract_fables_samples(rows)

    assert len(samples) == 1
    assert samples[0].source_observation_id == "fables-summary-4"
    assert samples[0].story == "Cerita peluncuran."
    assert samples[0].contexts == ("Roket meluncur pukul enam.",)
    assert samples[0].context_origin == "ragas_context_relevance"
    assert samples[0].question == "Kapan roket meluncur?"
    assert samples[0].source_root_observation_id == "root-4"


def test_split_ragas_score_groups_keeps_fables_inside_existing_ragas_result():
    grouped = split_ragas_score_groups(
        {
            "answer_relevancy": 0.8,
            "context_relevance": 0.9,
            "fables_faithfulness": 1.0,
            "ragas_standard_faithfulness": 0.75,
            "fables_claims_total": 4,
        }
    )

    assert grouped["ragas"] == {"answer_relevancy": 0.8, "context_relevance": 0.9}
    assert grouped["fables"] == {
        "fables_faithfulness": 1.0,
        "ragas_standard_faithfulness": 0.75,
        "fables_claims_total": 4,
    }


def test_extract_geval_samples_reads_final_story_and_original_question():
    rows = [
        {
            "id": "critic-final-1",
            "traceId": "trace-geval-1",
            "name": "critic_agent",
            "input": {
                "user_message": "Jelaskan siklus air.",
                "story_content": "Cerita tentang penguapan dan hujan.",
            },
            "output": {"ragas_scores": {"geval_coherence": 4.8}},
        }
    ]

    samples = extract_geval_samples(rows)

    assert len(samples) == 1
    assert samples[0].source_observation_id == "critic-final-1"
    assert samples[0].trace_id == "trace-geval-1"
    assert samples[0].question == "Jelaskan siklus air."
    assert samples[0].story == "Cerita tentang penguapan dan hujan."


def test_extract_geval_samples_recovers_agentic_story_and_question_from_ragas_fables():
    rows = [
        {
            "id": "root-agentic",
            "traceId": "trace-agentic",
            "name": "StoryGenerationWorkflow",
        },
        {
            "id": "critic-agentic",
            "traceId": "trace-agentic",
            "name": "critic_agent",
            "input": {"theme": "Siklus air"},
            "output": {"ragas_scores": {"geval_coherence": 4.2}},
        },
        {
            "id": "ragas-context-agentic",
            "traceId": "trace-agentic",
            "name": "ragas_context_relevance",
            "input": {"user_input": "Pembuatan cerita dari teks berikut: Jelaskan siklus air."},
        },
        {
            "id": "fables-agentic",
            "traceId": "trace-agentic",
            "name": "fables_verify_all_claims",
            "input": {"model": "google/gemini-2.5-flash", "user_input": "Cerita air."},
        },
    ]

    samples = extract_geval_samples(rows)

    assert len(samples) == 1
    assert samples[0].source_observation_id == "critic-agentic"
    assert samples[0].question == "Jelaskan siklus air."
    assert samples[0].story == "Cerita air."
    assert samples[0].source_root_observation_id == "root-agentic"


def test_extract_geval_samples_keeps_source_root_observation_id():
    rows = [
        {
            "id": "root-geval-1",
            "traceId": "trace-geval-1",
            "name": "StoryGenerationWorkflow",
        },
        {
            "id": "critic-final-1",
            "traceId": "trace-geval-1",
            "parentObservationId": "root-geval-1",
            "name": "critic_agent",
            "input": {"user_message": "Jelaskan siklus air.", "story_content": "Cerita air."},
            "output": {"ragas_scores": {"geval_coherence": 4.8}},
        },
    ]

    samples = extract_geval_samples(rows)

    assert samples[0].source_root_observation_id == "root-geval-1"


def test_extract_geval_samples_accepts_baseline_root_observation():
    rows = [
        {
            "id": "baseline-root",
            "traceId": "trace-baseline",
            "name": "BaselineWikiEvalWorkflow",
            "parentObservationId": None,
        },
        {
            "id": "critic-baseline",
            "traceId": "trace-baseline",
            "name": "critic_agent",
            "parentObservationId": "baseline-root",
            "input": {
                "user_message": "Question",
                "story_content": "Story",
            },
            "output": {"ragas_scores": {"geval_coherence": 3.0}},
        },
    ]

    samples = extract_geval_samples(rows)

    assert len(samples) == 1
    assert samples[0].source_root_observation_id == "baseline-root"


def test_benchmark_trace_overlay_places_each_model_under_one_source_root():
    rows = [
        {
            "source_trace_id": "trace-1",
            "source_root_observation_id": "root-1",
            "source_observation_id": "critic-1",
            "metric": "geval",
            "status": "completed",
            "error": None,
            "scores": {"geval_coherence_normalized": 0.7},
            "evaluator": {"identifier": "gpt4o-mini-openai", "model": "openai/gpt-4o-mini"},
        },
        {
            "source_trace_id": "trace-1",
            "source_root_observation_id": "root-1",
            "source_observation_id": "fables-1",
            "metric": "fables",
            "status": "completed",
            "error": None,
            "scores": {"fables_faithfulness": 1.0},
            "evaluator": {"identifier": "gpt4o-mini-openai", "model": "openai/gpt-4o-mini"},
        },
        {
            "source_trace_id": "trace-1",
            "source_root_observation_id": "root-1",
            "source_observation_id": "critic-1",
            "metric": "geval",
            "status": "completed",
            "error": None,
            "scores": {"geval_coherence_normalized": 0.9},
            "evaluator": {"identifier": "gemini-google", "model": "google/gemini-2.5-flash"},
        },
    ]

    overlay = build_benchmark_trace_overlay(rows, benchmark_run_id="run-1")

    group = overlay["root"]["children"][0]
    assert overlay["source_trace_id"] == "trace-1"
    assert group["name"] == "external_benchmark_evaluation"
    assert [node["name"] for node in group["children"]] == [
        "gpt4o-mini-openai",
        "gemini-google",
    ]
    assert [node["name"] for node in group["children"][0]["children"]] == ["geval", "fables"]
    assert group["children"][0]["scores"] == {
        "geval_coherence_normalized": 0.7,
        "fables_faithfulness": 1.0,
    }


def test_extract_structured_judge_samples_preserves_historical_prompt_and_story():
    rows = [
        {
            "id": "educational-1",
            "traceId": "trace-3",
            "name": "critic_educational_eval_llm",
            "input": json.dumps(
                {
                    "model": "google/gemini-2.5-flash",
                    "system_prompt": "Judge educational quality.",
                    "user_input": "Cerita tiga.",
                }
            ),
        }
    ]

    samples = extract_structured_judge_samples(rows, "educational")

    assert len(samples) == 1
    assert samples[0].metric == "educational"
    assert samples[0].system_prompt == "Judge educational quality."
    assert samples[0].story == "Cerita tiga."


def test_openrouter_factory_keeps_routing_preferences_in_request_body(monkeypatch):
    from providers.llm_factory import get_llm

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    llm = get_llm(
        provider="openrouter",
        model_name="nvidia/nemotron-free",
        openrouter_provider_preferences={
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny",
        },
    )

    assert llm.extra_body == {
        "provider": {
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny",
        }
    }


def test_openrouter_factory_uses_global_generation_provider_preferences(monkeypatch):
    """Prevent a full workflow from silently load-balancing its generation model."""
    from providers.llm_factory import get_llm

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv(
        "OPENROUTER_PROVIDER_PREFERENCES",
        '{"only":["openai"],"allow_fallbacks":false,"require_parameters":true}',
    )

    llm = get_llm(provider="openrouter", model_name="openai/gpt-4o-mini")

    assert llm.extra_body == {
        "provider": {
            "only": ["openai"],
            "allow_fallbacks": False,
            "require_parameters": True,
        }
    }
