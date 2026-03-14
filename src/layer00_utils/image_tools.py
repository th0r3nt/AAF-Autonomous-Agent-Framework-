import base64
import io
from PIL import Image
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger

def compress_and_encode_image(image_path: str) -> str:
    """Сжимает изображение и кодирует его в Base64 для передачи в LLM"""
    max_size = config.llm.limits.image_max_size
    try:
        with Image.open(image_path) as img:
            # Конвертируем в RGB (если это PNG с прозрачностью)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Сжимаем с сохранением пропорций
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Сохраняем в буфер оперативной памяти
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            
            # Кодируем в Base64
            b64_string = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return b64_string
            
    except Exception as e:
        system_logger.error(f"[ImageTools] Ошибка обработки изображения: {e}")
        raise