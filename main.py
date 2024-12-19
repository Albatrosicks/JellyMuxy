import os
import time
import threading
import logging
import sqlite3
import subprocess
from datetime import datetime
from flask import Flask, jsonify, render_template_string
from pymkv import MKVFile, MKVTrack
import shutil
import re
import py7zr
import patoolib
from pathlib import Path
import json

from config import get_config
from subtitle_utils import subtitle_info_checker, is_font_file
from compressed import unzip

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

app = Flask(__name__)

ROOT_DIR = os.environ.get("ROOT_DIR", "/data")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/config")
config_path = os.path.join(CONFIG_DIR, "config.json")
config = get_config(config_path=config_path)

DELETE_FONTS = config["TaskSettings"]["DeleteFonts"]
DELETE_ORIGINAL_MKV = config["TaskSettings"]["DeleteOriginalMKV"]
DELETE_ORIGINAL_MKA = config["TaskSettings"]["DeleteOriginalMKA"]
DELETE_SUB = config["TaskSettings"]["DeleteSubtitle"]
SUFFIX_NAME = "_Jelly"

UNRAR_PATH = config["Font"]["Unrar_Path"]
T_COUNT = config["multiprocessing"]["thread_count"]

DB_PATH = os.path.join(CONFIG_DIR, "directories.db")

processing_files = {}  # {dir_path: current_file_name}

