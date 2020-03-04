import logging
from asyncio import ensure_future
from logging.handlers import RotatingFileHandler

from databases import Database

from .config import Config
from .crawler import crawler_loop
from .models import RuleStorageDB


def init_logger(ignore_stdout_log=False, ignore_file_log=False):
    logger = logging.getLogger('watchdogs')
    formatter_str = "%(asctime)s %(levelname)-5s [%(name)s] %(filename)s(%(lineno)s): %(message)s"
    formatter = logging.Formatter(formatter_str, datefmt="%Y-%m-%d %H:%M:%S")
    logger.setLevel(logging.INFO)

    if not ignore_file_log:
        handler = RotatingFileHandler(
            Config.CONFIG_DIR / 'info.log',
            maxBytes=1024 * 1024 * 5,
            backupCount=1)
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        handler = RotatingFileHandler(
            Config.CONFIG_DIR / 'error.log',
            maxBytes=1024 * 1024 * 1,
            backupCount=1)
        handler.setLevel(logging.ERROR)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if not ignore_stdout_log:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def setup_db(db_url=None):
    if db_url is None:
        sqlite_path = Config.CONFIG_DIR / 'storage.sqlite'
        db_url = f'sqlite:///{sqlite_path}'
    Config.db = Database(db_url)
    Config.rule_db = RuleStorageDB(Config.db)


def setup_uniparser():
    from uniparser.config import GlobalConfig

    GlobalConfig.GLOBAL_TIMEOUT = Config.downloader_timeout


def setup(db_url=None,
          admin=None,
          password=None,
          ignore_stdout_log=False,
          ignore_file_log=False):
    Config.admin = admin
    Config.password = password
    Config.logger = init_logger(
        ignore_stdout_log=ignore_stdout_log, ignore_file_log=ignore_file_log)
    setup_uniparser()
    setup_db(db_url)


async def setup_app(app):
    db = Config.db
    if db:
        await db.connect()
        from .models import tasks, create_tables
        create_tables(str(db.url))
        # crawler_loop
        ensure_future(crawler_loop(tasks, db))


async def release_app(app):
    if Config.db:
        await Config.db.disconnect()
