import logging
from asyncio import ensure_future
from logging.handlers import RotatingFileHandler

from databases import Database

from .config import Config
from .crawler import crawler_loop
from .models import RuleStorageDB


def init_logger(ignore_stdout_log=False, ignore_file_log=False):
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

    GlobalConfig.GLOBAL_TIMEOUT = 30


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
        try:
            query = tasks.insert().prefix_with('OR IGNORE')
            values = {
                "name": "example1",
                "request_args": '{"method":"get","url":"http://httpbin.org/forms/post","headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"}}',
            }
            print(await db.execute(query=query, values=values))
        except Exception as e:
            print(e)
            pass
            # print(e.__class__.__name__, 1111111)IntegrityError
        from .models import CrawlerRule
        try:

            try:
                await Config.rule_db.add_crawler_rule('{"name":"HelloWorld","request_args":{"method":"get","url":"http://httpbin.org/forms/post","headers":{"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36"}},"parse_rules":[{"name":"text","chain_rules":[["css","p","$text"],["python","getitem","[0]"]],"childs":""}],"regex":"","encoding":""}')
            except:
                import traceback
                traceback.print_exc()
        except Exception as e:
            print(e)
            pass


async def release_app(app):
    if Config.db:
        await Config.db.disconnect()
