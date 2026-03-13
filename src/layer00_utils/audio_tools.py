import base64
from pydub import AudioSegment
import io
from src.layer00_utils.logger import system_logger

def process_audio_for_llm(input_path: str) -> str:
    """Конвертирует любое аудио в MP3 (для уменьшения веса) и кодирует в Base64"""
    try:
        # Читаем файл (ogg, wav и т.д.)
        audio = AudioSegment.from_file(input_path)
        
        # Экспортируем в MP3 с небольшим битрейтом (для экономии токенов)
        buffer = io.BytesIO()
        audio.export(buffer, format="mp3", bitrate="64k")
        
        # Кодируем в Base64
        b64_string = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return b64_string
            
    except Exception as e:
        system_logger.error(f"[AudioTools] Ошибка обработки аудио: {e}")
        raise