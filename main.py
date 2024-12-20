import os
import time
import threading
import logging
from flask import Flask, jsonify, render_template, request
from database import init_db, get_all_directories, update_directory_status, get_directory_status
from processing import process_directory
from config import get_config

app = Flask(__name__)

# Получение переменных окружения или установка значений по умолчанию
ROOT_DIR = os.environ.get("ROOT_DIR", "/data")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/config")
config_path = os.path.join(CONFIG_DIR, "config.json")
config = get_config(config_path=config_path)

# Настройки из конфигурации
DELETE_FONTS = config["TaskSettings"]["DeleteFonts"]
DELETE_ORIGINAL_MKV = config["TaskSettings"]["DeleteOriginalMKV"]
DELETE_ORIGINAL_MKA = config["TaskSettings"]["DeleteOriginalMKA"]
DELETE_SUB = config["TaskSettings"]["DeleteSubtitle"]
SUFFIX_NAME = config["TaskSettings"].get("OutputSuffixName", "_Plex")

UNRAR_PATH = config["Font"]["Unrar_Path"]
T_COUNT = config["multiprocessing"]["thread_count"]

DB_PATH = os.path.join(CONFIG_DIR, "directories.db")

# Глобальные переменные
processing_files = {}  # {dir_path: current_file_name}
paused = False  # Флаг паузы

# Инициализация базы данных
init_db()

# Функция для сканирования корневой директории
def scan_root_directory():
    for category in os.listdir(ROOT_DIR):
        category_path = os.path.join(ROOT_DIR, category)
        if os.path.isdir(category_path):
            for item in os.listdir(category_path):
                full_path = os.path.join(category_path, item)
                if os.path.isdir(full_path) and contains_mkv(full_path):
                    status, last_update, logs = get_directory_status(full_path)
                    if status is None:
                        update_directory_status(full_path, "PENDING")
                        logging.info(f"Directory marked as PENDING: {full_path}")

# Проверка наличия хотя бы одного mkv файла в директории рекурсивно
def contains_mkv(directory):
    for root, _, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(".mkv"):
                return True
    return False

# Фоновый рабочий поток
def background_worker():
    global paused
    while True:
        if paused:
            logging.info("Background worker paused. Waiting...")
            time.sleep(5)
            continue
        try:
            scan_root_directory()
            dirs = get_all_directories()
            for d in dirs:
                path, status, last_update, logs = d
                if paused:
                    logging.info("Paused during directory processing iteration.")
                    break
                if status == "PENDING":
                    process_directory(path)
        except Exception as e:
            logging.error(f"Background worker error: {e}")
        time.sleep(60)

# Запуск фонового рабочего потока
t = threading.Thread(target=background_worker, daemon=True)
t.start()

# Эндпоинт для получения статуса
@app.route('/status')
def status():
    dirs = get_all_directories()
    resp = []
    for d in dirs:
        entry = {
            "path": d[0],
            "status": d[1],
            "last_update": d[2],
            "current_file": processing_files.get(d[0]),
            # "logs": d[3]  # Если хотите отображать логи на фронтенде
        }
        resp.append(entry)
    return jsonify(resp)

# Эндпоинт для получения состояния паузы
@app.route('/status_state')
def status_state():
    return jsonify({"paused": paused})

# Главная страница с кнопкой Toggle Pause/Unpause
@app.route('/', methods=["GET"])
def index():
    return render_template('index.html')

# Эндпоинт для управления паузой (toggle)
@app.route('/toggle_pause', methods=['POST'])
def toggle_pause():
    global paused
    paused = not paused
    state = "paused" if paused else "unpaused"
    logging.info(f"Background worker {state} by user.")
    return jsonify({"paused": paused, "state": state})

# Запуск Flask приложения
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
