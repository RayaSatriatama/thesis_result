# Story Studio (fork UI Claw3D → Story Agent API)

## Ringkasan

Folder [`story-agent-ui/story-studio`](../story-agent-ui/story-studio) adalah salinan kerja Claw3D yang diarahkan ke backend **Story Agent** (FastAPI) tanpa menjalankan **OpenClaw Gateway**.

## Menjalankan

1. **API Python** — dari root proyek Skripsi, set `API_KEY` di environment, lalu jalankan `src/apps/api/main.py` (biasanya port `8000`).
2. **Story Studio** — di `story-agent-ui/story-studio`:

   - Salin `.env.example` → `.env`.
   - Set minimal:
     - `NEXT_PUBLIC_STUDIO_RUNTIME=skripsi`
     - `STUDIO_RUNTIME=skripsi`
     - `STORY_API_URL=http://127.0.0.1:8000`
     - `STORY_API_KEY=<sama dengan API_KEY FastAPI>`
   - `npm install` lalu `npm run dev`.

3. **CORS** — jika browser memanggil API langsung, tambahkan origin Next ke `ALLOWED_ORIGINS` di FastAPI. Mode default memakai proxy same-origin `/api/story/*` sehingga CORS ke UI tidak wajib.

## Endpoint FastAPI tambahan

- `GET /api/meta/studio-agents` — daftar agen untuk hidrasi UI (bentuk kompatibel `agents.list`).
- `GET /api/meta/npcs` — daftar NPC (debug).

Keduanya memakai header `X-API-Key` seperti router lain.

## Dokumentasi teknis di dalam fork

Lihat [`STORY_RPC_MATRIX.md`](../story-agent-ui/story-studio/STORY_RPC_MATRIX.md) dan [`ATTRIBUTION.md`](../story-agent-ui/story-studio/ATTRIBUTION.md).
