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


def test_selects_only_generated_stories_missing_external_evaluation():
    recovery = _load(
        "wikieval_external_recovery",
        ROOT / "scripts" / "recover_wikieval_external_evaluations.py",
    )
    rows = [
        {"item_idx": 0, "language": "id", "final_story": "story", "trace_id": "trace-0"},
        {
            "item_idx": 1,
            "language": "id",
            "final_story": "story",
            "trace_id": "trace-1",
            "external_evaluation_status": "completed",
        },
        {"item_idx": 2, "language": "id", "error": "generation failed"},
        {"item_idx": 3, "language": "id", "final_story": "story"},
    ]

    selected = recovery.select_recovery_rows(rows)

    assert [(row["item_idx"], row["trace_id"]) for row in selected] == [(0, "trace-0")]


def test_removes_only_rows_that_never_generated_a_story():
    recovery = _load(
        "wikieval_external_recovery_cleanup",
        ROOT / "scripts" / "recover_wikieval_external_evaluations.py",
    )
    rows = [
        {"item_idx": 0, "language": "id", "error": "generation failed"},
        {"item_idx": 1, "language": "id", "final_story": "story", "trace_id": "trace-1"},
    ]

    kept, removed = recovery.remove_generation_failures(rows)

    assert [row["item_idx"] for row in kept] == [1]
    assert removed == 1
