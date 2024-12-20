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
            "OutputSuffixName": "_Jelly"
        },
        "Font": {
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
            "path": "/usr/bin/mkvmerge"
        },
        "multiprocessing": {
            "thread_count": 24
        },
        "AllowedCodecs": ["HEVC"]
    }

    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    with open(config_path, "w", encoding='utf-8') as output:
        json.dump(new_config, output, indent=2, ensure_ascii=False)
    print(f"Default config file generated at {config_path}")

def get_config(config_path=None) -> dict:
    if config_path is None:
        config_dir = os.environ.get("CONFIG_DIR", "/config")
        config_path = os.path.join(config_dir, "config.json")

    if not os.path.exists(config_path):
        print("Config file does not exist, creating default...")
        make_default_config(config_path)

    with open(config_path, "r", encoding='utf-8') as f:
        local_config = json.load(f)

    if any(item not in local_config.keys() for item in REQUIRED_CONFIG):
        raise ValueError("Config file does not meet requirements")

    return local_config
