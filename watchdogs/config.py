from logging import getLogger
from operator import itemgetter
from pathlib import Path
from time import time
from traceback import format_exc
from typing import Any, Callable

from databases import Database
from fastapi import Request
from frequency_controller import AsyncFrequency
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from torequests.utils import md5 as _md5
from torequests.utils import parse_qsl, quote_plus, urlparse
from uniparser.crawler import RuleStorage

from .callbacks import CallbackHandlerBase

logger = getLogger('watchdogs')


def md5(obj, n=32, with_salt=True):
    if not with_salt:
        return _md5(obj, n=n)
    salt = Config.md5_salt
    if not salt:
        raise ValueError('Config.md5_salt should not be null')
    return _md5(f'{obj}{salt}', n=n)


async def md5_checker(obj, target, freq=False):
    if freq:
        async with Config.check_pwd_freq:
            # anti guessing password
            return md5(obj) == target
    else:
        # may get a cache
        return md5(obj) == target


# @app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    trace_id = str(int(time() * 1000))
    err_name = exc.__class__.__name__
    err_value = str(exc)
    msg = f'{err_name}({err_value}) trace_id: {trace_id}:\n{format_exc()}'
    logger.error(msg)
    return JSONResponse(
        status_code=500,
        content={
            "message": f"Oops! {err_name}.",
            "trace_id": trace_id
        },
    )


def ensure_dir(path: Path):
    if isinstance(path, str):
        path = Path(path)
    if path.is_dir():
        return path
    else:
        paths = list(reversed(path.parents))
        paths.append(path)
        p: Path
        for p in paths:
            if not p.is_dir():
                p.mkdir()
        return path


def get_query_sign(query):
    params = dict(parse_qsl(query, keep_blank_values=True))
    given_sign = params.pop('sign', '')
    sorted_query = sorted(params.items(), key=itemgetter(0))
    valid_sign = md5(sorted_query)
    return given_sign, valid_sign


def get_url_sign(url):
    return get_query_sign(urlparse(url).query)


async def auth_checker(request: Request, call_next):
    # {'type': 'http', 'http_version': '1.1', 'server': ('127.0.0.1', 9901), 'client': ('127.0.0.1', 7037), 'scheme': 'http', 'method': 'GET', 'root_path': '', 'path': '/auth', 'raw_path': b'/auth', 'query_string': b'', 'headers': [(b'host', b'127.0.0.1:9901'), (b'connection', b'keep-alive'), (b'sec-fetch-dest', b'image'), (b'user-agent', b'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36'), (b'dnt', b'1'), (b'accept', b'image/webp,image/apng,image/*,*/*;q=0.8'), (b'sec-fetch-site', b'same-origin'), (b'sec-fetch-mode', b'no-cors'), (b'referer', b'http://127.0.0.1:9901/auth'), (b'accept-encoding', b'gzip, deflate, br'), (b'accept-language', b'zh-CN,zh;q=0.9'), (b'cookie', b'ads_id=lakdsjflakjdf; _ga=GA1.1.1550108461.1583462251')], 'fastapi_astack': <contextlib.AsyncExitStack object at 0x00000165BE69EEB8>, 'app': <fastapi.applications.FastAPI object at 0x00000165A7B738D0>}
    query_string = request.scope.get('query_string', b'').decode('u8')
    path = request.scope['path']
    is_valid_cookie = Config.watchdog_auth != request.cookies.get(
        'watchdog_auth', '')
    if path != '/auth' and (not Config.watchdog_auth or is_valid_cookie):
        resp = RedirectResponse(
            f'/auth?redirect={quote_plus(request.scope["path"])}', 302)
        resp.set_cookie('watchdog_auth', '')
        return resp
    elif 'sign=' in query_string:
        given_sign, valid_sign = get_query_sign(query_string)
        if given_sign != valid_sign:
            return JSONResponse(
                status_code=400,
                content={
                    "message": 'signature expired',
                },
            )
    return await call_next(request)


class Config:
    CONFIG_DIR: Path = ensure_dir(Path.home() / 'watchdogs')
    ENCODING = 'utf-8'
    # db_url defaults to sqlite://
    db_url: str = ''
    db: Database = None
    logger = logger
    password: str = ''
    rule_db: RuleStorage = None
    metas = None
    check_interval: int = 60
    default_interval: int = 5 * 60
    default_crawler_timeout: int = 30
    downloader_timeout: int = 15
    watchdog_auth: str = ''
    md5_salt: str = ''
    crawler = None
    # anti brute force attack
    check_pwd_freq = AsyncFrequency(1, 3)
    # for anti-crawl frequency
    DEFAULT_HOST_FREQUENCY = (1, 1)
    cdn_urls: dict = {}
    callback_handler: CallbackHandlerBase = None
    access_log: bool = True
    mute_std_log = False
    mute_file_log = False
    LOG_FILE_SIZE_MB = {'info': 2, 'error': 5, 'server': 2}
    uvicorn_kwargs: dict = {'access_log': True, 'port': 9901}
    # check interval 60s, so format do use %M , backup every 12 hours. this pattern may miss for crawl cost more than 60s.
    # db_backup_time: str = '%H:%M==00:00|%H:%M==12:00'
    db_backup_time: str = '%H:%M==00:00'
    backup_count: int = 4
    db_backup_function: Callable[..., Any] = None
    exception_handlers: list = [
        (Exception, exception_handler),
    ]
    middlewares = [{
        'middleware_class': BaseHTTPMiddleware,
        'dispatch': auth_checker
    }]
