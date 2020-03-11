import logging
from asyncio import ensure_future
from logging.handlers import RotatingFileHandler

from databases import Database

from .config import Config, md5
from .crawler import background_loop
from .models import RuleStorageDB
from .callbacks import CallbackHandler


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
    from uniparser.parsers import Uniparser, AsyncFrequency
    from uniparser.config import GlobalConfig

    GlobalConfig.GLOBAL_TIMEOUT = Config.downloader_timeout
    Uniparser._DEFAULT_ASYNC_FREQUENCY = AsyncFrequency(
        *Config.DEFAULT_HOST_FREQUENCY)


def setup(
        db_url=None,
        password='',
        ignore_stdout_log=False,
        ignore_file_log=False,
        md5_salt=None,
        use_default_cdn=False,
):
    from uniparser.fastapi_ui.views import cdn_urls

    cdn_urls.update(Config.cdn_urls)
    Config.password = password
    Config.logger = init_logger(
        ignore_stdout_log=ignore_stdout_log, ignore_file_log=ignore_file_log)
    Config.md5_salt = md5_salt
    if not Config.cdn_urls:
        if use_default_cdn:
            # default online cdn
            Config.cdn_urls = {
                'VUE_JS_CDN': 'https://cdn.staticfile.org/vue/2.6.11/vue.min.js',
                'ELEMENT_CSS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/theme-chalk/index.css',
                'ELEMENT_JS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/index.js',
                'VUE_RESOURCE_CDN': 'https://cdn.staticfile.org/vue-resource/1.5.1/vue-resource.min.js',
                'CLIPBOARDJS_CDN': 'https://cdn.staticfile.org/clipboard.js/2.0.4/clipboard.min.js',
            }
        else:
            # local statics
            Config.cdn_urls = {
                'VUE_JS_CDN': '/static/js/vue.min.js',
                'ELEMENT_CSS_CDN': '/static/css/index.css',
                'ELEMENT_JS_CDN': '/static/js/index.js',
                'VUE_RESOURCE_CDN': '/static/js/vue-resource.min.js',
                'CLIPBOARDJS_CDN': '/static/js/clipboard.min.js',
            }

    setup_db(db_url)


async def setup_md5_salt():
    logger = Config.logger
    query = 'select `value` from metas where `key`="md5_salt"'
    result = await Config.db.fetch_one(query)
    exist_salt = result.value if result else None
    if Config.md5_salt is None:
        if exist_salt is None:
            # create new salt
            from time import time
            from random import random
            Config.md5_salt = md5(time() * random(), with_salt=False)
        else:
            # no need to update
            Config.md5_salt = exist_salt
            return
    elif Config.md5_salt == exist_salt:
        # no need to update
        return
    # need to update: new md5_salt from settings, or no exist_salt
    logger.critical(f'Setting md5_salt as {Config.md5_salt}, replaced into db.')
    query = 'replace into metas (`key`, `value`) values ("md5_salt", :md5_salt)'
    return await Config.db.execute(query, values={'md5_salt': Config.md5_salt})


async def setup_crawler():
    from uniparser import Crawler

    crawler = Crawler(storage=Config.rule_db)
    Config.logger.info(
        f'Downloader middleware installed: {crawler.uniparser.ensure_adapter(False).__class__.__name__}'
    )
    Config.crawler = crawler
    callback_handler = CallbackHandler()
    Config.callback_handler = callback_handler
    Config.logger.info(f'Current online callbacks:\n{callback_handler.workers}')


async def update_password(password=None):
    if password is not None:
        Config.password = password
    query = 'replace into metas (`key`, `value`) values ("admin", :password)'
    return await Config.db.execute(query, values={'password': Config.password})


async def refresh_token():
    if Config.password:
        await update_password()
    query = 'select `value` from metas where `key`="admin"'
    result = await Config.db.fetch_one(query)
    if result and result.value:
        Config.watchdog_auth = md5(result.value)


async def setup_app(app):
    setup_uniparser()
    db = Config.db
    if db:
        await db.connect()
        from .models import create_tables
        create_tables(str(db.url))
        await setup_md5_salt()
        # background_loop
        await setup_crawler()
        await refresh_token()
        ensure_future(background_loop())
    Config.logger.info(f'App start success, CONFIG_DIR: {Config.CONFIG_DIR}')


async def release_app(app):
    if Config.db:
        await Config.db.disconnect()
