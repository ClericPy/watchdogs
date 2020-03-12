from logging import getLogger
from pathlib import Path
from typing import Optional

from databases import Database
from frequency_controller import AsyncFrequency
from torequests.utils import md5 as _md5


class Config:
    CONFIG_DIR: Path = Path.home() / 'watchdogs'
    if not CONFIG_DIR.is_dir():
        CONFIG_DIR.mkdir()
    db: Optional[Database] = None
    logger = getLogger('watchdogs')
    password: str = ''
    rule_db = None
    metas = None
    check_interval: int = 60
    default_interval: int = 5 * 60
    default_crawler_timeout: int = 30
    downloader_timeout: int = 15
    watchdog_auth: str = ''
    md5_salt: str = ''
    # anti brute force attack
    check_pwd_freq = AsyncFrequency(1, 3)
    # for anti-crawl frequency
    DEFAULT_HOST_FREQUENCY = (1, 1)
    cdn_urls: dict = {}
    callback_handler = None
    access_log: bool = True
    mute_std_log = False
    mute_file_log = False
    LOG_FILE_SIZE_MB = {'info': 5, 'error': 5, 'server': 5}


def md5(obj, n=32, with_salt=True):
    if not with_salt:
        return _md5(obj, n=n)
    salt = Config.md5_salt
    if not salt:
        raise ValueError('Config.md5_salt should not be null')
    return _md5(f'{obj}{salt}', n=n)


async def md5_checker(string, target, freq=True):
    result = md5(string) == target
    if freq:
        async with Config.check_pwd_freq:
            return result
    else:
        return result
