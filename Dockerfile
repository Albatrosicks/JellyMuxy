FROM python:3.11-slim

# Устанавливаем нужные пакеты и ключ GPG для репозитория mkvtoolnix
RUN echo "deb https://deb.debian.org/debian bookworm main contrib non-free" > /etc/apt/sources.list.d/debian.list && \
    apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    unzip \
    p7zip-full \
    unrar && \
    rm -rf /var/lib/apt/lists/*

# Добавляем ключ и репозиторий mkvtoolnix (для Ubuntu 22.04 Jammy)
RUN mkdir -p /etc/apt/keyrings/ && \
    wget -qO - https://mkvtoolnix.download/gpg-pub-moritzbunkus.gpg | gpg --dearmor > /etc/apt/keyrings/gpg-pub-moritzbunkus.gpg && \
    echo " deb [signed-by=/etc/apt/keyrings/gpg-pub-moritzbunkus.gpg] https://mkvtoolnix.download/debian/ bookworm main" > /etc/apt/sources.list.d/mkvtoolnix.download.list && \
    apt-get update && \
    apt-get install -y mkvtoolnix mkvtoolnix-gui && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV ROOT_DIR=/data
ENV CONFIG_DIR=/config

EXPOSE 5000

CMD ["python", "main.py"]
