# OpenRouter Evaluator Benchmark Specification

## Goal

Enable reproducible comparison of OpenRouter evaluator models against frozen
Gemini 2.5 Flash story outputs without mutating Langfuse or the source exports.

## Requirements

- Generation and evaluator models are independent, explicit roles.
- A benchmark run receives every model, routing, temperature, and metric choice
  from a JSON configuration file. API keys remain environment variables.
- OpenRouter routing preferences use the official `provider` request object.
- The runner rejects a model before inference when it is not listed as free when
  `require_free` is enabled, or when required capabilities are absent.
- FABLES replay reads story and contexts from exported observations, writes new
  JSONL artifacts, and never writes to Langfuse or the source export directory.
- Each result records model metadata, requested capabilities, routing settings,
  config digest, source observation id, and a clear success or failure status.
- Runtime Critic configuration can select a separate evaluator provider/model
  while preserving existing generation settings when no evaluator role is set.
- No paid request may be issued by the smoke-test command. It only permits a
  model passing the live free-price preflight.

## Non-goals

- Replacing historical Langfuse observations.
- Routing through `openrouter/free`, which is non-deterministic.
- Installing DeepEval automatically. G-Eval remains an optional metric until its
  dependency is explicitly installed.

## Acceptance evidence

- Unit tests cover config validation, free/capability preflight, and frozen
  observation extraction.
- A dry run produces a manifest without network inference.
- A live smoke test, when credentials and a qualifying current free model exist,
  performs a tool-call round trip only after the same capability and price check.
