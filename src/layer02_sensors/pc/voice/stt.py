import json
import os
import vosk
import asyncio
import wave
from dotenv import load_dotenv
from config.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer00_utils.watchdog.watchdog import stt_module
from src.layer01_datastate.sql_db.management.dialogue import create_dialogue_entry

try:
    import sounddevice
except (ImportError, OSError):
    sounddevice = None

load_dotenv()

VOSK_MODEL_PATH = config.hardware.voice.stt_model_path
VOICE_QUERY = Events.VOICE_QUERY

class VoskSpeechListener:
    def __init__(self):
        self.audio_queue = asyncio.Queue() 
        self.loop = asyncio.get_event_loop()
        
        # Если включен Headless, даже не пытаемся грузить модель в ОЗУ
        if config.system.flags.headless_mode or not sounddevice:
            system_logger.warning("[Vosk] Headless режим включен или sounddevice недоступен. Микрофон отключен.")
            self.recognizer = None
            self.model = None
            return

        try:
            if not os.path.exists(VOSK_MODEL_PATH):
                raise FileNotFoundError(f"Модель Vosk не найдена по пути: {VOSK_MODEL_PATH}")

            self.model = vosk.Model(VOSK_MODEL_PATH)
            self.recognizer = vosk.KaldiRecognizer(self.model, config.hardware.voice.sample_rate)

            system_logger.info("[Vosk] Локальное распознавание голоса инициализировано.")

        except Exception as e:
            system_logger.error(f"[Vosk] Ошибка при инициализации: {e}")
            self.recognizer = None

    def _audio_callback(self, indata, frames, time, status):
        if status:
            system_logger.warning(f"[Vosk] Статус микрофона: {status}")
        # Безопасно передаем байты звука из аудиопотока в наш главный асинхронный цикл
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, bytes(indata))

    async def run_loop(self):
        if not self.recognizer or config.system.flags.headless_mode:
            system_logger.info("[Vosk] Модуль прослушивания микрофона деактивирован.")
            return
        
        system_logger.info("[Vosk] Цикл прослушивания микрофона запущен.")
        
        try:
            # Звук пишется в фоне, а мы асинхронно забираем его из очереди
            with sounddevice.RawInputStream(
                samplerate=16000, blocksize=16000, dtype='int16', 
                channels=1, callback=self._audio_callback
            ):
                while True:
                    await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=stt_module, status="ON")
                    data = await self.audio_queue.get() 

                    is_speech = await asyncio.to_thread(self.recognizer.AcceptWaveform, data)

                    if is_speech:
                        # Result() тоже лучше в поток, на всякий случай
                        res_str = await asyncio.to_thread(self.recognizer.Result)
                        result = json.loads(res_str)
                        query = result.get("text", "")

                        if query:
                            system_logger.info(f"[Vosk] Распознано: {query}")

                            # Записываем то, что услышали, в историю
                            await create_dialogue_entry(
                                actor="user", 
                                message=query, 
                                source="pc_microphone"
                            )

                            await event_bus.publish(VOICE_QUERY, query)

        except Exception as e:
            await event_bus.publish(Events.SYSTEM_MODULE_ERROR, module_name=stt_module, status="ERROR", error_msg=str(e))
            system_logger.error(f"[Vosk] Ошибка в цикле записи: {e}")

    async def transcribe_audio_file(self, filepath: str) -> str:
        """Транскрибирует готовый .wav файл (16kHz, mono)"""
        if not self.model:
            return "Ошибка: Модель Vosk не загружена."
        
        try:
            # Читаем wav файл (запускаем в to_thread, так как это блокирующие I/O операции)
            def _process_file():
                wf = wave.open(filepath, "rb")
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                    return "Ошибка: Аудиофайл должен быть в формате WAV моно PCM."
                
                # Создаем отдельный recognizer для файла
                rec = vosk.KaldiRecognizer(self.model, wf.getframerate())
                rec.SetWords(True)

                results = []
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    if rec.AcceptWaveform(data):
                        part_result = json.loads(rec.Result())
                        results.append(part_result.get("text", ""))
                
                part_result = json.loads(rec.FinalResult())
                results.append(part_result.get("text", ""))
                wf.close()
                
                return " ".join(filter(None, results))

            text = await asyncio.to_thread(_process_file)
            return text

        except Exception as e:
            system_logger.error(f"[Vosk] Ошибка при транскрибации файла: {e}")
            return f"Ошибка при транскрибации файла: {e}"

stt = VoskSpeechListener() 

async def stt_loop():
    # Теперь мы запускаем его напрямую, так как он на 100% асинхронный
    await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=stt_module, status="ON") # # Отправляем сигнал, что модуль запустился
    await stt.run_loop()