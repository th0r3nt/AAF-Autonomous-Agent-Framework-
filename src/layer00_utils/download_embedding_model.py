from sentence_transformers import SentenceTransformer
import os 
from dotenv import load_dotenv

load_dotenv()

LOCAL_EMBEDDING_MODEL_PATH = os.getenv("LOCAL_EMBEDDING_MODEL_PATH")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

# Указываем название модели
model_name = "BAAI/bge-m3" # Хороший выбор с балансом скорости/качества
cache_folder = "./local_models" # Укажите папку, куда сохранить модель

print(f"Скачиваю модель '{model_name}' в папку '{cache_folder}'.")

# Эта команда скачает все необходимые файлы модели и сохранит их в указанную папку
model = SentenceTransformer(model_name, cache_folder=LOCAL_EMBEDDING_MODEL_PATH)

print("Модель успешно скачана и сохранена локально!")