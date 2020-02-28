from asyncio import Lock
import logging
from pathlib import Path


class Config(object):
    CONFIG_DIR = Path.home() / 'watchdogs'
    if not CONFIG_DIR.is_dir():
        CONFIG_DIR.mkdir()
    db = None
    admin = None
    password = None
    logger = logging.getLogger('watchdog')
    check_interval = 60
    default_interval = 5 * 60
    default_crawler_timeout = 60
    db_lock = Lock()
