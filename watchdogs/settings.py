import datetime
import logging
from asyncio import ensure_future, sleep, wait
from logging.handlers import RotatingFileHandler

from databases import Database
from uniparser.crawler import Crawler

from .config import Config


def setup_logger(ignore_stdout_log=False, ignore_file_log=False):
    logger = logging.getLogger('watchdog')
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
        sqlite_path = Config.CONFIG_DIR / 'storage.sqlite'
        db_url = f'sqlite:///{sqlite_path}'
    Config.db = Database(db_url)


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
    Config.admin = admin
    Config.password = password
    setup_logger(
        ignore_stdout_log=ignore_stdout_log, ignore_file_log=ignore_file_log)
    setup_uniparser()
    setup_db(db_url)


async def crawl_once(tasks, crawler):
    db = crawler.storage.db
    # sqlite do not has datediff...
    query = tasks.select()
    todo = []
    now = datetime.datetime.now()
    async with Config.db_lock:
        async for task in db.iterate(query=query):
            # print(dict(task), 'crawl_once')
            # not reach interval
            if task.last_check_time + datetime.timedelta(
                    seconds=task.interval) > now:
                # wait interval
                continue
            print(dict(task), 'start crawling')
            # task.interval = 299
            # query = tasks.update()
            # values = {"name": "example1", "completed": True}
            # await db.execute(query=query, values=values)
    return
    done, pending = wait(todo, timeout=Config.default_crawler_timeout)
    async with Config.db_lock:
        for task in done:
            pass


async def crawler_loop(tasks, db):
    from .models import RuleStorageDB
    rule_db = RuleStorageDB(db)
    crawler = Crawler(storage=rule_db)
    while 1:
        await crawl_once(tasks, crawler)
        await sleep(Config.check_interval)


async def setup_app(app):
    db = Config.db
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
    if Config.db:
        await Config.db.disconnect()
