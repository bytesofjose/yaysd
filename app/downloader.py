import logging
import shutil
import threading
import time
import uuid
from pathlib import Path

import yt_dlp

from .config import settings

MAX_ITEMS = 100


def setup_logging():
    handlers = [logging.StreamHandler()]
    try:
        settings.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(settings.LOG_FILE))
        print(f"Logging to file: {settings.LOG_FILE}")
    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}. Falling back to console only.")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


setup_logging()
logger = logging.getLogger(__name__)

jobs = {}
jobs_lock = threading.Lock()


def _new_job(url):
    job_id = uuid.uuid4().hex[:12]
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "url": url,
            "status": "resolving",
            "total": 0,
            "done": 0,
            "failed": 0,
            "percent": 0,
            "stage": "resolviendo",
            "current_title": "",
            "items": [],
            "message": "",
            "created": time.time(),
        }
    return job_id


def _update(job_id, **fields):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(fields)


def _get(job_id):
    with jobs_lock:
        return dict(jobs.get(job_id, {}))


def get_metadata(info):
    artist = info.get('artist') or info.get('uploader') or "Unknown Artist"
    album = info.get('album') or "Singles"
    artist = "".join([c for c in artist if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
    album = "".join([c for c in album if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
    return artist or "Unknown Artist", album or "Singles"


def _base_opts(extra=None):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 20,
        'retries': 2,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['dash', 'hls']
            }
        },
    }
    if settings.COOKIES_FILE.is_file():
        opts['cookiefile'] = str(settings.COOKIES_FILE)
    if extra:
        opts.update(extra)
    return opts


def resolve_entries(url, limit=MAX_ITEMS):
    with yt_dlp.YoutubeDL(_base_opts({"extract_flat": True, "noplaylist": False})) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        return []
    entries = info.get("entries")
    if entries is None:
        return [{"id": info.get("id"), "title": info.get("title", url),
                 "url": info.get("webpage_url") or url}]
    out = []
    for e in entries:
        if not e:
            continue
        vid = e.get("id")
        if not vid:
            continue
        out.append({
            "id": vid,
            "title": e.get("title") or vid,
            "url": e.get("url") or f"https://www.youtube.com/watch?v={vid}",
        })
        if len(out) >= limit:
            break
    return out


def _download_one(entry_url, progress_cb):
    ydl_opts = _base_opts({
        'format': 'bestaudio/best',
        'outtmpl': '/tmp/%(title)s.%(ext)s',
        'noplaylist': True,
        'progress_hooks': [progress_cb],
    })
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(entry_url, download=True)
        temp_file = Path(ydl.prepare_filename(info))
        artist, album = get_metadata(info)
        dest_dir = settings.BASE_MUSIC_PATH / artist / album
        dest_dir.mkdir(parents=True, exist_ok=True)
        final_path = dest_dir / temp_file.name
        shutil.move(str(temp_file), str(final_path))
        return str(final_path), info.get("title", temp_file.stem)


def run_job(job_id, url):
    try:
        entries = resolve_entries(url)
    except Exception as e:
        logger.error(f"Job {job_id}: resolve failed for {url}: {e}")
        _update(job_id, status="error", message=f"No se pudo leer la URL: {e}")
        return
    if not entries:
        _update(job_id, status="error", message="No se encontraron videos en esa URL.")
        return
    _update(job_id, status="downloading", total=len(entries),
            items=[{"url": e["url"], "title": e["title"], "status": "pending"} for e in entries])
    ok, failed = 0, 0
    for i, entry in enumerate(entries):
        with jobs_lock:
            if jobs.get(job_id, {}).get("cancelled"):
                jobs[job_id]["status"] = "cancelled"
                jobs[job_id]["message"] = f"Cancelado ({ok}/{len(entries)} descargadas)."
                return
        _update(job_id, current_title=entry["title"], stage="descargando")

        def hook(d, _i=i, _n=len(entries)):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done_b = d.get("downloaded_bytes", 0)
                frac = (done_b / total) if total else 0
                _update(job_id, percent=round(((_i + min(frac, 1)) / _n) * 100, 1),
                        stage="descargando")
            elif d.get("status") == "finished":
                _update(job_id, stage="guardando en biblioteca")

        try:
            path, title = _download_one(entry["url"], hook)
            ok += 1
            logger.info(f"Job {job_id}: OK {path}")
        except Exception as e:
            failed += 1
            logger.error(f"Job {job_id}: FAIL {entry['url']}: {e}")
            title = entry["title"]
        with jobs_lock:
            job = jobs.get(job_id, {})
            items = job.get("items", [])
            if i < len(items):
                items[i] = {"url": entry["url"], "title": title,
                            "status": "ok" if title else "fail"}
            jobs[job_id]["items"] = items
            jobs[job_id]["done"] = ok + failed
            jobs[job_id]["failed"] = failed
            jobs[job_id]["percent"] = round(((ok + failed) / len(entries)) * 100, 1)
            jobs[job_id]["current_title"] = ""
    _update(job_id, status="done", percent=100, stage="listo",
            message=f"Listo: {ok} descargada(s)" + (f", {failed} fallaron" if failed else ""))


def start_job(url):
    job_id = _new_job(url)
    t = threading.Thread(target=run_job, args=(job_id, url), daemon=True)
    t.start()
    return job_id


def cancel_job(job_id):
    with jobs_lock:
        if job_id in jobs and jobs[job_id]["status"] in ("resolving", "downloading"):
            jobs[job_id]["cancelled"] = True
            return True
    return False


def download_audio(url: str):
    try:
        path, _ = _download_one(url, lambda d: None)
        logger.info(f"Successfully downloaded and moved to: {path}")
        return {
            "status": "success",
            "message": "Cancion descargada ✅",
            "path": path
        }
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return {
            "status": "error",
            "message": f"Ocurrió un error: {str(e)}"
        }
