# WikiEval benchmark

Benchmark WikiEval memakai 50 item dalam dua bahasa (`id` dan `en`). Satu
model menghasilkan 100 cerita. Jalankan setiap model dengan direktori output
berbeda agar checkpoint, metadata, dan skor tidak bercampur.

## Agentic API

`scripts/run_wikieval_api_benchmark.py` memanggil `POST /api/workflow/generate`
dan menyimpan SSE, `job_id`, `trace_id`, cerita final, skor internal, serta
referensi WikiEval ke `results.jsonl` dan `results.json`.

Provider ditentukan oleh environment proses API. `--model` dikirim pada setiap
request. Untuk OpenRouter, pin provider dan parameter provider pada environment
server, sesuai konfigurasi OpenRouter yang dipakai server.

Smoke test satu cerita per model:

```bash
python scripts/run_wikieval_api_benchmark.py \
  --model openai/gpt-4o-mini --provider openrouter \
  --languages id --limit 1 \
  --out output/wikieval/agentic-gpt4o-mini-smoke

python scripts/run_wikieval_api_benchmark.py \
  --model google/gemini-2.5-flash --provider openrouter \
  --languages id --limit 1 \
  --out output/wikieval/agentic-gemini-25-flash-smoke
```

Batch penuh, 100 cerita per model, hanya dijalankan setelah smoke test:

```bash
python scripts/run_wikieval_api_benchmark.py --model openai/gpt-4o-mini --out output/wikieval/agentic-gpt4o-mini
python scripts/run_wikieval_api_benchmark.py --model google/gemini-2.5-flash --out output/wikieval/agentic-gemini-25-flash
```

## Baseline LLM-only

`baseline/run_baseline.py` memakai konteks WikiEval `context_v1 + context_v2`
yang dideduplikasi, satu panggilan generator, lalu CriticAgent untuk evaluasi.
Model generator dan evaluator dapat dipisahkan melalui opsi CLI. `--language
id --limit 1` menghasilkan tepat satu cerita.

```bash
python baseline/run_baseline.py \
  --model openai/gpt-4o-mini --provider openrouter \
  --language id --limit 1 \
  --out output/wikieval/baseline-gpt4o-mini-smoke

python baseline/run_baseline.py \
  --model google/gemini-2.5-flash --provider openrouter \
  --language id --limit 1 \
  --out output/wikieval/baseline-gemini-25-flash-smoke
```

Tanpa `--language`, baseline menjalankan 100 cerita per model. Setiap output
menyimpan model generator dan evaluator di metadata serta tag Langfuse.

## Evaluator eksternal

Kedua runner menjalankan gate evaluator eksternal sebelum checkpoint sebuah
cerita dianggap selesai. Konfigurasinya adalah
`configs/external_evaluators_3_models.json`: GPT-4o-mini melalui OpenAI,
Gemini 2.5 Flash melalui Google AI Studio, dan DeepSeek V4.1 Flash melalui
DeepInfra. Setiap model menjalankan G-Eval, FABLES, dan RAGAS secara paralel.
Hasilnya menjadi node model terpisah di bawah trace cerita sumber yang sama,
sehingga skor tidak bertumpuk dan checkpoint tanpa sembilan hasil tersebut
akan dicoba ulang saat runner diteruskan.

## LightRAG dan web search

`LIGHTRAG_INGEST_ENABLED=false` menjadi default. Workflow masih boleh melakukan
retrieval, tetapi tidak menulis sumber baru ke knowledge base bersama. Set ke
`true` hanya untuk eksperimen ingestion yang disengaja. Konfigurasi web search
tidak diubah pada benchmark ini.
