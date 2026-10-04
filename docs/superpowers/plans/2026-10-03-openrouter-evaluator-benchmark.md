# OpenRouter Evaluator Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reproducible, role-separated OpenRouter evaluator benchmarks for frozen Gemini outputs.

**Architecture:** A small evaluation package parses frozen FABLES observations, validates a named OpenRouter model against the live model catalogue, and executes evaluator calls without Langfuse. The existing LLM factory gains an explicit OpenRouter routing object so runtime Critic and the benchmark share the same routing contract.

**Tech Stack:** Python 3.9+, OpenAI-compatible OpenRouter API, LangChain OpenAI, Ragas, pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-openrouter-evaluator-benchmark.md`

## Global Constraints

- API keys are read from environment variables and never stored in configuration or artifacts.
- Every benchmark model is an explicit stable slug, never `openrouter/free`.
- Benchmark artifacts are additive and source exports are read-only.
- Models requiring structured evaluator metrics must advertise `structured_outputs`; tool smoke tests also require `tools`.

---

### Task 1: Establish benchmark configuration and model preflight

**Files:**
- Create: `src/evaluation/openrouter_benchmark.py`
- Test: `tests/test_openrouter_benchmark.py`

**Interfaces:**
- Produces `BenchmarkConfig.from_json(path)`, `OpenRouterModelInspector.inspect(model)`, and `validate_model_for_run(...)`.

- [ ] **Step 1: Write failing configuration and capability tests**

```python
def test_free_model_with_required_capabilities_is_accepted():
    assert validate_model_for_run(model, {"tools"}, True) == []
```

- [ ] **Step 2: Run `pytest tests/test_openrouter_benchmark.py -v` and confirm the import fails.**
- [ ] **Step 3: Implement typed config, live catalogue parsing, and deterministic validation.**
- [ ] **Step 4: Rerun the focused tests and confirm they pass.**

### Task 2: Add frozen FABLES evaluator runner

**Files:**
- Modify: `src/evaluation/openrouter_benchmark.py`
- Create: `scripts/benchmark_openrouter_evaluators.py`
- Test: `tests/test_openrouter_benchmark.py`

**Interfaces:**
- Consumes exported observation JSONL and `BenchmarkConfig`.
- Produces a manifest and one JSONL row per source observation/evaluator pair.

- [ ] **Step 1: Write failing tests for extracting story/context from `fables_verify_all_claims` inputs.**
- [ ] **Step 2: Implement dry-run artifact generation and FABLES-only evaluation through `RagasEvaluator` with Langfuse disabled.**
- [ ] **Step 3: Run focused tests and a CLI dry-run over a fixture.**

### Task 3: Make evaluator role and routing configurable at runtime

**Files:**
- Modify: `src/providers/llm_factory.py`
- Modify: `src/settings.py`
- Modify: `src/workflows/story_agent/agents/critic/agent.py`
- Modify: `.env.example`
- Test: `tests/test_openrouter_benchmark.py`

**Interfaces:**
- `get_llm(..., openrouter_provider_preferences=dict | None)` attaches the exact provider object only for OpenRouter.
- `EvaluatorConfig` selects an optional evaluator provider/model without changing generation configuration.

- [ ] **Step 1: Write a failing test that asserts routing preferences reach the OpenRouter client configuration.**
- [ ] **Step 2: Implement evaluator role settings and explicit factory argument.**
- [ ] **Step 3: Run focused tests.**

### Task 4: Document and verify the safe free-model workflow

**Files:**
- Modify: `README.md`
- Modify: `docs/configuration.md`
- Modify: `requirements.txt`

- [ ] **Step 1: Document explicit model IDs, provider routing fields, preflight, artifact layout, and no-paid smoke test.**
- [ ] **Step 2: Run compile, focused pytest, and CLI `--help`.**
- [ ] **Step 3: If `OPENROUTER_API_KEY` is present, run preflight then a one-call free tool smoke test; otherwise record it as unverified.**
