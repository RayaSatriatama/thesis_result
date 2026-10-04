import json
from pathlib import Path


def test_requires_every_metric_from_all_three_evaluators(tmp_path: Path):
    from evaluation.external_evaluator_gate import validate_external_evaluator_results

    result_path = tmp_path / "results.jsonl"
    evaluators = ("gpt", "gemini", "deepseek")
    rows = [
        {
            "evaluator": {"identifier": evaluator},
            "metric": metric,
            "status": "completed",
        }
        for evaluator in evaluators
        for metric in ("geval", "fables", "ragas")
    ]
    result_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    assert validate_external_evaluator_results(result_path, evaluators) == ()


def test_reports_missing_evaluator_metric(tmp_path: Path):
    from evaluation.external_evaluator_gate import validate_external_evaluator_results

    result_path = tmp_path / "results.jsonl"
    result_path.write_text(
        json.dumps(
            {
                "evaluator": {"identifier": "gpt"},
                "metric": "geval",
                "status": "completed",
            }
        )
        + "\n"
    )

    assert validate_external_evaluator_results(result_path, ("gpt",)) == (
        "gpt:fables",
        "gpt:ragas",
    )


def test_rejects_config_without_exactly_three_evaluators(tmp_path: Path):
    from evaluation.external_evaluator_gate import evaluator_ids_from_config

    config_path = tmp_path / "evaluators.json"
    config_path.write_text(json.dumps({"evaluators": [{"id": "gpt"}, {"id": "gemini"}]}))

    try:
        evaluator_ids_from_config(config_path)
    except ValueError as exc:
        assert "exactly three" in str(exc)
    else:
        raise AssertionError("invalid evaluator config was accepted")
