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

# Динамическая установка звисимостей плагинов для конкретного агента

# Получаем имя агента при сборке (передается из aaf.py -> docker-compose)
ARG AGENT_NAME
# Сохраняем его как переменную окружения внутри контейнера
ENV AGENT_NAME=${AGENT_NAME}

# Проверяем, есть ли файл custom_requirements.txt в папке плагинов этого агента.
# Если есть - устанавливаем библиотеки из него. || true защищает от падения сборки.
RUN if [ -f /app/Agents/${AGENT_NAME}/plugins/custom_requirements.txt ]; then \
        echo "Installing custom plugins dependencies for ${AGENT_NAME}..." && \
        pip install --no-cache-dir -r /app/Agents/${AGENT_NAME}/plugins/custom_requirements.txt || true; \
    fi

# Указываем команду для запуска
CMD ["python", "-m", "src.main"]