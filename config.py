import os
import json

REQUIRED_CONFIG = ["TaskSettings", "Font", "Subtitle", "mkvmerge", "multiprocessing"]

def make_default_config(config_path):
    new_config = {
        "TaskSettings": {
            "DeleteFonts": False,
            "DeleteOriginalMKV": False,
            "DeleteOriginalMKA": False,
            "DeleteSubtitle": False,
            "OutputSuffixName": "_Plex"
        },
        "Font": {
            # Подразумеваем, что на Linux путь к unrar в PATH или /usr/bin/unrar
            "AllowedExtensions": [".ttf", ".otf", ".ttc"],
            "Unrar_Path": "/usr/bin/unrar"
        },
        "Subtitle": {
            "Keyword": {
                "CHS": [".chs", ".sc", "[chs]", "[sc]", ".gb", "[gb]"],
                "CHT": [".cht", ".tc", "[cht]", "[tc]", "big5", "[big5]"],
                "JP_SC": [".jpsc", "[jpsc]", "jp_sc", "[jp_sc]", "chs&jap", "简日"],
                "JP_TC": [".jptc", "[jptc]", "jp_tc", "[jp_tc]", "cht&jap", "繁日"],
                "JP": [".jp", ".jpn", ".jap", "[jp]", "[jpn]", "[jap]"],
                "RU": [".ru", ".rus", "[ru]", "[rus]"]
            },
            "DefaultLanguage": "chs",
            "ShowSubtitleAuthorInTrackName": True
        },
        "mkvmerge": {
            # mkvmerge на Linux обычно в PATH, например /usr/bin/mkvmerge
            "path": "/usr/bin/mkvmerge"
        },
        "multiprocessing": {
            "thread_count": 24
        }
    }

    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    with open(config_path, "w", encoding='utf-8') as output:
        json.dump(new_config, output, indent=2, ensure_ascii=False)
    print(f"Default config file has been generated at {config_path}, please check and modify it if necessary.")

def get_config(config_path=None) -> dict:
    # Если путь к конфигу не задан, читаем из переменной окружения или берём /config/config.json
    if config_path is None:
        config_dir = os.environ.get("CONFIG_DIR", "/config")
        config_path = os.path.join(config_dir, "config.json")

    if not os.path.exists(config_path):
        print("Configuration file does not exist, creating default settings...")
        make_default_config(config_path)

    with open(config_path, "r", encoding='utf-8') as f:
        local_config = json.load(f)

    if any(item not in local_config.keys() for item in REQUIRED_CONFIG):
        raise ValueError("Config file does not meet requirements")

    return local_config
