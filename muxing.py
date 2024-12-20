import os
import json
import shutil
import logging
import subprocess
from pymkv import MKVFile, MKVTrack
from pathlib import Path
from subtitle_utils import subtitle_info_checker
from config import get_config

config = get_config()
DELETE_FONTS = config["TaskSettings"]["DeleteFonts"]
DELETE_ORIGINAL_MKV = config["TaskSettings"]["DeleteOriginalMKV"]
DELETE_ORIGINAL_MKA = config["TaskSettings"]["DeleteOriginalMKA"]
DELETE_SUB = config["TaskSettings"]["DeleteSubtitle"]
SUFFIX_NAME = config["TaskSettings"].get("OutputSuffixName", "_Jelly")

ALLOWED_CODECS = config.get("AllowedCodecs", ["HEVC", "AVC"])

def is_allowed_codec(file_path, allowed_codecs):
    """
    Проверяет, используется ли в файле разрешённый кодек.
    :param file_path: путь к MKV-файлу
    :param allowed_codecs: список разрешённых кодеков
    :return: True, если используется разрешённый кодек, иначе False
    """
    cmd = ["mkvmerge", "-J", file_path]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        info = json.loads(output)
        for track in info.get("tracks", []):
            if track.get("type") == "video":
                codec = track.get("codec", "").upper()
                for allowed in allowed_codecs:
                    if allowed.upper() in codec:
                        return True
        return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to check codec for {file_path}: {e}")
        return False
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error for {file_path}: {e}")
        return False

