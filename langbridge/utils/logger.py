import logging
from logging.handlers import RotatingFileHandler
import os

LOCAL_LOG_DIR = './'

def get_root_logger():
    """Returns the root logger object ("")

    :return: Root Logger
    """
    return logging.getLogger('')

def empty_file(file_path):
    """Empty the contents of a file.

    :param file_path: Path to the file to be emptied.
    """
    with open(file_path, 'w'):
        pass

def setup_file_logging():
    os.makedirs(LOCAL_LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOCAL_LOG_DIR, 'app.log')
    if os.path.exists(log_file):
        empty_file(log_file)
    log_formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(log_formatter)
    logging.basicConfig(level=logging.ERROR
                        ,handlers=[file_handler]
                        )
