import yt_dlp
from pathlib import Path

url = "https://www.youtube.com/watch?v=nJ29rE-RYVA"
output_dir = Path("i:/TuminhAgi/storage/datasets/youtube_corpus/_test")
output_dir.mkdir(parents=True, exist_ok=True)
output_template = str(output_dir / "%(id)s.%(ext)s")

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
        'preferredquality': '192',
    }],
    'outtmpl': output_template,
    # 'quiet': True, # Remove quiet to see errors
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print("Download success")
except Exception as e:
    import traceback
    traceback.print_exc()
