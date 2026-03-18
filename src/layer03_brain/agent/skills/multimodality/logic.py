import asyncio

from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils.audio_tools import process_audio_for_llm
from src.layer00_utils.image_tools import compress_and_encode_image
from src.layer00_utils.config_manager import config

from src.layer03_brain.llm.multimodality import describe_image, transcribe_audio
from src.layer03_brain.agent.skills.auto_schema import llm_skill

@llm_skill(
    description="Транскрибирует локальный аудиофайл/голосовое сообщение из sandbox/ в текст. Использует внешнюю мультимодальную нейросеть.",
    parameters={"filepath": "VFS путь к аудиофайлу (например: 'sandbox/media/voice.ogg')"}
)
async def transcribe_local_file(filepath: str) -> str:
    try:
        target_path = workspace_manager.resolve_vfs_path(filepath, mode='read')
        if not target_path.exists() or not target_path.is_file():
            return f"Ошибка: Файл '{filepath}' не найден."
        
        b64_data = await asyncio.to_thread(process_audio_for_llm, str(target_path))
        transcription = await transcribe_audio(b64_data)
        return transcription
    except Exception as e:
        return f"Ошибка при транскрибации файла: {e}"

@llm_skill(
    description="Изучить медиафайл из sandbox/.",
    parameters={
        "filepath": "VFS путь к изображению (например: 'sandbox/media/photo.jpg')"
    }
)
async def read_local_media(filepath: str) -> str:
    try:
        target_path = workspace_manager.resolve_vfs_path(filepath, mode='read')
        if not target_path.exists() or not target_path.is_file():
            return f"Ошибка: Файл '{filepath}' не найден."
        
        # Если Мозг слепой -> используем подмодель и возвращаем текст
        if not config.llm.is_main_model_multimodal:
            b64_string = await asyncio.to_thread(compress_and_encode_image, str(target_path))
            description = await describe_image(b64_string)
            return description
        
        # Если главный мозг зрячий -> возвращаем магический системный тег с абсолютным путем
        return f"__MEDIA_INJECTION_REQUEST__:{str(target_path)}"
        
    except Exception as e:
        return f"Ошибка при обработке медиафайла: {e}"