import os
import sys
import json
import pyaudio
from vosk import Model, KaldiRecognizer
from pathlib import Path
import zipfile
import urllib.request

# Thêm đường dẫn gốc
sys.path.append(str(Path(__file__).parent.parent.parent))

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-vn-0.4.zip"
MODEL_PATH = Path("storage/models/vosk-vn")

class EarEngine:
    def __init__(self):
        if not MODEL_PATH.exists() or not any(MODEL_PATH.iterdir()):
            self._download_model()
        
        try:
            self.model = Model(str(MODEL_PATH))
            self.recognizer = KaldiRecognizer(self.model, 16000)
            self.mic = pyaudio.PyAudio()
        except Exception as e:
            print(f"❌ Lỗi khởi tạo thính giác: {e}")
            self.model = None

    def _download_model(self):
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
        
        print(f"📥 Đang chuẩn bị tải mô hình thính giác Vietnamese (Offline)...")
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        zip_path = MODEL_PATH.parent / "vosk_vn.zip"
        
        # Xóa file cũ nếu bị kẹt
        if zip_path.exists():
            os.remove(zip_path)

        try:
            with Progress(
                TextColumn("[bold blue]{task.description}", justify="right"),
                BarColumn(bar_width=40),
                "[progress.percentage]{task.percentage:>3.1f}%",
                "•",
                DownloadColumn(),
                "•",
                TransferSpeedColumn(),
                "•",
                TimeRemainingColumn(),
            ) as progress:
                
                task_id = progress.add_task("Đang tải Vosk Model", total=None)
                
                def reporthook(blocknum, blocksize, totalsize):
                    if progress.tasks[task_id].total is None and totalsize > 0:
                        progress.update(task_id, total=totalsize)
                    progress.update(task_id, completed=blocknum * blocksize)

                urllib.request.urlretrieve(MODEL_URL, zip_path, reporthook)

            print(f"📦 Đang giải nén mô hình...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(MODEL_PATH.parent)
            
            # Tìm thư mục vừa giải nén và đổi tên
            extracted_dir = next(MODEL_PATH.parent.glob("vosk-model-small-vn-*"))
            if MODEL_PATH.exists():
                import shutil
                shutil.rmtree(MODEL_PATH)
            extracted_dir.rename(MODEL_PATH)
            os.remove(zip_path)
            print(f"✅ Đã cài đặt xong mô hình thính giác tại {MODEL_PATH}")
        except Exception as e:
            print(f"❌ Lỗi tải mô hình: {e}")
            if zip_path.exists(): os.remove(zip_path)

    def listen(self, timeout=10):
        """Lắng nghe và chuyển thành văn bản."""
        if not self.model: return ""

        stream = self.mic.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8192)
        stream.start_stream()
        
        print("\n👂 [Tự Minh]: Đang lắng nghe...")
        
        start_time = os.times().elapsed
        try:
            while True:
                data = stream.read(4000, exception_on_overflow=False)
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        stream.stop_stream()
                        return text
                
                # Tránh treo nếu không nghe thấy gì
                if timeout and (os.times().elapsed - start_time > timeout):
                    break
        except Exception as e:
            print(f"⚠️ Lỗi Microphone: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            
        return ""

# Singleton instance
tuminh_ear = EarEngine()

if __name__ == "__main__":
    text = tuminh_ear.listen()
    if text:
        print(f"✨ Tự Minh nghe thấy: {text}")
    else:
        print("... Không nghe rõ.")
