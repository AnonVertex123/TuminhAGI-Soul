# i:\TuminhAgi\scripts\youtube_pipeline.py
"""
TuminhAGI — YouTube Audio-to-Dataset Pipeline
================================================
Automated pipeline to download YouTube audio, transcribe with Whisper,
and export as JSONL datasets for LLM training.

Author: Antigravity AI
Stack: yt-dlp, faster-whisper, rich, concurrent.futures
"""

import os
import re
import json
import logging
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import yt_dlp
from faster_whisper import WhisperModel
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn

# Configuration
STORAGE_ROOT = Path("I:/TuminhAgi/storage/datasets/youtube_corpus")
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(STORAGE_ROOT / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("YoutubePipeline")
console = Console()

class AudioDownloader:
    """Handles YouTube audio extraction using yt-dlp."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def get_info(self, url: str) -> Optional[Dict]:
        """Fetches metadata for a single video OR a playlist."""
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',  # Get titles without downloading
            'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"Failed to fetch info for {url}: {e}")
            return None

    def download_audio(self, video_url: str) -> Optional[Path]:
        """Downloads a single video's audio and returns its Path."""
        # Use a sanitized template for filenames to prevent invalid chars
        output_template = str(self.output_dir / "%(id)s.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192',
            }],
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                # yt-dlp might change extension after post-processing
                final_path = self.output_dir / f"{info['id']}.m4a"
                if final_path.exists():
                    return final_path
                return None
        except Exception as e:
            logger.error(f"Error downloading {video_url}: {e}")
            return None

class TranscriptionEngine:
    """Handles speech-to-text using faster-whisper."""
    
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        """
        model_size: 'tiny', 'base', 'small', 'medium', 'large-v3'
        device: 'cpu' or 'cuda'
        """
        logger.info(f"Loading Whisper model: {model_size} on {device}")
        # Setting compute_type to float16 for GPU performance, int8 for CPU efficiency
        compute_type = "float16" if device == "cuda" else "int8"
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio_path: Path) -> str:
        """Transcribes audio file to text with VAD (Voice Activity Detection)."""
        logger.info(f"Transcribing: {audio_path.name}")
        
        # vad_filter=True implements Voice Activity Detection to skip silences
        segments, info = self.model.transcribe(
            str(audio_path),
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            word_timestamps=True  # Accuracy for future fine-grained use
        )
        
        full_text = []
        for segment in segments:
            full_text.append(segment.text)
            
        return " ".join(full_text)

class TextPreprocessor:
    """Cleans and chunks transcribed text."""
    
    @staticmethod
    def clean(text: str) -> str:
        # Remove multiple spaces/newlines
        text = re.sub(r'\s+', ' ', text)
        # Remove common "filler" words if detected in transcription (basic regex)
        text = re.sub(r'\b(um|uh|hmm|ah|eh)\b', '', text, flags=re.IGNORECASE)
        return text.strip()

    @staticmethod
    def chunk_text(text: str, max_words: int = 500) -> List[str]:
        words = text.split()
        return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]

class YouTubePipeline:
    """Orchestrates the download, transcription, and export process."""
    
    def __init__(self, whisper_model: str = "base"):
        self.downloader = AudioDownloader(STORAGE_ROOT / "_temp_audio")
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.transcriber = TranscriptionEngine(model_size=whisper_model, device=device)
        self.processor = TextPreprocessor()
        self.dataset_file = STORAGE_ROOT / f"youtube_corpus_{datetime.now().strftime('%Y%m%d')}.jsonl"
        self.txt_dir = STORAGE_ROOT / "txt"
        self.txt_dir.mkdir(parents=True, exist_ok=True)

    def process_video(self, video_info: Dict) -> Optional[Dict]:
        """Wrapper for parallel execution of single-video unit."""
        video_id = video_info.get('id')
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Download
        audio_path = self.downloader.download_audio(video_url)
        if not audio_path:
            return None
            
        try:
            # Transcribe
            raw_text = self.transcriber.transcribe(audio_path)
            clean_text = self.processor.clean(raw_text)
            
            # Save separate TXT file with Title and Date
            sanitized_title = re.sub(r'[\\/*?:"<>|]', "", video_info.get('title', 'Unknown'))
            date_str = datetime.now().strftime('%Y%m%d')
            txt_filename = f"{date_str}_{sanitized_title[:50]}.txt"
            txt_path = self.txt_dir / txt_filename
            
            with open(txt_path, "w", encoding="utf-8") as tf:
                tf.write(f"TITLE: {video_info.get('title', 'Unknown')}\n")
                tf.write(f"URL: {video_url}\n")
                tf.write(f"DOWNLOADED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                tf.write("-" * 50 + "\n")
                if clean_text:
                    tf.write(clean_text)
                else:
                    tf.write("[Transcription was empty]")
            
            console.print(f"[green]✓ Transcription saved to:[/green] [white]{txt_filename}[/white]")
            
            # Record
            result = {
                "video_id": video_id,
                "title": video_info.get('title', 'Unknown'),
                "url": video_url,
                "text": clean_text,
                "timestamp": datetime.now().isoformat()
            }
            
            # Cleanup audio to save space
            if audio_path.exists():
                os.remove(audio_path)
                
            return result
        except Exception as e:
            logger.error(f"Failed to process video {video_id}: {e}")
            if audio_path and audio_path.exists():
                os.remove(audio_path)
            return None

    def run(self, input_url: str, max_workers: int = 4):
        """Main execution loop supporting individual videos or playlists."""
        info = self.downloader.get_info(input_url)
        if not info:
            console.print("[red]❌ Could not retrieve YouTube content info.[/red]")
            return

        entries = info.get('entries', [info]) if 'entries' in info else [info]
        total = len(entries)
        console.print(f"🚀 Found {total} video(s). Starting pipeline...")

        success_count = 0
        with open(self.dataset_file, "a", encoding="utf-8") as f:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # We mainly download in parallel, but transcription is heavy 
                # (Whisper usually handles its own threading/CUDA)
                future_to_video = {executor.submit(self.process_video, entry): entry for entry in entries}
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                ) as progress:
                    task = progress.add_task("[cyan]Processing YouTube data...", total=total)
                    
                    for future in concurrent.futures.as_completed(future_to_video):
                        res = future.result()
                        if res:
                            f.write(json.dumps(res, ensure_ascii=False) + "\n")
                            success_count += 1
                        progress.update(task, advance=1)

        console.print(f"\n✨ [bold green]Done![/bold green] Collected [yellow]{success_count}/{total}[/yellow] records.")
        console.print(f"📂 Dataset saved at: [bold]{self.dataset_file}[/bold]")

def main():
    """Command-line entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="TuminhAGI: YT to LLM Dataset")
    parser.add_argument("url", help="YouTube video or playlist URL")
    parser.add_argument("--model", default="base", help="Whisper model size (tiny, base, small, medium, large-v3)")
    parser.add_argument("--workers", type=int, default=1, help="Number of concurrent downloads/processes")
    args = parser.parse_args()

    pipeline = YouTubePipeline(whisper_model=args.model)
    pipeline.run(args.url, max_workers=args.workers)

if __name__ == "__main__":
    main()
