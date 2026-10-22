import logging
import shutil
import threading
import time
import uuid
from pathlib import Path

import json as _json

import yt_dlp

from .config import settings

MAX_ITEMS = 100
HISTORY_LIMIT = 200


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
            "finished": None,
            "skipped": 0,
        }
    return job_id


def _update(job_id, **fields):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(fields)


def _finish(job_id, status, message, **extra):
    fields = {"status": status, "message": message, "finished": time.time()}
    fields.update(extra)
    _update(job_id, **fields)
    _save_history(job_id)
    _clear_snapshot(job_id)


def _save_history(job_id):
    try:
        with jobs_lock:
            job = dict(jobs.get(job_id, {}))
        if not job:
            return
        record = {
            "id": job["id"],
            "url": job["url"],
            "status": job["status"],
            "total": job.get("total", 0),
            "ok": job.get("total", 0) - job.get("failed", 0) if job.get("status") == "done" else job.get("done", 0),
            "failed": job.get("failed", 0),
            "skipped": job.get("skipped", 0),
            "message": job.get("message", ""),
            "created": job.get("created"),
            "finished": job.get("finished"),
            "items": [{"title": it.get("title", ""), "status": it.get("status", "")}
                      for it in job.get("items", [])],
        }
        settings.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(settings.HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(_json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Job {job_id}: could not save history: {e}")


def read_history(limit=50):
    try:
        lines = settings.HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines()
    except (OSError, FileNotFoundError):
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(_json.loads(line))
        except Exception:
            continue
    return list(reversed(out))


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
    """Returns (path, title, skipped). Skips when the file already exists."""
    ydl_opts = _base_opts({
        'format': 'bestaudio/best',
        'outtmpl': '/tmp/%(title)s.%(ext)s',
        'noplaylist': True,
        'progress_hooks': [progress_cb],
    })
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        meta = ydl.extract_info(entry_url, download=False)
        if meta is None:
            raise RuntimeError("sin metadata")
        temp_name = Path(ydl.prepare_filename(meta)).name
        artist, album = get_metadata(meta)
        dest_dir = settings.BASE_MUSIC_PATH / artist / album
        existing = dest_dir / temp_name
        if existing.is_file():
            logger.info(f"SKIP exists: {existing}")
            return str(existing), meta.get("title", temp_name), True
        info = ydl.extract_info(entry_url, download=True)
        temp_file = Path(ydl.prepare_filename(info))
        artist, album = get_metadata(info)
        dest_dir = settings.BASE_MUSIC_PATH / artist / album
        dest_dir.mkdir(parents=True, exist_ok=True)
        final_path = dest_dir / temp_file.name
        shutil.move(str(temp_file), str(final_path))
        return str(final_path), info.get("title", temp_file.stem), False


def _snapshot(job_id):
    try:
        with jobs_lock:
            job = dict(jobs.get(job_id, {}))
        if not job or not job.get("items"):
            return
        settings.STATE_DIR.mkdir(parents=True, exist_ok=True)
        snap = {
            "url": job.get("url", ""),
            "items": [{"url": it.get("url", ""), "title": it.get("title", ""),
                       "status": it.get("status", "pending")} for it in job["items"]],
            "created": job.get("created"),
        }
        (settings.STATE_DIR / f"{job_id}.json").write_text(
            _json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"Job {job_id}: could not snapshot: {e}")


def _clear_snapshot(job_id):
    try:
        (settings.STATE_DIR / f"{job_id}.json").unlink(missing_ok=True)
    except OSError:
        pass


def _process(job_id):
    with jobs_lock:
        job = jobs.get(job_id, {})
        items = [dict(it) for it in job.get("items", [])]
        total = len(items)
    ok = sum(1 for it in items if it.get("status") == "ok")
    failed = sum(1 for it in items if it.get("status") == "fail")
    skipped = sum(1 for it in items if it.get("status") == "skipped")
    for i, entry in enumerate(items):
        if entry.get("status") != "pending":
            continue
        with jobs_lock:
            cancelled = jobs.get(job_id, {}).get("cancelled")
        if cancelled:
            _finish(job_id, "cancelled", f"Cancelado ({ok + skipped}/{total} en biblioteca.)",
                    done=ok + failed + skipped, failed=failed, skipped=skipped)
            return
        _update(job_id, current_title=entry.get("title", ""), stage="descargando")

        def hook(d, _i=i, _n=total):
            if d.get("status") == "downloading":
                total_b = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done_b = d.get("downloaded_bytes", 0)
                frac = (done_b / total_b) if total_b else 0
                _update(job_id, percent=round(((_i + min(frac, 1)) / _n) * 100, 1),
                        stage="descargando")
            elif d.get("status") == "finished":
                _update(job_id, stage="guardando en biblioteca")

        item_ok = True
        item_skipped = False
        try:
            path, title, item_skipped = _download_one(entry["url"], hook)
            if item_skipped:
                skipped += 1
            else:
                ok += 1
            logger.info(f"Job {job_id}: {'SKIP' if item_skipped else 'OK'} {path}")
        except Exception as e:
            failed += 1
            item_ok = False
            logger.error(f"Job {job_id}: FAIL {entry['url']}: {e}")
            title = entry.get("title", entry["url"])
        with jobs_lock:
            job = jobs.get(job_id, {})
            job_items = job.get("items", [])
            if i < len(job_items):
                job_items[i] = {"url": entry["url"], "title": title,
                                "status": "fail" if not item_ok else ("skipped" if item_skipped else "ok")}
            jobs[job_id]["items"] = job_items
            jobs[job_id]["done"] = ok + failed + skipped
            jobs[job_id]["failed"] = failed
            jobs[job_id]["skipped"] = skipped
            jobs[job_id]["percent"] = round(((ok + failed + skipped) / total) * 100, 1) if total else 100
            jobs[job_id]["current_title"] = ""
        _snapshot(job_id)
    parts = f"Listo: {ok} descargada(s)"
    if skipped:
        parts += f", {skipped} ya estaban"
    if failed:
        parts += f", {failed} fallaron"
    _finish(job_id, "done", parts, percent=100, stage="listo")


def run_job(job_id, url):
    try:
        entries = resolve_entries(url)
    except Exception as e:
        logger.error(f"Job {job_id}: resolve failed for {url}: {e}")
        _finish(job_id, "error", f"No se pudo leer la URL: {e}")
        return
    if not entries:
        _finish(job_id, "error", "No se encontraron videos en esa URL.")
        return
    _update(job_id, status="downloading", total=len(entries),
            items=[{"url": e["url"], "title": e["title"], "status": "pending"} for e in entries])
    _snapshot(job_id)
    _process(job_id)


def resume_interrupted():
    try:
        files = sorted(settings.STATE_DIR.glob("*.json"))
    except OSError:
        return 0
    resumed = 0
    for f in files:
        try:
            snap = _json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = snap.get("items", [])
        pending = sum(1 for it in items if it.get("status") == "pending")
        if not pending:
            try:
                f.unlink()
            except OSError:
                pass
            continue
        job_id = _new_job(snap.get("url", ""))
        _update(job_id, status="downloading", total=len(items),
                items=[{"url": it.get("url", ""), "title": it.get("title", ""),
                        "status": it.get("status", "pending")} for it in items],
                done=sum(1 for it in items if it.get("status") in ("ok", "skipped")),
                failed=sum(1 for it in items if it.get("status") == "fail"),
                skipped=sum(1 for it in items if it.get("status") == "skipped"),
                message=f"Reanudado tras reinicio ({pending} pendientes).")
        t = threading.Thread(target=_process, args=(job_id,), daemon=True)
        t.start()
        resumed += 1
        logger.info(f"Resumed job {job_id} with {pending} pending items from {f.name}")
        try:
            f.unlink()
        except OSError:
            pass
    return resumed


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
        path, _, _ = _download_one(url, lambda d: None)
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
