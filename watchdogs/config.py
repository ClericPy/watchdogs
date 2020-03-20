from logging import getLogger
from pathlib import Path
from time import time
from traceback import format_exc
from typing import Any, Callable

from databases import Database
from fastapi import Cookie, Header, Request
from frequency_controller import AsyncFrequency
from starlette.responses import JSONResponse, RedirectResponse
from torequests.utils import md5 as _md5
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


async def md5_checker(string, target, freq=True):
    if freq:
        async with Config.check_pwd_freq:
            # anti guessing password
            return md5(string) == target
    else:
        # may get a cache
        return md5(string) == target


class InvalidCookieError(Exception):
    '''bad cookie redirect to /auth'''


async def check_cookie(watchdog_auth: str = Cookie('')):
    if Config.watchdog_auth and watchdog_auth != Config.watchdog_auth:
        raise InvalidCookieError()


class InvalidTokenError(Exception):
    '''bad token return text: signature expired'''


async def check_token(tag: str = '',
                      sign: str = '',
                      host: str = Header('', alias='Host')):
    valid = await md5_checker(tag, sign, False)
    if not valid:
        raise InvalidTokenError()


# @app.exception_handler(InvalidCookieError)
async def cookie_error_handler(request: Request, exc: InvalidCookieError):
    resp = RedirectResponse('/auth', 302)
    resp.set_cookie('watchdog_auth', '')
    return resp


# @app.exception_handler(InvalidTokenError)
async def token_error_handler(request: Request, exc: InvalidTokenError):
    return JSONResponse(
        status_code=400,
        content={
            "message": 'signature expired',
        },
    )


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


class Config:
    CONFIG_DIR: Path = Path.home() / 'watchdogs'
    if not CONFIG_DIR.is_dir():
        CONFIG_DIR.mkdir()
    ENCODING = 'utf-8'
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
    uvicorn_kwargs: dict = {}
    # check interval 60s, so format do use %M , backup every 12 hours. this pattern may miss for crawl cost more than 60s.
    db_backup_time: str = '%H:%M==00:00|%H:%M==12:00'
    backup_count: int = 4
    db_backup_function: Callable[..., Any] = None
    check_cookie = check_cookie
    check_token = check_token
    exception_handlers: list = [
        (InvalidCookieError, cookie_error_handler),
        (InvalidTokenError, token_error_handler),
        (Exception, exception_handler),
    ]
