import logging
from asyncio import ensure_future, sleep, Lock, wait
from pathlib import Path
from databases import Database
from logging.handlers import RotatingFileHandler
import datetime



class GlobalConfig(object):
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


def setup_logger(ignore_stdout_log=False, ignore_file_log=False):
    logger = logging.getLogger('watchdog')
    formatter_str = "%(asctime)s %(levelname)-5s [%(name)s] %(filename)s(%(lineno)s): %(message)s"
    formatter = logging.Formatter(formatter_str, datefmt="%Y-%m-%d %H:%M:%S")
    logger.setLevel(logging.INFO)

    if not ignore_file_log:
        handler = RotatingFileHandler(
            GlobalConfig.CONFIG_DIR / 'info.log',
            maxBytes=1024 * 1024 * 5,
            backupCount=1)
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        handler = RotatingFileHandler(
            GlobalConfig.CONFIG_DIR / 'error.log',
            maxBytes=1024 * 1024 * 1,
            backupCount=1)
        handler.setLevel(logging.INFO)
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
        sqlite_path = GlobalConfig.CONFIG_DIR / 'storage.sqlite'
        db_url = f'sqlite:///{sqlite_path}'
    GlobalConfig.db = Database(db_url)


def setup_uniparser():
    from orjson import JSONDecodeError, dumps, loads
    from uniparser.config import GlobalConfig

    GlobalConfig.JSONDecodeError = JSONDecodeError
    GlobalConfig.json_dumps = dumps
    GlobalConfig.json_loads = loads


def setup(db_url=None,
          admin=None,
          password=None,
          ignore_stdout_log=False,
          ignore_file_log=False):
    GlobalConfig.admin = admin
    GlobalConfig.password = password
    setup_logger(
        ignore_stdout_log=ignore_stdout_log, ignore_file_log=ignore_file_log)
    setup_uniparser()
    setup_db(db_url)


async def crawl_once(tasks, db):
    # sqlite do not has datediff...
    query = tasks.select()
    todo = []
    now = datetime.datetime.now()
    async with GlobalConfig.db_lock:
        async for task in db.iterate(query=query):
            # print(dict(task), 'crawl_once')
            # not reach interval
            if (task.last_check_time + datetime.timedelta(
                    seconds=task.interval)) > now:
                # wait interval
                continue
            print(dict(task), 'start crawling')
            task.interval = 299
            # query = tasks.update()
            # values = {"name": "example1", "completed": True}
            # await db.execute(query=query, values=values)
    done, pending = wait(todo, timeout=GlobalConfig.default_crawler_timeout)
    async with GlobalConfig.db_lock:
        for task in done:
            pass

async def crawler_loop(tasks, db):
    while 1:
        await crawl_once(tasks, db)
        await sleep(GlobalConfig.check_interval)
        quit()


async def setup_app(app):
    db = GlobalConfig.db
    if db:
        await db.connect()
        from .models import tasks, create_tables
        create_tables(str(db.url))
        try:
            query = tasks.insert().prefix_with('OR IGNORE')
            values = {
                "name": "example1",
                "request_args": 'test1',
            }
            print(await db.execute(query=query, values=values))
        except Exception as e:
            print(e)
            pass
            # print(e.__class__.__name__, 1111111)IntegrityError
        # TODO async start crawler loop
        # crawler_loop
        ensure_future(crawler_loop(tasks, db))


async def release_app(app):
    if GlobalConfig.db:
        await GlobalConfig.db.disconnect()
