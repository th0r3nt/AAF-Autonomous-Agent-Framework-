# Используем Debian-based slim образ. Alpine ломает сборку ChromaDB, Kuzu и PyTorch
FROM python:3.11-slim

# Настройки Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Устанавливаем системные зависимости
# build-essential, gcc, g++ нужны для компиляции некоторых C-расширений
# curl, gnupg необходимы для скачивания ключей Docker
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    gnupg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Docker CLI (для отладки DooD внутри контейнера)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем зависимости и устанавливаем их
# Делаем это отдельным шагом для кэширования слоев Docker
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Копируем остальной код проекта
COPY . .

# Точка входа. Запускаем именно src.main, так как там находится asyncio.run()
CMD ["python", "-m", "src.main"]