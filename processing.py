import os
import logging
import time
import shutil
import py7zr
import patoolib
from pathlib import Path
from datetime import datetime
from database import update_directory_status, get_directory_status
from logging_capture import LogCaptureHandler
from subtitle_utils import subtitle_info_checker, is_font_file
from compressed import unzip
from muxing import is_allowed_codec, mkv_mux_task

# Импортируем необходимые настройки
from config import get_config

# Получение конфигурации
config = get_config()
DELETE_FONTS = config["TaskSettings"]["DeleteFonts"]
DELETE_ORIGINAL_MKV = config["TaskSettings"]["DeleteOriginalMKV"]
DELETE_ORIGINAL_MKA = config["TaskSettings"]["DeleteOriginalMKA"]
DELETE_SUB = config["TaskSettings"]["DeleteSubtitle"]
SUFFIX_NAME = config["TaskSettings"].get("OutputSuffixName", "_Jelly")
ALLOWED_CODECS = config.get("AllowedCodecs", ["HEVC"])

# Глобальные переменные (импортируются из main.py)
# Предполагается, что main.py импортирует и управляет этими переменными
processing_files = {}  # {dir_path: current_file_name}

def process_directory(path):
    """
    Обрабатывает указанную директорию:
    - Проверяет статус и изменения файлов
    - Распаковывает шрифты из архивов
    - Перемещает шрифты в основную директорию Fonts
    - Фильтрует и обрабатывает MKV-файлы с допустимыми кодеками
    - Выполняет muxing MKV-файлов
    - Обрабатывает категорию 'movies' (переименование и перемещение)
    - Удаляет пустые вложенные директории
    - Захватывает и сохраняет логи обработки в базе данных
    """
    # Получение статуса директории из базы данных
    status, last_update, _ = get_directory_status(path)
    if status == "OK" and not directory_changed_since_last_update(path, last_update):
        logging.info(f"No changes in {path} since last OK, skipping reprocessing.")
        return

    if not are_files_stable(path):
        logging.info(f"Files in {path} are not stable yet. Will keep status PENDING.")
        return

    # Захват логов в память
    log_capture = LogCaptureHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
    log_capture.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(log_capture)

    # Обновление статуса директории на PROCESSING
    update_directory_status(path, "PROCESSING")
    logging.info(f"Started processing directory: {path}")

    try:
        all_files = []
        for root, _, files in os.walk(path):
            for f in files:
                full_path = os.path.join(root, f)
                try:
                    if os.path.getsize(full_path) == 0:
                        logging.info(f"Skipping empty file: {full_path}")
                        continue
                except OSError as e:
                    logging.error(f"Error accessing file {full_path}: {e}")
                    continue
                all_files.append(full_path)

        # Создание и получение специальных директорий Fonts и Extra
        fonts_dir, extra_dir = ensure_special_dirs(path)

        # Распаковка шрифтов из архивов
        for file_path in all_files:
            lower_name = os.path.basename(file_path).lower()
            if "font" in lower_name:
                try:
                    if lower_name.endswith(".zip"):
                        unzip(file_path, "utf-8")
                        logging.info(f"Unzipped font archive: {file_path}")
                    elif lower_name.endswith(".7z"):
                        with py7zr.SevenZipFile(file_path, 'r') as z:
                            z.extractall(fonts_dir)
                        logging.info(f"Extracted 7z font archive: {file_path}")
                    elif lower_name.endswith(".rar") and config["Font"].get("Unrar_Path"):
                        patoolib.extract_archive(file_path, outdir=fonts_dir, program=config["Font"]["Unrar_Path"])
                        logging.info(f"Extracted rar font archive: {file_path}")
                except Exception as e:
                    logging.error(f"Failed to extract fonts from {file_path}: {e}")

        # Сбор всех директорий Fonts внутри base_path
        font_dirs = [os.path.join(root, d) for root, dirs, _ in os.walk(path) for d in dirs if d.lower() == 'fonts']
        font_list = []
        for font_dir in font_dirs:
            try:
                fonts = [os.path.join(font_dir, f) for f in os.listdir(font_dir) if is_font_file(f)]
                font_list.extend(fonts)
                logging.info(f"Collected fonts from {font_dir}: {fonts}")
            except Exception as e:
                logging.error(f"Failed to collect fonts from {font_dir}: {e}")

        # Определяем основную директорию Fonts
        main_fonts_dir = os.path.join(path, "Fonts")
        if not os.path.exists(main_fonts_dir):
            os.makedirs(main_fonts_dir, exist_ok=True)
            logging.info(f"Created main Fonts directory: {main_fonts_dir}")

        # Перемещение шрифтов из вложенных директорий Fonts в основную директорию Fonts
        for font_dir in font_dirs:
            if os.path.abspath(font_dir) != os.path.abspath(main_fonts_dir):
                for font_file in [f for f in os.listdir(font_dir) if is_font_file(f)]:
                    src = os.path.join(font_dir, font_file)
                    dest = os.path.join(main_fonts_dir, font_file)
                    try:
                        shutil.move(src, dest)
                        logging.info(f"Moved font {src} to {dest}")
                        font_list.append(dest)
                    except Exception as e:
                        logging.error(f"Failed to move font {src} to {dest}: {e}")

        # Удаление пустых вложенных директорий Fonts после перемещения
        for font_dir in font_dirs:
            if os.path.abspath(font_dir) != os.path.abspath(main_fonts_dir):
                try:
                    os.rmdir(font_dir)
                    logging.info(f"Removed empty Fonts directory: {font_dir}")
                except OSError as e:
                    logging.error(f"Failed to remove directory {font_dir}: {e}")

        # Обновление списка шрифтов после перемещения
        font_list = [os.path.join(main_fonts_dir, f) for f in os.listdir(main_fonts_dir) if is_font_file(f)]
        logging.info(f"Updated font list after moving: {font_list}")

        # Фильтрация MKV-файлов: допустимые кодеки
        folder_mkv_list = []
        for f in all_files:
            if f.lower().endswith(".mkv"):
                if is_allowed_codec(f, ALLOWED_CODECS):
                    folder_mkv_list.append(f)
                    logging.info(f"Allowed MKV file added for processing: {f}")
                else:
                    logging.info(f"Skipping MKV file with unsupported codec: {f}")

        # Список остальных файлов (не MKV)
        folder_other_file_list = [f for f in all_files if not f.lower().endswith(".mkv") and "." in os.path.basename(f)]

        # Обработка каждого MKV-файла
        for mkv_file_path in folder_mkv_list:
            try:
                # Обновление текущего обрабатываемого файла
                processing_files[path] = os.path.basename(mkv_file_path)
                logging.info(f"Started muxing MKV file: {mkv_file_path}")
                
                mkv_mux_task(mkv_file_path, folder_other_file_list, font_list, path)
            except Exception as e:
                logging.error(f"Error processing MKV file {mkv_file_path}: {e}")
                continue

        # Удаление шрифтов, если настроено
        if DELETE_FONTS and os.path.exists(main_fonts_dir):
            try:
                shutil.rmtree(main_fonts_dir)
                Path(os.path.join(main_fonts_dir, ".ignore")).touch()
                logging.info(f"Deleted Fonts directory and created .ignore: {main_fonts_dir}")
            except Exception as e:
                logging.error(f"Failed to delete and recreate Fonts directory {main_fonts_dir}: {e}")

        # Обновление статуса директории на OK с логами
        logs = log_capture.get_logs()
        update_directory_status(path, "OK", logs=logs)
        logging.info(f"Successfully processed directory: {path}")

    except Exception as e:
        logging.error(f"Error processing directory {path}: {e}")
        # Обновление статуса директории на ERROR с логами
        logs = log_capture.get_logs()
        update_directory_status(path, "ERROR", logs=logs)

    finally:
        # Удаление обработчика логов
        root_logger.removeHandler(log_capture)
        # Очистка текущего файла из processing_files
        processing_files[path] = None
        # Удаление пустых директорий после обработки
        remove_empty_dirs(path)

