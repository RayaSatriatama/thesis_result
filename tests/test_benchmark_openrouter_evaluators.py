import importlib.util
import asyncio
from pathlib import Path
from contextlib import contextmanager
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
    class Observation:
        def __init__(self, identifier):
            self.id = identifier

    class Client:
        def __init__(self):
            self.calls = []
            self.scores = []

        @contextmanager
        def start_as_current_observation(self, **kwargs):
            self.calls.append(kwargs)
            yield Observation(f"observation-{len(self.calls)}")

        def create_score(self, **kwargs):
            self.scores.append(kwargs)

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
    reporter.client = client = Client()
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

    assert client.calls[0]["name"] == "external_benchmark_evaluation"
    assert client.calls[0]["trace_context"] == {
        "trace_id": "trace-1",
        "parent_span_id": "root-1",
    }
    assert [call["name"] for call in client.calls[1:]] == [
        "judge-a",
        "geval",
        "judge-b",
        "fables",
    ]
    assert {(score["name"], score["observation_id"]) for score in client.scores} == {
        ("geval_coherence_normalized", "observation-2"),
        ("fables_faithfulness", "observation-4"),
    }


def test_source_trace_observer_records_native_evaluator_processes_under_its_model():
    """Removing the observer must hide the metric process tree, not only its scores."""

    class Observation:
        def __init__(self, identifier):
            self.id = identifier
            self.output = None

        def update(self, *, output=None, **_kwargs):
            self.output = output

    class Client:
        def __init__(self):
            self.calls = []

        @contextmanager
        def start_as_current_observation(self, **kwargs):
            observation = Observation(f"observation-{len(self.calls) + 1}")
            self.calls.append({"kwargs": kwargs, "observation": observation})
            yield observation

    runner = _load_runner_module()
    client = Client()
    observer = runner._BenchmarkEvaluatorObserver(
        client=client,
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

    calls = {call["kwargs"]["name"]: call for call in client.calls}
    assert "end_on_exit" not in calls["ragas_evaluation"]["kwargs"]
    assert calls["ragas_evaluation"]["kwargs"]["trace_context"] == {
        "trace_id": "trace-1",
        "parent_span_id": "judge-1",
    }
    assert calls["ragas_answer_relevancy"]["kwargs"]["trace_context"]["parent_span_id"] == (
        calls["ragas_evaluation"]["observation"].id
    )
    assert calls["fables_faithfulness"]["kwargs"]["trace_context"]["parent_span_id"] == (
        calls["ragas_evaluation"]["observation"].id
    )
    assert calls["fables_extract_claims"]["kwargs"]["trace_context"]["parent_span_id"] == (
        calls["fables_faithfulness"]["observation"].id
    )
    assert calls["fables_faithfulness"]["observation"].output == {"fables_faithfulness": 1.0}


def test_source_trace_mode_prepares_one_live_observer_per_model_and_reuses_it_for_scores(
    tmp_path, monkeypatch
):
    """A later score write must reuse the live model node, not create a duplicate node."""

    class Observation:
        def __init__(self, identifier):
            self.id = identifier

    class Client:
        def __init__(self):
            self.calls = []
            self.scores = []

        @contextmanager
        def start_as_current_observation(self, **kwargs):
            observation = Observation(f"observation-{len(self.calls) + 1}")
            self.calls.append({"kwargs": kwargs, "observation": observation})
            yield observation

        def create_score(self, **kwargs):
            self.scores.append(kwargs)

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
    reporter.client = client = Client()
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
    assert [call["kwargs"]["name"] for call in client.calls] == [
        "external_benchmark_evaluation",
        "judge-a",
        "judge-b",
    ]
    assert client.scores[0]["observation_id"] == observers[("trace-1", "judge-a")].evaluator_observation_id


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
