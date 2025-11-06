"""Test yt-dlp with YouTube Shorts URL"""
from yt_dlp import YoutubeDL
import tempfile
from pathlib import Path

url = "https://www.youtube.com/watch?v=-2DvWn6wUFc"
print(f"Testing URL: {url}")

ydl_opts = {
    "format": "best[ext=mp4]/best",
    "outtmpl": str(Path(tempfile.gettempdir()) / "test_video.%(ext)s"),
    "quiet": False,
    "no_warnings": False,
}

try:
    with YoutubeDL(ydl_opts) as ydl:
        print("Extracting info...")
        info = ydl.extract_info(url, download=False)
        print(f"Title: {info.get('title')}")
        print(f"Duration: {info.get('duration')}s")
        print("Video info extracted successfully!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()




