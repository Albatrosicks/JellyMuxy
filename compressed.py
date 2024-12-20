import zipfile
import zlib
from pathlib import Path
import logging

def unzip(f: str, encoding: str) -> list:
    """
    Unzip a file and return the contents name in a list.
    :param f: original zip file name (path)
    :param encoding: encoding of the zip file
    :return: a list of the contents name
    """
    fonts_list = []
    with zipfile.ZipFile(f, 'r') as this_zip:
        for i in this_zip.namelist():
            try:
                decoded_name = i.encode('cp437').decode(encoding)
                fonts_list.append("Fonts/" + decoded_name)
                n = Path("Fonts/" + decoded_name)
            except UnicodeDecodeError:
                try:
                    decoded_name = i.encode('utf-8').decode(encoding)
                    fonts_list.append("Fonts/" + decoded_name)
                    n = Path("Fonts/" + decoded_name)
                except UnicodeDecodeError:
                    logging.error(f"Unsupported encoding for file in zip: {i}")
                    raise UnicodeDecodeError("Unsupported encoding, please manually zip the file...")
            try:
                if i.endswith('/'):
                    if not n.exists():
                        n.mkdir(parents=True, exist_ok=True)
                else:
                    with n.open('wb') as w:
                        w.write(this_zip.read(i))
            except zlib.error:
                logging.error(f"Unsupported compression for file: {i}")
                raise zlib.error("Unsupported compression, please manually zip the file...")
            except Exception as e:
                logging.error(f"Error extracting file {i} from zip {f}: {e}")
                raise e
    logging.info(f"Unzipped fonts from {f}: {fonts_list}")
    return fonts_list
