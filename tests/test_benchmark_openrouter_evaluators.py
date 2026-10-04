import importlib.util
import asyncio
from pathlib import Path
from types import SimpleNamespace

from evaluation.openrouter_benchmark import BenchmarkConfig


def _load_runner_module():
    path = Path(__file__).parents[1] / "scripts" / "benchmark_openrouter_evaluators.py"
    spec = importlib.util.spec_from_file_location("benchmark_openrouter_evaluators", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_export_mode_writes_one_overlay_for_all_evaluators(tmp_path):
    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        '{"evaluators":[{"id":"judge-a","model":"nvidia/nemotron-free"}]}',
        encoding="utf-8",
    )
    runner = _load_runner_module()
    reporter = runner._LangfuseBenchmarkReporter(
        BenchmarkConfig.from_json(config_path), "run-1", tmp_path
    )
    rows = [
        {
            "source_trace_id": "trace-1",
            "source_root_observation_id": "root-1",
            "source_observation_id": "critic-1",
            "metric": "geval",
            "status": "completed",
            "error": None,
            "scores": {"geval_coherence_normalized": 0.7},
            "evaluator": {
                "identifier": "judge-a",
                "model": "nvidia/nemotron-free",
                "provider_preferences": {},
            },
        },
        {
            "source_trace_id": "trace-1",
            "source_root_observation_id": "root-1",
            "source_observation_id": "critic-1",
            "metric": "geval",
            "status": "completed",
            "error": None,
            "scores": {"geval_coherence_normalized": 0.8},
            "evaluator": {
                "identifier": "judge-b",
                "model": "qwen/qwen3-235b-a22b:free",
                "provider_preferences": {},
            },
        },
    ]

    reporter.record(rows)

    overlay_path = tmp_path / "trace_overlays" / "trace-1.json"
    assert overlay_path.exists()
    assert '"judge-a"' in overlay_path.read_text(encoding="utf-8")
    assert '"judge-b"' in overlay_path.read_text(encoding="utf-8")


def test_source_trace_mode_nests_evaluators_and_scores_under_the_source_root(tmp_path, monkeypatch):
    class Writer:
        def __init__(self):
            self.spans = []
            self.scores = []

        def start_span(self, *, trace_id, parent_observation_id, name, input_data, metadata):
            observation_id = f"observation-{len(self.spans) + 1}"
            self.spans.append(
                {
                    "id": observation_id,
                    "trace_id": trace_id,
                    "parent_observation_id": parent_observation_id,
                    "name": name,
                    "input": input_data,
                    "metadata": metadata,
                }
            )
            return observation_id

        def end_span(self, **_kwargs):
            return None

        def create_score(self, **kwargs):
            self.scores.append(kwargs)

        def flush(self):
            return None

    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        '{"evaluators":[{"id":"judge-a","model":"nvidia/nemotron-free"}],'
        '"langfuse":{"enabled":true,"mode":"source_trace"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret")
    runner = _load_runner_module()
    reporter = runner._LangfuseBenchmarkReporter(
        BenchmarkConfig.from_json(config_path), "run-1", tmp_path
    )
    writer = Writer()
    reporter._source_trace_writer = writer
    rows = [
        {
            "source_trace_id": "trace-1",
            "source_root_observation_id": "root-1",
            "source_observation_id": "critic-1",
            "metric": "geval",
            "status": "completed",
            "error": None,
            "scores": {"geval_coherence_normalized": 0.7},
            "evaluator": {
                "identifier": "judge-a",
                "model": "nvidia/nemotron-free",
                "provider_preferences": {},
            },
        },
        {
            "source_trace_id": "trace-1",
            "source_root_observation_id": "root-1",
            "source_observation_id": "fables-1",
            "metric": "fables",
            "status": "completed",
            "error": None,
            "scores": {"fables_faithfulness": 1.0},
            "evaluator": {
                "identifier": "judge-b",
                "model": "qwen/qwen3-235b-a22b:free",
                "provider_preferences": {},
            },
        },
    ]

    reporter.record(rows)

    assert [(span["name"], span["parent_observation_id"]) for span in writer.spans] == [
        ("external_benchmark_evaluation", "root-1"),
        ("judge-a", "observation-1"),
        ("geval", "observation-2"),
        ("judge-b", "observation-1"),
        ("fables", "observation-4"),
    ]
    assert {(score["name"], score["observation_id"]) for score in writer.scores} == {
        ("geval_coherence_normalized", "observation-2"),
        ("fables_faithfulness", "observation-4"),
    }


