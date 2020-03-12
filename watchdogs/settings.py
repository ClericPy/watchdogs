import logging
from asyncio import ensure_future
from logging.handlers import RotatingFileHandler

from databases import Database

from .callbacks import CallbackHandler
from .config import Config, md5
from .crawler import background_loop
from .models import Metas, RuleStorageDB

NotSet = type('NotSet', (object,), {})


def get_valid_value(values: list, default=None, invalid=NotSet):
    for value in values:
        if value is not invalid:
            return value
    return default


def init_logger():
    logger = logging.getLogger('watchdogs')
    uniparser_logger = logging.getLogger('uniparser')
    uvicorn_logger = logging.getLogger('uvicorn')
    formatter_str = "%(asctime)s %(levelname)-5s [%(name)s] %(filename)s(%(lineno)s): %(message)s"
    formatter = logging.Formatter(formatter_str, datefmt="%Y-%m-%d %H:%M:%S")
    logger.setLevel(logging.INFO)
    if not Config.mute_file_log:
        info_handler = RotatingFileHandler(
            Config.CONFIG_DIR / 'info.log',
            maxBytes=1024 * 1024 * Config.LOG_FILE_SIZE_MB['info'],
            backupCount=1)
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(formatter)
        logger.addHandler(info_handler)
        uniparser_logger.addHandler(info_handler)

        error_handler = RotatingFileHandler(
            Config.CONFIG_DIR / 'error.log',
            maxBytes=1024 * 1024 * Config.LOG_FILE_SIZE_MB['error'],
            backupCount=1)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
        uniparser_logger.addHandler(error_handler)

        server_handler = RotatingFileHandler(
            Config.CONFIG_DIR / 'server.log',
            maxBytes=1024 * 1024 * Config.LOG_FILE_SIZE_MB['server'],
            backupCount=1)
        server_handler.setLevel(logging.INFO)
        server_handler.setFormatter(formatter)
        uvicorn_logger.addHandler(server_handler)

    if not Config.mute_std_log:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        uniparser_logger.addHandler(handler)
    return logger


def setup_db(db_url=None):
    if db_url is None:
        sqlite_path = Config.CONFIG_DIR / 'storage.sqlite'
        db_url = f'sqlite:///{sqlite_path}'
    Config.db = Database(db_url)
    Config.rule_db = RuleStorageDB(Config.db)
    Config.metas = Metas(Config.db)


def setup_uniparser():
    from torequests.utils import (
        curlparse, escape, guess_interval, itertools_chain, json, parse_qs,
        parse_qsl, ptime, quote, quote_plus, slice_by_size, slice_into_pieces,
        split_n, timeago, ttime, unescape, unique, unquote, unquote_plus,
        urljoin, urlparse, urlsplit, urlunparse)
    from uniparser.parsers import Uniparser, AsyncFrequency, UDFParser
    from uniparser.config import GlobalConfig

    UDFParser._GLOBALS_ARGS.update({
        'curlparse': curlparse,
        'escape': escape,
        'guess_interval': guess_interval,
        'itertools_chain': itertools_chain,
        'json': json,
        'parse_qs': parse_qs,
        'parse_qsl': parse_qsl,
        'ptime': ptime,
        'quote': quote,
        'quote_plus': quote_plus,
        'slice_by_size': slice_by_size,
        'slice_into_pieces': slice_into_pieces,
        'split_n': split_n,
        'timeago': timeago,
        'ttime': ttime,
        'unescape': unescape,
        'unique': unique,
        'unquote': unquote,
        'unquote_plus': unquote_plus,
        'urljoin': urljoin,
        'urlparse': urlparse,
        'urlsplit': urlsplit,
        'urlunparse': urlunparse,
    })
    GlobalConfig.GLOBAL_TIMEOUT = Config.downloader_timeout
    Uniparser._DEFAULT_ASYNC_FREQUENCY = AsyncFrequency(
        *Config.DEFAULT_HOST_FREQUENCY)


def setup(
        db_url=None,
        password='',
        md5_salt='',
        use_default_cdn=False,
):
    from uniparser.fastapi_ui.views import cdn_urls

    cdn_urls.update(Config.cdn_urls)
    Config.password = password
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
    exist_salt = await Config.metas.get('md5_salt', None)
    if not Config.md5_salt:
        if exist_salt:
            # no need to update
            Config.md5_salt = exist_salt
            return
        else:
            # create new salt
            from time import time
            from random import random
            Config.md5_salt = md5(time() * random(), with_salt=False)
    elif Config.md5_salt == exist_salt:
        # no need to update
        return
    # need to update: new md5_salt from settings, or no exist_salt
    logger.critical(f'Setting md5_salt as {Config.md5_salt}, replaced into db.')
    return await Config.metas.set('md5_salt', Config.md5_salt)


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
    return await Config.metas.set('admin', Config.password)


async def refresh_token():
    if Config.password:
        await update_password()
    password = await Config.metas.get('admin', '')
    if password:
        Config.watchdog_auth = md5(password)


def mute_loggers():
    names = ['', 'uvicorn', 'watchdogs', 'uniparser']
    logger = Config.logger
    if Config.mute_std_log:
        logger.info('Mute std logs')
        for name in names:
            _logger = logging.getLogger(name)
            old_handlers = _logger.handlers
            _logger.handlers = [
                i for i in old_handlers
                if i.__class__ is not logging.StreamHandler
            ]
            logger.info(
                f'[MUTE] log {name or "root"}: {old_handlers} => {_logger.handlers}'
            )
    if Config.mute_file_log:
        logger.info('Mute std logs')
        for name in names:
            _logger = logging.getLogger(name)
            old_handlers = _logger.handlers
            _logger.handlers = [
                i for i in old_handlers
                if i.__class__ is not RotatingFileHandler
            ]
            logger.info(
                f'[MUTE] log {name or "root"}: {old_handlers} => {_logger.handlers}'
            )


async def setup_app(app):
    mute_loggers()
    setup_uniparser()
    db = Config.db
    if db:
        await db.connect()
        from .models import create_tables
        create_tables(str(db.url))
        await setup_md5_salt()
        await setup_crawler()
        await refresh_token()
        ensure_future(background_loop())
    Config.logger.info(f'App start success, CONFIG_DIR: {Config.CONFIG_DIR}')


async def release_app(app):
    if Config.db:
        await Config.db.disconnect()
