import ast
from pathlib import Path


def test_all_ragas_and_fables_requests_share_the_extended_timeout():
    source_path = (
        Path(__file__).parents[1]
        / "src/workflows/story_agent/agents/critic/eval_ragas.py"
    )
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    constants = {
        node.targets[0].id: node.value.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert constants["EVALUATION_TIMEOUT_SECONDS"] == 1800

    timeouts = [
        node.keywords[-1].value.id
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "wait_for"
        and node.keywords
        and node.keywords[-1].arg == "timeout"
        and isinstance(node.keywords[-1].value, ast.Name)
    ]
    assert timeouts == ["EVALUATION_TIMEOUT_SECONDS"] * 3