def init_db():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS directories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  path TEXT UNIQUE,
                  status TEXT,
                  last_update TEXT)''')
    conn.commit()
    conn.close()

init_db()

def update_directory_status(path, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO directories (path, status, last_update) VALUES (?, ?, ?)",
              (path, status, datetime.now().isoformat()))
    c.execute("UPDATE directories SET status=?, last_update=? WHERE path=?",
              (status, datetime.now().isoformat(), path))
    conn.commit()
    conn.close()
    if status != "PROCESSING":
        if path in processing_files:
            processing_files[path] = None

def get_directory_status(path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status,last_update FROM directories WHERE path=?", (path,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None, None

def get_all_directories():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT path, status, last_update FROM directories")
    rows = c.fetchall()
    conn.close()
    return rows

def scan_root_directory():
    # Теперь нам нужно рекурсивно проверить есть ли mkv файлы внутри директории верхнего уровня
    for item in os.listdir(ROOT_DIR):
        full_path = os.path.join(ROOT_DIR, item)
        if os.path.isdir(full_path):
            # Рекурсивно ищем mkv
            if contains_mkv(full_path):
                status, _ = get_directory_status(full_path)
                if status is None:
                    update_directory_status(full_path, "PENDING")

def contains_mkv(directory):
    # Рекурсивно проверяем наличие хотя бы одного mkv файла
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith(".mkv"):
                return True
    return False

def directory_changed_since_last_update(path, last_update_str):
    if not last_update_str:
        return True
    last_update = datetime.fromisoformat(last_update_str)
    newest_mtime = datetime.fromtimestamp(0)

    for root, _, files in os.walk(path):
        for f in files:
            full_path = os.path.join(root, f)
            mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
            if mtime > newest_mtime:
                newest_mtime = mtime

    return newest_mtime > last_update

def are_files_stable(path, wait_time=2):
    initial_sizes = {}
    for root, _, files in os.walk(path):
        for f in files:
            full_path = os.path.join(root, f)
            try:
                initial_sizes[full_path] = os.path.getsize(full_path)
            except FileNotFoundError:
                return False

    time.sleep(wait_time)

    for full_path, initial_size in initial_sizes.items():
        if not os.path.exists(full_path):
            return False
        new_size = os.path.getsize(full_path)
        if new_size != initial_size:
            return False

    return True

def ensure_special_dirs(base_path):
    fonts_dir = os.path.join(base_path, "Fonts")
    extra_dir = os.path.join(base_path, "Extra")

    if not os.path.exists(fonts_dir):
        os.makedirs(fonts_dir, exist_ok=True)
        open(os.path.join(fonts_dir, ".ignore"), "w").close()

    if not os.path.exists(extra_dir):
        os.makedirs(extra_dir, exist_ok=True)
        open(os.path.join(extra_dir, ".ignore"), "w").close()

    return fonts_dir, extra_dir

def remove_empty_dirs(base_path):
    extra_dir = os.path.join(base_path, "Extra")
    fonts_dir = os.path.join(base_path, "Fonts")

    for root, dirs, files in os.walk(base_path, topdown=False):
        if root == base_path:
            continue
        if os.path.normpath(root) == os.path.normpath(extra_dir):
            continue
        if os.path.normpath(root) == os.path.normpath(fonts_dir):
            continue

        only_ignore = True
        for f in files:
            if f != ".ignore":
                only_ignore = False
                break
        if only_ignore and len(files) <= 1 and len(dirs) == 0:
            try:
                shutil.rmtree(root)
            except OSError as e:
                logging.error(f"Failed to remove empty directory {root}: {e}")

def process_directory(path):
    status, last_update = get_directory_status(path)
    if status == "OK":
        if not directory_changed_since_last_update(path, last_update):
            logging.info(f"No changes in {path} since last OK, skipping reprocessing.")
            return

    if not are_files_stable(path, wait_time=2):
        logging.info(f"Files in {path} are not stable yet. Will keep status PENDING.")
        return

    update_directory_status(path, "PROCESSING")

    try:
        # Теперь уже внутри process_directory мы делаем рекурсивное сканирование
        all_files = []
        for root, _, files in os.walk(path):
            for f in files:
                all_files.append(os.path.join(root, f))

        fonts_dir, extra_dir = ensure_special_dirs(path)

        # Распаковка шрифтов
        for file_path in all_files:
            lower_name = os.path.basename(file_path).lower()
            if "font" in lower_name:
                if lower_name.endswith(".zip"):
                    unzip(file_path, "utf-8")
                elif lower_name.endswith(".7z"):
                    with py7zr.SevenZipFile(file_path, 'r') as z:
                        z.extractall(fonts_dir)
                elif lower_name.endswith(".rar") and UNRAR_PATH:
                    patoolib.extract_archive(file_path, outdir=fonts_dir, program=UNRAR_PATH)

        unfiltered_font_list = os.listdir(fonts_dir) if os.path.exists(fonts_dir) else []
        font_list = list(filter(is_font_file, unfiltered_font_list))

        folder_mkv_list = [f for f in all_files if f.endswith(".mkv")]
        folder_other_file_list = [f for f in all_files if not f.endswith(".mkv") and "." in os.path.basename(f)]

        for mkv_file_path in folder_mkv_list:
            mkv_mux_task(mkv_file_path, folder_other_file_list, font_list, path)

        if DELETE_FONTS and os.path.exists(fonts_dir):
            shutil.rmtree(fonts_dir)
            os.makedirs(fonts_dir, exist_ok=True)
            open(os.path.join(fonts_dir, ".ignore"), "w").close()

        update_directory_status(path, "OK")
        logging.info(f"Directory processed successfully: {path}")
    except Exception as e:
        logging.error(f"Error processing directory {path}: {e}")
        update_directory_status(path, "ERROR")

    remove_empty_dirs(path)

def mkv_mux_task(mkv_file_path: str, folder_other_file_list: list, font_list: list, base_path: str):
    mkv_dir, mkv_file_name = os.path.split(mkv_file_path)
    mkv_name_no_extension = mkv_file_name.rsplit('.', 1)[0]

    processing_files[base_path] = mkv_file_name

    this_task = MKVFile(mkv_file_path)

    delete_list = []
    move_list = []

    original_final_name = os.path.join(mkv_dir, mkv_name_no_extension + ".mkv")
    new_mkv_name = os.path.join(mkv_dir, mkv_name_no_extension + SUFFIX_NAME + ".mkv")

    sub_track_count = 0

    # Добавляем поддержку .srt субтитров
    subtitle_extensions = (".ass", ".srt")

    for item in folder_other_file_list:
        if mkv_name_no_extension in os.path.basename(item):
            if item.endswith(subtitle_extensions):
                sub_info = subtitle_info_checker(item)
                if sub_info["language"] != "":
                    track_name = sub_info["language"]
                    sub_track = MKVTrack(item,
                                         track_name=track_name,
                                         default_track=False,
                                         language=sub_info["mkv_language"])
                    if sub_info["default_language"]:
                        sub_track.default_track = True
                        sub_track.forced_track = True
                    this_task.add_track(sub_track)
                    sub_track_count += 1
                    if DELETE_SUB:
                        delete_list.append(item)
                    else:
                        move_list.append(item)
            if item.endswith(".mka"):
                this_task.add_track(item)
                if DELETE_ORIGINAL_MKA:
                    delete_list.append(item)
                else:
                    move_list.append(item)

    if sub_track_count == 0:
        # Не нашли субтитров, проверим все *.ass и *.srt
        all_subs = [f for f in folder_other_file_list if f.endswith(subtitle_extensions)]
        for sub_file in all_subs:
            sub_info = subtitle_info_checker(sub_file)
            if sub_info["language"] != "":
                track_name = sub_info["language"]
                sub_track = MKVTrack(sub_file,
                                     track_name=track_name,
                                     default_track=False,
                                     language=sub_info["mkv_language"])
                if sub_info["default_language"]:
                    sub_track.default_track = True
                    sub_track.forced_track = True
                this_task.add_track(sub_track)
                sub_track_count += 1
                if DELETE_SUB:
                    delete_list.append(sub_file)
                else:
                    move_list.append(sub_file)

    if sub_track_count == 1:
        for track in this_task.tracks:
            if track.track_type == "subtitles":
                track.default_track = True

    # Добавляем шрифты
    for font in font_list:
        font_path = os.path.join(base_path, "Fonts", font)
        this_task.add_attachment(font_path)

    # Обработка оригинального MKV
    if DELETE_ORIGINAL_MKV:
        delete_list.append(mkv_file_path)
    # Если не удаляем MKV, то он остаётся на месте, мы его не перемещаем.

    try:
        this_task.mux(new_mkv_name, silent=True)
        logging.info("Muxed successfully: " + new_mkv_name)
    except subprocess.CalledProcessError as e:
        logging.error("MKVMerge error: " + str(e))

    extra_dir = os.path.join(base_path, "Extra")
    if not os.path.exists(extra_dir):
        os.makedirs(extra_dir, exist_ok=True)
        open(os.path.join(extra_dir, ".ignore"), "w").close()

    # Перемещаем файлы из move_list в Extra
    for f in move_list:
        if os.path.exists(f):
            dest = os.path.join(extra_dir, os.path.basename(f))
            logging.info(f"Moving file {f} to {dest}")
            shutil.move(f, dest)
            # Проверяем, что файл исчез из исходного места
            if os.path.exists(f):
                logging.warning(f"File {f} still exists after move! Trying to remove it.")
                try:
                    os.remove(f)
                except Exception as ex:
                    logging.error(f"Failed to remove {f}: {ex}")
        else:
            logging.warning(f"File {f} does not exist before move operation.")

    # Удаляем файлы из delete_list
    for f in delete_list:
        if os.path.exists(f):
            logging.info(f"Deleting file {f}")
            os.remove(f)
        else:
            logging.warning(f"File {f} not found for deletion.")

    # Переименовываем финальный mkv
    if os.path.exists(new_mkv_name):
        if os.path.exists(original_final_name):
            os.remove(original_final_name)
        os.rename(new_mkv_name, original_final_name)
        logging.info(f"Renamed {new_mkv_name} to {original_final_name}")

    processing_files[base_path] = None

def background_worker():
    while True:
        try:
            scan_root_directory()
            dirs = get_all_directories()
            for d in dirs:
                path, status, _ = d
                if status == "PENDING":
                    process_directory(path)
        except Exception as e:
            logging.error(f"Background worker error: {e}")
        time.sleep(60)

t = threading.Thread(target=background_worker, daemon=True)
t.start()

@app.route('/status')
def status():
    dirs = get_all_directories()
    resp = []
    for d in dirs:
        entry = {
            "path": d[0],
            "status": d[1],
            "last_update": d[2],
            "current_file": processing_files.get(d[0])
        }
        resp.append(entry)
    return jsonify(resp)

@app.route('/')
def index():
    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Directory Status</title>
<style>
  body {
    font-family: sans-serif;
    margin: 20px;
    transition: background-color 0.3s, color 0.3s;
  }

  @media (prefers-color-scheme: dark) {
    body {
      background-color: #222;
      color: #fff;
    }
  }

  @media (prefers-color-scheme: light) {
    body {
      background-color: #f5f5f5;
      color: #000;
    }
  }

  .status-dot {
    display: inline-block;
    width: 0.8em;
    height: 0.8em;
    border-radius: 50%;
    margin-right: 0.5em;
  }

  .status-OK .status-dot {
    background-color: green;
  }
  .status-PENDING .status-dot {
    background-color: gray;
  }
  .status-PROCESSING .status-dot {
    background-color: orange;
  }
  .status-ERROR .status-dot {
    background-color: red;
  }

  .processing-file {
    color: gray;
    font-style: italic;
    margin-left: 1.5em;
  }

</style>
</head>
<body>
<h1>Directory Status</h1>
<div id="dirs"></div>

<script>
async function updateStatus() {
  const res = await fetch('/status');
  const data = await res.json();
  const container = document.getElementById('dirs');
  container.innerHTML = '';
  data.forEach(dir => {
    const div = document.createElement('div');
    div.className = 'status-' + dir.status;
    let statusName = dir.status;
    const dot = '<span class="status-dot"></span>';
    div.innerHTML = dot + dir.path + ' - ' + statusName;

    if (dir.status === 'PROCESSING' && dir.current_file) {
      const fileDiv = document.createElement('div');
      fileDiv.className = 'processing-file';
      fileDiv.textContent = dir.current_file;
      div.appendChild(fileDiv);
    }

    container.appendChild(div);
  });
}

updateStatus();
setInterval(updateStatus, 1000);
</script>
</body>
</html>
"""
    return render_template_string(html_template)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
