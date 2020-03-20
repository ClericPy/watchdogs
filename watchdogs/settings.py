import logging
from asyncio import ensure_future, get_event_loop
from datetime import datetime
from json import dumps, loads
from logging.handlers import RotatingFileHandler

from databases import Database
from torequests.utils import (
    curlparse, escape, guess_interval, itertools_chain, json, parse_qs,
    parse_qsl, ptime, quote, quote_plus, slice_by_size, slice_into_pieces,
    split_n, timeago, ttime, unescape, unique, unquote, unquote_plus, urljoin,
    urlparse, urlsplit, urlunparse)
from uniparser.config import GlobalConfig
from uniparser.parsers import AsyncFrequency, UDFParser, Uniparser

from .background import background_loop, db_backup_handler
from .callbacks import CallbackHandler
from .config import Config, md5
from .crawler import crawl_once
from .models import Metas, RuleStorageDB

NotSet = object()


def get_valid_value(values: list, default=None, invalid=NotSet):
    for value in values:
        if value is not invalid:
            return value
    return default


def init_logger():
    logger = logging.getLogger('watchdogs')
    uniparser_logger = logging.getLogger('uniparser')
    uvicorn_logger = logging.getLogger('uvicorn')
    if Config.access_log:
        # fix https://github.com/encode/uvicorn/issues/523
        logging.getLogger('uvicorn.access').propagate = True
    formatter_str = "%(asctime)s %(levelname)-5s [%(name)s] %(filename)s(%(lineno)s): %(message)s"
    formatter = logging.Formatter(formatter_str, datefmt="%Y-%m-%d %H:%M:%S")
    logger.setLevel(logging.INFO)
    if not Config.mute_file_log:
        info_handler = RotatingFileHandler(
            Config.CONFIG_DIR / 'info.log',
            maxBytes=1024 * 1024 * Config.LOG_FILE_SIZE_MB['info'],
            backupCount=1,
            encoding=Config.ENCODING)
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(formatter)
        logger.addHandler(info_handler)
        uniparser_logger.addHandler(info_handler)

        error_handler = RotatingFileHandler(
            Config.CONFIG_DIR / 'error.log',
            maxBytes=1024 * 1024 * Config.LOG_FILE_SIZE_MB['error'],
            backupCount=1,
            encoding=Config.ENCODING)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
        uniparser_logger.addHandler(error_handler)

        server_handler = RotatingFileHandler(
            Config.CONFIG_DIR / 'server.log',
            maxBytes=1024 * 1024 * Config.LOG_FILE_SIZE_MB['server'],
            backupCount=1,
            encoding=Config.ENCODING)
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


async def setup_uniparser():
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
    await load_host_freqs()


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
    if Config.db_backup_function is None:
        Config.db_backup_function = default_db_backup_sqlite


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
    if Config.callback_handler is None:
        Config.callback_handler = CallbackHandler()
    workers = ', '.join(Config.callback_handler.callbacks_dict.keys())
    Config.logger.info(f'Current online callbacks:\n{workers}')


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


async def setup_background():
    loop_funcs = [db_backup_handler, crawl_once]
    ensure_future(background_loop(loop_funcs))


def setup_exception_handlers(app):
    for exc, callback in Config.exception_handlers:
        app.add_exception_handler(exc, callback)


async def setup_app(app):
    mute_loggers()
    await setup_uniparser()
    db = Config.db
    if db:
        await db.connect()
        from .models import create_tables
        create_tables(str(db.url))
        await setup_background()
        await setup_md5_salt()
        await setup_crawler()
        await refresh_token()
        setup_exception_handlers(app)
    Config.logger.info(f'App start success, CONFIG_DIR: {Config.CONFIG_DIR}')


async def release_app(app):
    if Config.db:
        await Config.db.disconnect()


async def default_db_backup_sqlite():
    current_time = datetime.now().strftime('%Y%m%d%H%M%S')
    for storage_path in Config.CONFIG_DIR.iterdir():
        if storage_path.name == 'storage.sqlite':
            import shutil
            from pathlib import Path
            backup_dir: Path = Config.CONFIG_DIR / 'backups'
            if not backup_dir.is_dir():
                backup_dir.mkdir()
            backup_path = backup_dir / f'storage-{current_time}.sqlite'
            # 3.6 has no get_running_loop
            loop = get_event_loop()
            # wait for copy
            future = loop.run_in_executor(None, shutil.copy, str(storage_path),
                                          str(backup_path))
            await future
            # remove overdue files
            backup_file_paths = sorted([i for i in backup_dir.iterdir()],
                                       key=lambda path: path.name,
                                       reverse=True)
            path_to_del = backup_file_paths[Config.backup_count:]
            for p in path_to_del:
                p.unlink()


def get_host_freq_list(host):
    freq = Uniparser._HOST_FREQUENCIES.get(host, None)
    if freq:
        return [freq.n, freq.interval]
    else:
        return [None, 0]


async def set_host_freq(host, n, interval):
    if n:
        Uniparser._HOST_FREQUENCIES[host] = AsyncFrequency(n, interval)
    else:
        Uniparser._HOST_FREQUENCIES.pop(host, None)
    await save_host_freqs()


async def save_host_freqs():
    items = {
        host: freq.to_list()
        for host, freq in Uniparser._HOST_FREQUENCIES.items()
    }
    await Config.metas.set('host_freqs', dumps(items))


async def load_host_freqs():
    host_freqs_str = await Config.metas.get('host_freqs', default='{}')
    host_freqs = loads(host_freqs_str)
    Uniparser._HOST_FREQUENCIES = {
        host: AsyncFrequency(*args) for host, args in host_freqs.items()
    }
