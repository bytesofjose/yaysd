# Guardarol

LAN-only YouTube audio library app. Paste a video, playlist or channel URL and
tracks land in the music library as `Artist/Album/*` in the **original source
format** (`bestaudio` as served — typically `.m4a` or `.opus`, no re-encode, no
quality lost to transcoding). Same layout Navidrome and the
`song-recommender` ⬇ button already consume.

Live: `http://192.168.1.94:8000` (container `youtube_mp3_downloader`).

## Features

- Single videos, playlists (`list=…`) and channels (`@handle`, `/channel/`,
  `/c/`, `/user/`, `/…/videos` tab) — channels resolve to recent uploads
  (capped at 100 items per job).
- Blocking loading orb: fullscreen overlay blurs and locks the page while a
  job runs, with a real progress ring + bar driven by yt-dlp byte progress,
  `done/total` counter, current title and stage (downloading → converting).
  Cancel button stops the queue.
- Async jobs: `POST /download` returns a `job_id` immediately;
  `GET /api/job/{id}` polls progress. `POST /download?sync=1` keeps the old
  blocking single-file behaviour (used by song-recommender's ⬇ button).
- `GET /api/health` for deploy healthchecks.

## Run

```bash
cp .env.example .env
docker compose up -d --build
```

## UI

Tailwind CSS v3, vendored locally (`app/static/tailwind.css`, offline-safe —
no CDN). Source: `app/static/input.css` + `tailwind.config.js` (Dracula
palette). Rebuild after changing classes:

```bash
npm install
npx tailwindcss -c ./tailwind.config.js -i ./app/static/input.css -o ./app/static/tailwind.css --minify
```

## Deploy

Push to `main` → Forgejo pipeline (`joe/guardarol`) syncs code to the
homelab service dir, rebuilds and healthchecks. Container name
`youtube_mp3_downloader` is kept stable: `song-recommender` reaches it at
`http://youtube_mp3_downloader:8000`.
