"""One-shot backfill (2026-10-22): tag + cover + per-song folders for the 185
pre-existing Mik4000 files (no tags/art, shared Singles/Single EP folders).

Runs INSIDE the guardarol container (has yt-dlp + ffmpeg):
  docker cp backfill-tags.py youtube_mp3_downloader:/tmp/backfill-tags.py
  docker exec -d youtube_mp3_downloader python3 /tmp/backfill-tags.py
Log: /app/logs/backfill.log (mounted host volume).
"""
import subprocess
import sys
import urllib.request
from pathlib import Path

MUSIC = Path("/mnt/data_pool/music/Mik4000")
LOG = Path("/app/logs/backfill.log")
CHANNEL = "https://www.youtube.com/@miks4000/videos"


def log(msg):
    line = f"{msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def clean(s):
    return "".join([c for c in (s or "") if c.isalnum() or c in (' ', '.', '_', '-')]).strip()


def norm(s):
    return "".join([c for c in (s or "").lower() if c.isalnum()])


def existing_artist(name):
    want = norm(name)
    for d in MUSIC.iterdir():
        if d.is_dir() and norm(d.name) == want:
            return d.name
    return clean(name) or "Mik4000"


def channel_map():
    r = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--no-warnings",
         "--print", "%(id)s\t%(title)s\t%(webpage_url)s\t%(uploader)s\t%(thumbnail)s",
         CHANNEL],
        capture_output=True, text=True, timeout=600)
    entries = {}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or not parts[1]:
            continue
        vid, title = parts[0], parts[1]
        url = parts[2] or f"https://www.youtube.com/watch?v={vid}"
        uploader = parts[3] if len(parts) > 3 else ""
        thumb = parts[4] if len(parts) > 4 else ""
        entries[norm(title)] = (title, url, uploader, thumb)
    return entries


def fetch_thumb(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest.is_file() and dest.stat().st_size > 0


def has_title_tag(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=title",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    return bool(r.stdout.strip())


def process(src, title, artist, album, thumb_url, keep_ext):
    dest_dir = MUSIC / artist / album
    dest_dir.mkdir(parents=True, exist_ok=True)
    final_name = src.stem + (".mp3" if keep_ext == "mp3" else ".m4a")
    if keep_ext == "mp3" and has_title_tag(src):
        dst = dest_dir / src.name
        if dst != src:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
        return f"MOVED {dst}"
    tmp_thumb = src.with_suffix(".thumb.jpg")
    tmp_out = src.with_suffix(".tagged" + (".mp3" if keep_ext == "mp3" else ".m4a"))
    thumb_ok = False
    if thumb_url:
        try:
            thumb_ok = fetch_thumb(thumb_url, tmp_thumb)
        except Exception as e:
            log(f"  thumb fail: {e}")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src)]
    if thumb_ok:
        cmd += ["-i", str(tmp_thumb), "-map", "0:a:0", "-map", "1:v:0",
                "-c", "copy", "-c:v:0", "mjpeg",
                "-disposition:v:0", "attached_pic"]
    else:
        cmd += ["-map", "0:a:0", "-c", "copy"]
    cmd += ["-metadata", f"title={title}",
            "-metadata", f"artist={artist}",
            "-metadata", f"album={album}", str(tmp_out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    tmp_thumb.unlink(missing_ok=True)
    if r.returncode != 0 or not tmp_out.is_file():
        tmp_out.unlink(missing_ok=True)
        raise RuntimeError((r.stderr or "").strip()[:200])
    dst = dest_dir / final_name
    if tmp_out != dst:
        tmp_out.rename(dst)
    src.unlink(missing_ok=True)
    return f"OK {dst}"


def main():
    log("== backfill start ==")
    cmap = channel_map()
    log(f"channel entries: {len(cmap)}")
    files = sorted(MUSIC.rglob("*.m4a")) + sorted(MUSIC.rglob("*.mp3"))
    log(f"files found: {len(files)}")
    ok = fail = skip = 0
    for src in files:
        if src.suffix == ".tagged.m4a" or ".tagged" in src.suffixes:
            continue
        stem = src.stem
        hit = cmap.get(norm(stem))
        if not hit:
            log(f"SKIP no channel match: {stem[:60]}")
            skip += 1
            continue
        title, url, uploader, thumb = hit
        artist = existing_artist(uploader or "Mik4000")
        album = clean(title)[:100] or "Single EP"
        if (MUSIC / artist / album / (src.stem + src.suffix)).is_file():
            skip += 1
            continue
        try:
            kind = "mp3" if src.suffix == ".mp3" else "m4a"
            log(process(src, title, artist, album, thumb, kind))
            ok += 1
        except Exception as e:
            log(f"FAIL {stem[:60]}: {e}")
            fail += 1
    log(f"== backfill done ok={ok} fail={fail} skip={skip} ==")


if __name__ == "__main__":
    main()
