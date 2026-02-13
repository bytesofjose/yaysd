import yt_dlp
import os
import shutil
import logging
from pathlib import Path
from .config import settings

# Setup logging
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

def get_metadata(info):
    """Extract artist and album from yt-dlp info or fallback."""
    artist = info.get('artist') or info.get('uploader') or "Unknown Artist"
    album = info.get('album') or "Singles"
    
    # Simple cleaning for path safety
    artist = "".join([c for c in artist if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
    album = "".join([c for c in album if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
    
    return artist, album

def download_audio(url: str):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '0',
            }, {
                'key': 'EmbedThumbnail',
            }, {
                'key': 'FFmpegMetadata',
            }],
            'writethumbnail': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'skip': ['dash', 'hls']
                }
            }
        }

        # Use cookies if the file exists and is a file (not a directory mount)
        if settings.COOKIES_FILE.is_file():
            logger.info(f"Using cookies from {settings.COOKIES_FILE}")
            ydl_opts['cookiefile'] = str(settings.COOKIES_FILE)
        else:
            logger.warning(f"No valid cookies.txt found at {settings.COOKIES_FILE} (or it is a directory). Bot detection might occur.")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Starting download for URL: {url}")
            info = ydl.extract_info(url, download=True)
            
            temp_file = Path(ydl.prepare_filename(info)).with_suffix('.mp3')
            artist, album = get_metadata(info)
            
            # Construct final path
            dest_dir = settings.BASE_MUSIC_PATH / artist / album
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            final_path = dest_dir / temp_file.name
            
            # Move file
            shutil.move(str(temp_file), str(final_path))
            
            logger.info(f"Successfully downloaded and moved to: {final_path}")
            return {
                "status": "success",
                "message": f"Descargada exitosamente en {final_path}",
                "path": str(final_path)
            }

    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return {
            "status": "error",
            "message": f"Ocurrió un error: {str(e)}"
        }
