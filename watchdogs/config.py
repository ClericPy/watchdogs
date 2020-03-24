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
    uvicorn_kwargs: dict = {}
    # check interval 60s, so format do use %M , backup every 12 hours. this pattern may miss for crawl cost more than 60s.
    db_backup_time: str = '%H:%M==00:00|%H:%M==12:00'
    backup_count: int = 4
    db_backup_function: Callable[..., Any] = None
    exception_handlers: list = [
        (Exception, exception_handler),
    ]
