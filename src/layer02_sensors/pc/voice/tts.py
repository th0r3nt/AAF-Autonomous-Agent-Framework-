import edge_tts
import asyncio
from dotenv import load_dotenv
import os
from datetime import datetime
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.workspace import workspace_manager

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

load_dotenv()

TTS_VOICE = config.hardware.voice.tts_voice # edge-tts --list-voices
PHRASES_DIR = os.path.join("src", "layer00_utils", "phrases")

class EdgeTTS:
    def __init__(self):
        global PYGAME_AVAILABLE
        self.filename = ""
        
        if PYGAME_AVAILABLE and not config.system.flags.headless_mode:
            try:
                # В Docker без проброса звука это может упасть
                pygame.mixer.init()
            except Exception as e:
                system_logger.warning(f"[TTS] Не удалось инициализировать аудиодрайвер (pygame): {e}")
                PYGAME_AVAILABLE = False # Отключаем, чтобы не падало при попытке воспроизведения
        else:
            system_logger.warning("[TTS] Headless режим или pygame недоступен. Воспроизведение звука на ПК отключено.")

        if not os.path.exists(PHRASES_DIR):
            os.makedirs(PHRASES_DIR)
            system_logger.debug(f"[TTS] Создана директория для фраз: {PHRASES_DIR}")

    async def generate_voice(self, text: str) -> None:
        """Создает .mp3 файл с озвучкой текста"""
        if not text.strip():
            system_logger.warning("[STT] Аргумент text пуст.")
            return
        
        # Защита: вырезаем префикс, чтобы синтезатор не читал его вслух
        text = text.replace(f"[{config.identity.agent_name}]", "").strip()
        
        try:
            communicate = edge_tts.Communicate(text, TTS_VOICE)

            time_str = datetime.now().strftime("%H-%M-%S")
            file_name = f"{time_str}_voice.mp3"

            full_path = os.path.join(PHRASES_DIR, file_name)
            self.filename = full_path

            await communicate.save(full_path)
            system_logger.debug(f"[TTS] Голос успешно сгенерирован в '{full_path}'")

            await self._play_audio(full_path) # Отправляем озвучивать

        except Exception as e:
            system_logger.error(f"[TTS] Ошибка при генерации голоса: {e}")

    async def _play_audio(self, file_path: str) -> None:
        """Воспроизводит аудиофайл с помощью pygame"""
        if config.system.flags.headless_mode or not PYGAME_AVAILABLE:
            # В headless режиме просто удаляем файл, так как играть его не на чем
            if os.path.exists(file_path):
                os.remove(file_path)
            return

        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Файл {file_path} не найден")
            
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            system_logger.debug(f"[TTS] Воспроизведение '{file_path}'.")

            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)

            pygame.mixer.music.unload() # Разгружаем файл, чтобы его можно было удалить
            
            await asyncio.sleep(0.5) # Небольшая пауза, чтобы Windows точно отпустил файл
            if os.path.exists(file_path):
                os.remove(file_path)
                system_logger.debug(f"[TTS] Файл '{file_path}' удален с диска.")
                
        except pygame.error as e:
            system_logger.error(f"[TTS] Ошибка при воспроизведении аудиофайла '{file_path}': {e}")
        except FileNotFoundError:
            system_logger.error(f"[TTS] Ошибка: Файл '{file_path}' не найден.")
        except Exception as e:
            system_logger.error(f"[TTS] Ошибка при воспроизведении звукового файла: {e}")

    async def generate_audio_file(self, text: str) -> str:
        """Только генерирует .mp3 во временную папку и возвращает путь (без воспроизведения)"""
        if not text.strip():
            raise ValueError("Текст для озвучки пуст.")
        
        # Защита: вырезаем префикс, чтобы синтезатор не читал его вслух
        text = text.replace(f"[{config.identity.agent_name}]", "").strip()
        
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        
        file_path = workspace_manager.get_temp_file(prefix="voice_", extension=".mp3")
        
        await communicate.save(str(file_path))
        system_logger.debug(f"[TTS] Аудиофайл сгенерирован: {file_path}")
        
        return str(file_path)

tts = EdgeTTS()

async def generate_voice(text) -> None:
    """Обертка: генерирует .mp3 файл и озвучивает его"""
    await tts.generate_voice(text)
    return True



if __name__ == "__main__":
    test_text = "Сэр, провайдер решил устроить нам цифровой детокс. Пакеты данных не проходят, интернет пропал, мы в цифровом вакууме. Предлагаю два варианта: либо вы звоните в техподдержку и кричите на людей, либо мы наслаждаемся оффлайн-режимом, как пещерные люди."
    asyncio.run(generate_voice(test_text))
    print("Тык.")


# Неплохие голоса в EdgeTTS: 

# pt-BR-ThalitaMultilingualNeural   +-
# de-DE-FlorianMultilingualNeural   +
# de-DE-SeraphinaMultilingualNeural +
# en-AU-WilliamMultilingualNeural   +
# en-US-AndrewMultilingualNeural    -
# en-US-BrianMultilingualNeural     +-
# fr-FR-RemyMultilingualNeural      +
# fr-FR-VivienneMultilingualNeural  +
# it-IT-GiuseppeMultilingualNeural  -
# ko-KR-HyunsuMultilingualNeural    -
# ru-RU-DmitryNeural                +
# ru-RU-SvetlanaNeural              +