def mkv_mux_task(mkv_file_path: str, folder_other_file_list: list, font_list: list, base_path: str):
    """
    Выполняет muxing MKV-файла с субтитрами и шрифтами, а затем перемещает его при необходимости.
    :param mkv_file_path: путь к исходному MKV-файлу
    :param folder_other_file_list: список других файлов в директории
    :param font_list: список шрифтов
    :param base_path: путь к базовой директории
    """
    mkv_dir, mkv_file_name = os.path.split(mkv_file_path)
    mkv_name_no_extension = mkv_file_name.rsplit('.', 1)[0]

    logging.info(f"Started muxing: {mkv_file_name}")

    this_task = MKVFile(mkv_file_path)

    delete_list = []
    move_list = []

    original_final_name = os.path.join(mkv_dir, mkv_name_no_extension + ".mkv")
    new_mkv_name = os.path.join(mkv_dir, mkv_name_no_extension + SUFFIX_NAME + ".mkv")

    sub_track_count = 0
    subtitle_extensions = (".ass", ".srt")

    for item in folder_other_file_list:
        if mkv_name_no_extension in os.path.basename(item):
            if item.lower().endswith(subtitle_extensions):
                sub_info = subtitle_info_checker(item)
                if sub_info["language"] != "":
                    track_name = sub_info["language"]
                    sub_track = MKVTrack(
                        item,
                        track_name=track_name,
                        default_track=sub_info["default_language"],
                        language=sub_info["mkv_language"],
                        forced_track=sub_info["forced_track"]
                    )
                    this_task.add_track(sub_track)
                    sub_track_count += 1
                    if DELETE_SUB:
                        delete_list.append(item)
                        logging.info(f"Marked subtitle for deletion: {item}")
                    else:
                        move_list.append(item)
                        logging.info(f"Marked subtitle for moving: {item}")
                    logging.debug(f"Added subtitle track: {track_name}, Language: {sub_info['mkv_language']}")
            elif item.lower().endswith(".mka"):
                this_task.add_track(item)
                if DELETE_ORIGINAL_MKA:
                    delete_list.append(item)
                    logging.info(f"Marked audio for deletion: {item}")
                else:
                    move_list.append(item)
                    logging.info(f"Marked audio for moving: {item}")

    if sub_track_count == 0:
        # Не нашли субтитров, проверим все *.ass и *.srt
        all_subs = [f for f in folder_other_file_list if f.lower().endswith(subtitle_extensions)]
        for sub_file in all_subs:
            sub_info = subtitle_info_checker(sub_file)
            if sub_info["language"] != "":
                track_name = sub_info["language"]
                sub_track = MKVTrack(
                    sub_file,
                    track_name=track_name,
                    default_track=sub_info["default_language"],
                    language=sub_info["mkv_language"],
                    forced_track=sub_info["forced_track"]
                )
                this_task.add_track(sub_track)
                sub_track_count += 1
                if DELETE_SUB:
                    delete_list.append(sub_file)
                    logging.info(f"Marked subtitle (fallback) for deletion: {sub_file}")
                else:
                    move_list.append(sub_file)
                    logging.info(f"Marked subtitle (fallback) for moving: {sub_file}")
                logging.debug(f"Added fallback subtitle track: {track_name}, Language: {sub_info['mkv_language']}")

    if sub_track_count == 1:
        for track in this_task.tracks:
            if track.track_type == "subtitles":
                track.default_track = True
                logging.info(f"Set default subtitle track: {track.file_path}")

    # Добавляем шрифты
    for font in font_list:
        font_path = font
        if os.path.exists(font_path):
            this_task.add_attachment(font_path)
            logging.info(f"Added font attachment: {font_path}")
        else:
            logging.warning(f"Font file does not exist: {font_path}")

    # Обработка оригинального MKV
    if DELETE_ORIGINAL_MKV:
        delete_list.append(mkv_file_path)
        logging.info(f"Marked for deletion: {mkv_file_path}")

    # Выполняем muxing
    try:
        this_task.mux(new_mkv_name, silent=True)
        logging.info(f"Muxed successfully: {new_mkv_name}")
    except subprocess.CalledProcessError as e:
        logging.error(f"MKVMerge error for {mkv_file_path}: {e}")
        raise e

    # Создаём Extra директорию, если не существует
    extra_dir = os.path.join(base_path, "Extra")
    if not os.path.exists(extra_dir):
        os.makedirs(extra_dir, exist_ok=True)
        Path(os.path.join(extra_dir, ".ignore")).touch()
        logging.info(f"Created Extra directory with .ignore: {extra_dir}")

    # Перемещаем файлы в Extra
    for f in move_list:
        if os.path.exists(f):
            dest = os.path.join(extra_dir, os.path.basename(f))
            logging.info(f"Moving file {f} to {dest}")
            try:
                shutil.move(f, dest)
                logging.info(f"Moved file {f} to {dest}")
            except Exception as ex:
                logging.error(f"Failed to move file {f} to {dest}: {ex}")
        else:
            logging.warning(f"File {f} does not exist before move operation.")

    # Удаляем файлы из delete_list
    for f in delete_list:
        if os.path.exists(f):
            logging.info(f"Deleting file {f}")
            try:
                os.remove(f)
                logging.info(f"Deleted file {f}")
            except Exception as ex:
                logging.error(f"Failed to delete file {f}: {ex}")
        else:
            logging.warning(f"File {f} not found for deletion.")

    # Переименовываем новый mkv обратно
    if os.path.exists(new_mkv_name):
        if os.path.exists(original_final_name):
            try:
                os.remove(original_final_name)
                logging.info(f"Removed existing original mkv: {original_final_name}")
            except Exception as ex:
                logging.error(f"Failed to remove existing original mkv {original_final_name}: {ex}")
        try:
            os.rename(new_mkv_name, original_final_name)
            logging.info(f"Renamed {new_mkv_name} to {original_final_name}")
        except Exception as ex:
            logging.error(f"Failed to rename {new_mkv_name} to {original_final_name}: {ex}")

    logging.info(f"Finished processing mkv: {mkv_file_name}")

    # Дополнительный функционал для категории "movies":
    category_path = Path(base_path).parent
    if "movies" in category_path.name.lower():
        # Предполагается структура: ROOT_DIR/movies/<MovieName>/<AnyMKVName>.mkv
        # После mux: переместить в ROOT_DIR/movies/<MovieName>.mkv и удалить директорию фильма
        movie_dir_name = Path(base_path).name
        final_movie_name = movie_dir_name + ".mkv"
        src = os.path.join(base_path, original_final_name)  # Используем original_final_name
        dest = os.path.join(category_path, final_movie_name)
        logging.info(f"Detected 'movies' category. Moving {src} to {dest} and removing {base_path}")
        try:
            shutil.move(src, dest)
            logging.info(f"Moved movie to {dest}")
            # Удаляем директорию фильма
            shutil.rmtree(base_path)
            logging.info(f"Deleted movie directory: {base_path}")
        except Exception as e:
            logging.error(f"Failed to move movie or remove directory {base_path}: {e}")