def directory_changed_since_last_update(path, last_update_str):
    """
    Проверяет, изменялись ли файлы в директории с момента последнего обновления.
    :param path: путь к директории
    :param last_update_str: строка с временем последнего обновления
    :return: True, если файлы изменялись, иначе False
    """
    if not last_update_str:
        return True
    last_update = datetime.fromisoformat(last_update_str)
    newest_mtime = datetime.fromtimestamp(0)

    for root, _, files in os.walk(path):
        for f in files:
            full_path = os.path.join(root, f)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
                if mtime > newest_mtime:
                    newest_mtime = mtime
            except FileNotFoundError:
                continue

    return newest_mtime > last_update

def are_files_stable(path, wait_time=2):
    """
    Проверяет, стабилизировались ли файлы (не изменяются ли их размеры).
    :param path: путь к директории
    :param wait_time: время ожидания в секундах
    :return: True, если файлы стабилизировались, иначе False
    """
    initial_sizes = {}
    for root, _, files in os.walk(path):
        for f in files:
            full_path = os.path.join(root, f)
            try:
                size = os.path.getsize(full_path)
                if size == 0:
                    # Пустой файл, пропускаем из обработки
                    continue
                initial_sizes[full_path] = size
            except OSError:
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
    """
    Создаёт специальные директории Fonts и Extra с файлом .ignore, если их нет.
    :param base_path: путь к базовой директории
    :return: кортеж (fonts_dir, extra_dir)
    """
    fonts_dir = os.path.join(base_path, "Fonts")
    extra_dir = os.path.join(base_path, "Extra")

    for directory in [fonts_dir, extra_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            ignore_file = os.path.join(directory, ".ignore")
            Path(ignore_file).touch()
            logging.info(f"Created {os.path.basename(directory)} directory with .ignore: {directory}")

    return fonts_dir, extra_dir

def remove_empty_dirs(base_path):
    """
    Удаляет все пустые вложенные директории в base_path, содержащие только файлы .ignore, .DS_Store и т.д.
    Специальные директории 'Extra' и 'Fonts' не удаляются, но их вложенные директории обрабатываются.
    :param base_path: путь к базовой директории
    """
    base = Path(base_path)
    skip_dir_names = {"Extra", "Fonts"}
    ignored_files = {'.ignore', '.ds_store', '.gitignore', '.env'}

    # Определяем основные директории 'Extra' и 'Fonts'
    main_extra_dir = base / "Extra"
    main_fonts_dir = base / "Fonts"

    # Получаем все директории, отсортированные по глубине (самые вложенные первыми)
    dirs = sorted([d for d in base.rglob('*') if d.is_dir()], key=lambda p: len(p.parts), reverse=True)

    for dir_path in dirs:
        # Пропускаем только основные 'Extra' и 'Fonts' директории
        if dir_path == main_extra_dir or dir_path == main_fonts_dir:
            logging.info(f"Skipping main special directory: {dir_path}")
            continue

        try:
            # Получаем список всех файлов в директории (включая скрытые)
            all_files = [f for f in dir_path.iterdir() if f.is_file()]
            # Получаем список поддиректорий
            subdirs = [d for d in dir_path.iterdir() if d.is_dir()]

            logging.info(f"Checking directory: {dir_path}")
            logging.info(f"Contains files: {[f.name for f in all_files]}")
            logging.info(f"Contains subdirectories: {[d.name for d in subdirs]}")

            # Условия для удаления:
            # 1. Директория не содержит поддиректорий
            # 2. Все файлы в директории — это .ignore или .DS_Store (независимо от регистра и без лишних пробелов)
            if not subdirs:
                if all(f.name.lower().strip() in ignored_files for f in all_files):
                    try:
                        shutil.rmtree(dir_path)
                        logging.info(f"Removed empty directory: {dir_path}")
                    except Exception as e:
                        logging.error(f"Failed to remove directory {dir_path}: {e}")
                else:
                    logging.info(f"Directory {dir_path} contains other files: {[f.name for f in all_files]}")
            else:
                logging.info(f"Directory {dir_path} contains subdirectories, skipping")
        except Exception as e:
            logging.error(f"Error checking directory {dir_path}: {e}")
