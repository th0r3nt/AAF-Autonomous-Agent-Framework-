import asyncio
from src.layer00_utils.config_manager import config
from src.layer03_brain.llm.client import client_openai, key_manager
from src.layer00_utils.logger import system_logger

async def describe_image(base64_image: str, custom_prompt: str = None) -> str:
    multimodal_model = config.llm.multimodal_model
    
    prompt_text = custom_prompt if custom_prompt else "Опиши это изображение максимально подробно. Что на нем происходит, есть ли текст (если есть - процитируй), какие объекты выделяются. Не теряй ни одной детали."
    
    messages =[
        {
            "role": "user",
            "content":[
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }
    ]
    
    max_attempts = key_manager.total_active if key_manager.total_active > 0 else 1
    for attempt in range(max_attempts):
        current_key = await key_manager.get_next_key()
        if current_key == "ALL_KEYS_EXHAUSTED": 
            return "[Ошибка: Все API ключи исчерпали квоту]"
        client_openai.api_key = current_key
        try:
            response = await client_openai.chat.completions.create(model=multimodal_model, messages=messages, max_tokens=1500)
            return f"[Мультимодальная подмодель ({multimodal_model})]: {response.choices[0].message.content}"
        except Exception as e:
            system_logger.warning(f"[Vision] Ошибка API ({multimodal_model}): {e}")
            if attempt < max_attempts - 1: 
                await asyncio.sleep(1)
            else: 
                return f"[Ошибка анализа изображения: {e}]"
    return "[Не удалось получить описание изображения]"

async def transcribe_audio(base64_audio: str) -> str:
    multimodal_model = config.llm.multimodal_model
    
    messages = [
        {
            "role": "user",
            "content":[
                {"type": "text", "text": "Транскрибируй это голосовое сообщение дословно. Если там есть ярко выраженные эмоции (смех, крик), укажи их в скобках. Не упускай абсолютно никаких деталей."},
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64_audio,
                        "format": "mp3"
                    }
                }
            ]
        }
    ]
    
    max_attempts = key_manager.total_active if key_manager.total_active > 0 else 1
    for attempt in range(max_attempts):
        current_key = await key_manager.get_next_key()
        if current_key == "ALL_KEYS_EXHAUSTED": 
            return "[Ошибка: Все API ключи исчерпали квоту]"
        client_openai.api_key = current_key
        try:
            response = await client_openai.chat.completions.create(model=multimodal_model, messages=messages)
            return f"[Голосовое сообщение (транскрибация от мультимодальной подмодели {multimodal_model})]: {response.choices[0].message.content}"
        except Exception as e:
            system_logger.warning(f"[Audio] Ошибка API ({multimodal_model}): {e}")
            if attempt < max_attempts - 1: 
                await asyncio.sleep(1)
            else: 
                return f"[Ошибка транскрибации аудио: {e}]"
    return "[Не удалось распознать аудио]"