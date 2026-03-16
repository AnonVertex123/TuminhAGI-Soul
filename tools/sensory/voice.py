import asyncio
import edge_tts
import pygame
import os
import sys
from pathlib import Path

# Thêm đường dẫn gốc để import config nếu cần
sys.path.append(str(Path(__file__).parent.parent.parent))

# Cấu hình giọng nói
# vi-VN-NamMinhNeural: Giọng nam trầm, đĩnh đạc, phù hợp với "Tự Minh"
# vi-VN-HoaiMyNeural: Giọng nữ mượt mà
VOICE = "vi-VN-NamMinhNeural"
STORAGE_DIR = Path("storage/audio")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

class VoiceEngine:
    def __init__(self, voice=VOICE):
        self.voice = voice
        self.output_file = STORAGE_DIR / "speech.mp3"
        pygame.mixer.init()

    async def _generate_audio(self, text: str):
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(str(self.output_file))

    def _play_audio(self):
        try:
            pygame.mixer.music.load(str(self.output_file))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            print(f"❌ Lỗi phát âm thanh: {e}")

    def speak(self, text: str):
        """Hàm đồng bộ để gọi từ main orchestrator."""
        if not text: return
        
        # Xóa file cũ nếu đang bị lock
        try:
            if self.output_file.exists():
                pygame.mixer.music.unload()
                # Thử xóa nhưng không crash nếu thất bại
                # os.remove(self.output_file) 
        except:
            pass

        asyncio.run(self._generate_audio(text))
        self._play_audio()

# Singleton instance
tuminh_voice = VoiceEngine()

if __name__ == "__main__":
    tuminh_voice.speak("Chào Hùng Đại, Tự Minh đã sẵn sàng cất tiếng nói phục vụ anh.")
