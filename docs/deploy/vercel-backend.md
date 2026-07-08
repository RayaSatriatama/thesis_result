# Deploy Backend FastAPI ke Vercel

Dokumen ini menjelaskan cara deploy backend `src/apps/api/main.py` ke Vercel sebagai Python Serverless Function.

## Ringkasan

- Entrypoint Vercel ada di `api/index.py` (mengekspor variabel `app`).
- Semua request diarahkan ke function tersebut melalui `vercel.json`.
- Endpoint utama:
  - `GET /health`
  - `POST /api/interactive/chat` (SSE)
 - Pada serverless (Vercel), warmup workflow saat startup dinonaktifkan untuk mencegah crash cold-start.

## Keterbatasan penting (SSE)

Endpoint `POST /api/interactive/chat` memakai SSE. Pada platform serverless, streaming dan koneksi panjang bisa terputus karena batas waktu dan limit koneksi.

Jika SSE sering putus:

- Kurangi durasi proses (lebih sedikit langkah agen, output lebih ringkas).
- Pertimbangkan fallback non-stream (polling) khusus untuk deployment serverless.

## Environment Variables di Vercel

Set di Vercel Project Settings:

- `API_KEY`: kunci untuk header `X-API-Key` dari client.
- `ALLOWED_ORIGINS`: origin frontend (comma-separated). Contoh: `https://kabiru-website.vercel.app`
- `LLM_PROVIDER`: contoh `openrouter` atau `google_genai`.
- Sesuai provider:
  - `OPENROUTER_API_KEY` (jika `LLM_PROVIDER=openrouter`)
  - `GEMINI_API_KEY` (jika `LLM_PROVIDER=google_genai`)
  - Lainnya sesuai `.env.example`

Nonaktifkan LightRAG server (tanpa deploy LightRAG):

- `LIGHTRAG_API_URL` kosong
- `LIGHTRAG_API_KEY` kosong

## Langkah Deploy (Dashboard Vercel)

1. Import repository ke Vercel.
2. Framework preset: pilih "Other".
3. Pastikan Vercel mendeteksi `vercel.json`.
4. Ubah **Install Command** menjadi:

   - `uv pip install -r requirements.vercel.txt`

   Ini diperlukan agar bundle tidak melewati batas storage serverless Vercel.
5. Tambahkan environment variables.
6. Deploy.

## Verifikasi

- `GET https://<project>.vercel.app/health`
- Pastikan client memanggil `X-API-Key` yang sesuai.

