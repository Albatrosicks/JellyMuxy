from config import get_config
import logging
import os

config = get_config()
CHS_LIST = config["Subtitle"]["Keyword"]["CHS"]
CHT_LIST = config["Subtitle"]["Keyword"]["CHT"]
JP_SC_LIST = config["Subtitle"]["Keyword"]["JP_SC"]
JP_TC_LIST = config["Subtitle"]["Keyword"]["JP_TC"]
JP_LIST = config["Subtitle"]["Keyword"]["JP"]
RU_LIST = config["Subtitle"]["Keyword"]["RU"]
ALLOWED_FONT_EXTENSIONS = config["Font"]["AllowedExtensions"]

def subtitle_info_checker(file_path):
    """
    Определяет информацию о субтитрах на основе пути к файлу.
    :param file_path: путь к файлу субтитров
    :return: словарь с информацией о субтитрах
    """
    sub_info = {
        "language": "",
        "mkv_language": "",
        "default_language": False,
        "forced_track": False
    }
    try:
        # Преобразуем путь к файлу в нижний регистр для сопоставления
        normalized_path = os.path.normpath(file_path).lower()

        # Определение языка на основе пути к файлу
        if os.path.sep.join(["sub", "jp"]) in normalized_path or "japanese" in normalized_path:
            sub_info["language"] = "Japanese"
            sub_info["mkv_language"] = "jpn"
        elif os.path.sep.join(["sub", "ru"]) in normalized_path or "russian" in normalized_path:
            sub_info["language"] = "Russian"
            sub_info["mkv_language"] = "rus"
        elif os.path.sep.join(["sub", "eng"]) in normalized_path or "english" in normalized_path:
            sub_info["language"] = "English"
            sub_info["mkv_language"] = "eng"
        else:
            sub_info["language"] = "Unknown"
            sub_info["mkv_language"] = "und"

        # Определение, является ли субтитр языком по умолчанию или принудительным
        basename = os.path.basename(file_path).lower()
        if "default" in basename:
            sub_info["default_language"] = True
            sub_info["forced_track"] = True

        logging.debug(f"Determined subtitle info for {file_path}: {sub_info}")

    except Exception as e:
        logging.error(f"Unexpected error in subtitle_info_checker for {file_path}: {e}")

    return sub_info

def is_font_file(f: str) -> bool:
    """
    Проверяет, является ли файл шрифтом по расширению.
    :param f: имя файла (путь)
    :return: True, если файл шрифт, иначе False
    """
    return any(f.lower().endswith(ext) for ext in ALLOWED_FONT_EXTENSIONS)
