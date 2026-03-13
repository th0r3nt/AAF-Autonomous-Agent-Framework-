# Используем официальный легкий образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости
# ffmpeg - для работы с аудио (Vosk/EdgeTTS/Pydub)
# docker.io - чтобы агент мог запускать субагентов (Agent Swarm System)
# build-essential, g++, python3-dev - для компиляции ChromaDB и KuzuDB
RUN apt-get update && apt-get install -y \
    ffmpeg \
    docker.io \
    build-essential \
    g++ \
    python3-dev \
    portaudio19-dev \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Задаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем сначала только requirements, чтобы закэшировать слой установки
COPY requirements.txt .

# Устанавливаем Python-библиотеки
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код проекта
COPY . .

# Указываем команду для запуска ядра
CMD ["python", "main.py"]