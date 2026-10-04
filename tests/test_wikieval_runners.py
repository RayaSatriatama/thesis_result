import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_agentic_sse_parser_reads_completion_and_trace_id():
    runner = _load("wikieval_api_runner", ROOT / "scripts" / "run_wikieval_api_benchmark.py")

    events = runner.parse_sse_events(
        "event: WORKFLOW::MULAI\n"
        'data: {"job_id":"story_abc"}\n\n'
        "event: WORKFLOW::SELESAI\n"
        'data: {"job_id":"story_abc","trace_id":"trace_xyz","final_story":"done"}\n\n'
    )

    assert events[-1].event == "WORKFLOW::SELESAI"
    assert events[-1].data["trace_id"] == "trace_xyz"


def test_agentic_payload_uses_request_model_and_explicit_metadata():
    runner = _load("wikieval_api_runner_payload", ROOT / "scripts" / "run_wikieval_api_benchmark.py")

    payload = runner.build_request_payload(
        question="What is water?",
        language="Indonesian",
        model="openai/gpt-4o-mini",
        target_age="15-18",
        story_length="short",
    )

    assert payload["model"] == "openai/gpt-4o-mini"
    assert payload["language"] == "Indonesian"
    assert payload["prompt"].startswith("Buat cerita edukatif")


def test_agentic_selection_can_run_exactly_one_story():
    runner = _load("wikieval_api_runner_selection", ROOT / "scripts" / "run_wikieval_api_benchmark.py")
    rows = [
        runner.WikiEvalRow("s1", "q1", "a1", [], []),
        runner.WikiEvalRow("s2", "q2", "a2", [], []),
    ]

    selected = list(runner._selected_runs(rows, ("id",), start=0, limit=1))

    assert [(idx, language) for idx, _row, language in selected] == [(0, "id")]


def test_baseline_runner_accepts_model_and_provider_options():
    runner = _load("baseline_runner", ROOT / "baseline" / "run_baseline.py")
    parser = runner.build_argument_parser()

    args = parser.parse_args(
        [
            "--model",
            "openai/gpt-4o-mini",
            "--provider",
            "openrouter",
            "--limit",
            "1",
        ]
    )

    assert args.model == "openai/gpt-4o-mini"
    assert args.provider == "openrouter"
    assert args.limit == 1
