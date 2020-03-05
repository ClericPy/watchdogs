from asyncio import Lock
from pathlib import Path
from databases import Database
from logging import Logger


class Config(object):
    CONFIG_DIR = Path.home() / 'watchdogs'
    if not CONFIG_DIR.is_dir():
        CONFIG_DIR.mkdir()
    db: Database = None
    logger: Logger = None
    admin = None
    password = None
    rule_db = None
    check_interval = 60
    default_interval = 5 * 60
    default_crawler_timeout = 30
    downloader_timeout = 15
    db_lock = Lock()
    # for anti-crawl frequency
    default_host_frequency = (1, 1)