def test_source_trace_mode_uses_explicit_ingestion_parents_not_sdk_trace_context(
    tmp_path, monkeypatch
):
    """Keep the source trace name intact when benchmarking its child observations."""

    class LegacySdkClient:
        def start_as_current_observation(self, **_kwargs):
            raise AssertionError("source_trace must not use SDK trace_context")

    class IngestionWriter:
        def __init__(self):
            self.spans = []
            self.generations = []
            self.scores = []

        def start_span(self, *, trace_id, parent_observation_id, name, input_data, metadata):
            observation_id = f"ingested-{len(self.spans) + 1}"
            self.spans.append(
                {
                    "id": observation_id,
                    "trace_id": trace_id,
                    "parent_observation_id": parent_observation_id,
                    "name": name,
                    "input": input_data,
                    "metadata": metadata,
                }
            )
            return observation_id

        def end_span(self, **_kwargs):
            return None

        def log_generation(self, **kwargs):
            self.generations.append(kwargs)

        def create_score(self, **kwargs):
            self.scores.append(kwargs)

        def flush(self):
            return None

    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        '{"evaluators":[{"id":"judge-a","model":"model-a"}],'
        '"langfuse":{"enabled":true,"mode":"source_trace"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret")
    runner = _load_runner_module()
    reporter = runner._LangfuseBenchmarkReporter(
        BenchmarkConfig.from_json(config_path), "run-1", tmp_path
    )
    writer = IngestionWriter()
    reporter.client = LegacySdkClient()
    reporter._source_trace_writer = writer
    sample = SimpleNamespace(
        trace_id="trace-1",
        source_observation_id="critic-1",
        source_root_observation_id="root-1",
    )

    observers = reporter.prepare_source_trace_observers({"geval": [sample]})
    observers[("trace-1", "judge-a")].log_generation(
        name="geval_clarity",
        model="model-a",
        input_text="story",
        output_text="score",
    )

    assert [(span["name"], span["parent_observation_id"]) for span in writer.spans] == [
        ("external_benchmark_evaluation", "root-1"),
        ("judge-a", "ingested-1"),
    ]
    assert writer.generations[0]["parent_observation_id"] == "ingested-2"


def test_ingestion_writer_sends_benchmark_scores_to_the_underlying_sdk_client():
    class SdkClient:
        def __init__(self):
            self.scores = []

        def create_score(self, **kwargs):
            self.scores.append(kwargs)

    class LangfuseWrapper:
        def __init__(self):
            self.client = SdkClient()

    runner = _load_runner_module()
    client = LangfuseWrapper()
    writer = runner._BenchmarkIngestionWriter(client)

    writer.create_score(
        trace_id="trace-1",
        observation_id="evaluator-1",
        name="geval_coherence_normalized",
        value=0.8,
        config_id="config-1",
        score_id="score-1",
        data_type="NUMERIC",
        metadata={"evaluator_id": "judge-a"},
        timestamp="2026-10-04T00:00:00Z",
    )

    assert client.client.scores[0]["config_id"] == "config-1"
    assert client.client.scores[0]["score_id"] == "score-1"


def test_source_trace_observer_records_native_evaluator_processes_under_its_model():
    """Removing the observer must hide the metric process tree, not only its scores."""

    class Writer:
        def __init__(self):
            self.spans = []
            self.generations = []
            self.ended = []

        def start_span(self, *, trace_id, parent_observation_id, name, input_data, metadata):
            observation_id = f"observation-{len(self.spans) + 1}"
            self.spans.append(
                {
                    "id": observation_id,
                    "trace_id": trace_id,
                    "parent_observation_id": parent_observation_id,
                    "name": name,
                }
            )
            return observation_id

        def end_span(self, **kwargs):
            self.ended.append(kwargs)

        def log_generation(self, **kwargs):
            self.generations.append(kwargs)

    runner = _load_runner_module()
    writer = Writer()
    observer = runner._BenchmarkEvaluatorObserver(
        writer=writer,
        trace_id="trace-1",
        evaluator_observation_id="judge-1",
    )

    ragas_span = observer.start_span(
        name="ragas_evaluation",
        input_data={"contexts_count": 2},
    )
    observer.log_generation(
        name="ragas_answer_relevancy",
        model="openai/gpt-4o-mini",
        input_text="question",
        output_text='{"score": 0.5}',
    )
    fables_span = observer.start_span(name="fables_faithfulness", input_data={"story_length": 20})
    observer.log_generation(
        name="fables_extract_claims",
        model="openai/gpt-4o-mini",
        input_text="story",
        output_text='{"claims": ["claim"]}',
    )
    observer.end_span(fables_span, output_data={"fables_faithfulness": 1.0})
    observer.end_span(ragas_span, output_data={"ragas_answer_relevancy": 0.5})

    assert [(span["name"], span["parent_observation_id"]) for span in writer.spans] == [
        ("ragas_evaluation", "judge-1"),
        ("fables_faithfulness", "observation-1"),
    ]
    assert [generation["parent_observation_id"] for generation in writer.generations] == [
        "observation-1",
        "observation-2",
    ]
    assert writer.ended[0]["output_data"] == {"fables_faithfulness": 1.0}


