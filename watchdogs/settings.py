import logging
from asyncio import ensure_future, get_event_loop
from datetime import datetime
from functools import lru_cache
from json import dumps, loads
from logging.handlers import RotatingFileHandler

from uniparser.parsers import AsyncFrequency, Uniparser

from .config import Config, NotSet, ensure_dir, md5


def get_valid_value(values: list, default=None, invalid=NotSet):
    for value in values:
        if value is not invalid:
            return value
    return default


def get_file_handler(file_name,
                     file_size_mb=2,
                     backup_count=1,
                     level=logging.INFO):
    handler = RotatingFileHandler(
        Config.CONFIG_DIR / file_name,
        maxBytes=1024 * 1024 * Config.LOGGING_FILE_CONFIG.get(
            file_name, {}).get('file_size_mb', file_size_mb),
        backupCount=Config.LOGGING_FILE_CONFIG.get(file_name, {}).get(
            'backup_count', backup_count),
        encoding=Config.ENCODING)
    handler.setLevel(
        Config.LOGGING_FILE_CONFIG.get(file_name, {}).get('level', level))
    handler.setFormatter(Config.DEFAULT_LOGGER_FORMATTER)
    return handler


def get_stream_handler(level=logging.INFO):
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(Config.DEFAULT_LOGGER_FORMATTER)
    return handler


def setup_logger():
    watchdogs_logger = logging.getLogger('watchdogs')
    uniparser_logger = logging.getLogger('uniparser')
    uvicorn_logger = logging.getLogger('uvicorn')
    if not Config.mute_file_log:
        info_handler = get_file_handler('info.log')
        watchdogs_logger.addHandler(info_handler)
        uniparser_logger.addHandler(info_handler)

        error_handler = get_file_handler('error.log')
        watchdogs_logger.addHandler(error_handler)
        uniparser_logger.addHandler(error_handler)

        server_handler = get_file_handler('server.log')
        uvicorn_logger.addHandler(server_handler)

    if not Config.mute_std_log:
        handler = get_stream_handler()
        watchdogs_logger.addHandler(handler)
        uniparser_logger.addHandler(handler)
        uvicorn_logger.addHandler(handler)
    return watchdogs_logger


def setup_models():
    from databases import Database
    # lazy import models to config cache size, means set cache after run main.init_app
    from .models import Metas, RuleStorageDB, create_tables

    Config.db = Database(Config.db_url)
    Config.rule_db = RuleStorageDB(Config.db)
    Config.metas = Metas(Config.db)
    # if Config.db_backup_function is None and Config.db_url.startswith(
    #         'sqlite:///'):
    #     Config.db_backup_function = default_db_backup_sqlite
    create_tables(str(Config.db.url))


async def setup_uniparser():
    import re
    import datetime
    import math
    import random
    from torequests.utils import (curlparse, escape, guess_interval,
                                  itertools_chain, json, parse_qs, parse_qsl,
                                  ptime, quote, quote_plus, slice_by_size,
                                  slice_into_pieces, split_n, timeago, ttime,
                                  unescape, unique, unquote, unquote_plus,
                                  urljoin, urlparse, urlsplit, urlunparse)
    from uniparser.utils import TorequestsAiohttpAsyncAdapter
    from uniparser.parsers import UDFParser
    from uniparser.config import GlobalConfig
    import uniparser.fastapi_ui
    UDFParser._GLOBALS_ARGS.update({
        're': re,
        'datetime': datetime,
        'curlparse': curlparse,
        'math': math,
        'random': random,
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
    Config.uniparser = Uniparser(
        request_adapter=TorequestsAiohttpAsyncAdapter())
    uniparser.fastapi_ui.views.uni = Config.uniparser


def setup_cdn_urls(use_default_cdn=False):
    from uniparser.fastapi_ui.views import cdn_urls

    if not Config.cdn_urls:
        # while cdn_urls not set, check use default cdn or static files.
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
    # overwrite uniparser's cdn
    cdn_urls.update(Config.cdn_urls)


def setup_lru_cache():
    Config._md5 = lru_cache(maxsize=Config.md5_cache_maxsize)(Config._md5)
    Config.get_sign = lru_cache(maxsize=Config.sign_cache_maxsize)(
        Config.get_sign)


def setup(use_default_cdn=False):
    setup_logger()
    setup_lru_cache()
    setup_cdn_urls(use_default_cdn=use_default_cdn)
    setup_models()


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
            from uuid import uuid1
            Config.md5_salt = uuid1().hex
    elif Config.md5_salt == exist_salt:
        # no need to update
        return
    # need to update: new md5_salt from settings, or no exist_salt
    logger.critical(f'Setting md5_salt as {Config.md5_salt}, replaced into db.')
    return await Config.metas.set('md5_salt', Config.md5_salt)


async def setup_crawler():
    from uniparser import Crawler
    from .callbacks import CallbackHandler

    crawler = Crawler(uniparser=Config.uniparser, storage=Config.rule_db)
    Config.crawler = crawler
    if Config.callback_handler is None:
        Config.callback_handler = CallbackHandler()
    workers = ', '.join(Config.callback_handler.callbacks_dict.keys())
    Config.logger.info(f'Current online callbacks: {workers}')


async def update_password(password=None):
    if password is not None:
        Config.password = password
    return await Config.metas.set('admin', Config.password)


async def refresh_token():
    if Config.password:
        await update_password()
        password = Config.password
    else:
        password = await Config.metas.get('admin', '')
    if password:
        Config.watchdog_auth = md5(password)


async def setup_background():
    from .crawler import crawl_once
    from .background import background_loop, db_backup_handler
    Config.background_funcs.append(crawl_once)
    if Config.db_backup_function:
        Config.background_funcs.append(db_backup_handler)
    Config.background_task = ensure_future(
        background_loop(Config.background_funcs))


def setup_exception_handlers(app):
    for exc, callback in Config.exception_handlers:
        app.add_exception_handler(exc, callback)


def setup_middleware(app):
    for middleware in Config.middlewares:
        app.add_middleware(**middleware)


def mute_noise_logger():
    # uvicorn will set new handler for root logger and access logger after app launched.
    logging.getLogger('').handlers.clear()
    if Config.uvicorn_kwargs['access_log']:
        # fix https://github.com/encode/uvicorn/issues/523
        access_logger = logging.getLogger('uvicorn.access')
        access_logger.propagate = True
        access_logger.handlers.clear()


async def setup_app(app):
    mute_noise_logger()
    db = Config.db
    if not db:
        raise RuntimeError('No database?')
    await db.connect()
    await setup_md5_salt()
    # refresh_token should be after setup_md5_salt
    await refresh_token()
    setup_exception_handlers(app)
    setup_middleware(app)
    # 1
    await setup_uniparser()
    # 2
    await setup_crawler()
    # 3
    await setup_background()
    Config.logger.info(f'App start success, CONFIG_DIR: {Config.CONFIG_DIR}')


async def release_app(app):
    Config.is_shutdown = True
    if Config.background_task and not Config.background_task.done():
        Config.background_task.cancel()
    if Config.db:
        await Config.db.disconnect()


async def default_db_backup_sqlite():
    current_time = datetime.now().strftime('%Y%m%d%H%M%S')
    for storage_path in Config.CONFIG_DIR.iterdir():
        if storage_path.name == 'storage.sqlite':
            import shutil
            from pathlib import Path
            backup_dir: Path = ensure_dir(Config.CONFIG_DIR / 'backups')
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
            path_to_del = backup_file_paths[Config.db_backup_count:]
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