def test_source_trace_mode_prepares_one_live_observer_per_model_and_reuses_it_for_scores(
    tmp_path, monkeypatch
):
    """A later score write must reuse the live model node, not create a duplicate node."""

    class Writer:
        def __init__(self):
            self.spans = []
            self.scores = []

        def start_span(self, *, trace_id, parent_observation_id, name, input_data, metadata):
            observation_id = f"observation-{len(self.spans) + 1}"
            self.spans.append(
                {
                    "id": observation_id,
                    "trace_id": trace_id,
                    "parent_observation_id": parent_observation_id,
                    "name": name,
                }
            )
            return observation_id

        def end_span(self, **_kwargs):
            return None

        def create_score(self, **kwargs):
            self.scores.append(kwargs)

        def flush(self):
            return None

    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        '{"evaluators":[{"id":"judge-a","model":"model-a"},'
        '{"id":"judge-b","model":"model-b"}],'
        '"langfuse":{"enabled":true,"mode":"source_trace"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret")
    runner = _load_runner_module()
    reporter = runner._LangfuseBenchmarkReporter(
        BenchmarkConfig.from_json(config_path), "run-1", tmp_path
    )
    writer = Writer()
    reporter._source_trace_writer = writer
    sample = SimpleNamespace(
        trace_id="trace-1",
        source_observation_id="critic-1",
        source_root_observation_id="root-1",
    )

    observers = reporter.prepare_source_trace_observers({"geval": [sample]})
    reporter.record(
        [
            {
                "source_trace_id": "trace-1",
                "source_root_observation_id": "root-1",
                "source_observation_id": "critic-1",
                "metric": "geval",
                "status": "completed",
                "error": None,
                "scores": {"geval_coherence_normalized": 0.7},
                "evaluator": {
                    "identifier": "judge-a",
                    "model": "model-a",
                    "provider_preferences": {},
                },
            }
        ]
    )

    assert set(observers) == {("trace-1", "judge-a"), ("trace-1", "judge-b")}
    assert [span["name"] for span in writer.spans] == [
        "external_benchmark_evaluation",
        "judge-a",
        "judge-b",
    ]
    assert writer.scores[0]["observation_id"] == observers[("trace-1", "judge-a")].evaluator_observation_id


def test_evaluate_target_passes_prepared_observer_into_native_geval(tmp_path, monkeypatch):
    """The native G-Eval call must receive the scoped observer rather than None."""

    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        '{"evaluators":[{"id":"judge-a","model":"model-a"}]}' , encoding="utf-8"
    )
    runner = _load_runner_module()
    config = BenchmarkConfig.from_json(config_path)
    sample = SimpleNamespace(
        trace_id="trace-1",
        source_observation_id="critic-1",
        source_root_observation_id="root-1",
        source_evaluator_model="generator-model",
    )
    observer = object()
    received = []

    async def fake_geval(*_args, observer=None, **_kwargs):
        received.append(observer)
        return {
            "status": "completed",
            "started_at": "now",
            "scores": {"geval_coherence_normalized": 0.7},
            "error": None,
        }

    monkeypatch.setattr(runner, "evaluate_geval_sample", fake_geval)
    rows = asyncio.run(
        runner._evaluate_target(
            config.evaluators[0],
            args=SimpleNamespace(smoke_tools=False),
            config=config,
            samples_by_metric={"geval": [sample]},
            api_key="test-key",
            base_url="https://example.invalid",
            observers={("trace-1", "judge-a"): observer},
        )
    )

    assert received == [observer]
    assert rows[0]["metric"] == "geval"
