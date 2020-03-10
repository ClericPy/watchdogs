from pathlib import Path

from frequency_controller import AsyncFrequency
from torequests.utils import md5 as _md5


class Config:
    CONFIG_DIR = Path.home() / 'watchdogs'
    if not CONFIG_DIR.is_dir():
        CONFIG_DIR.mkdir()
    db = None
    logger = None
    password: str = ''
    rule_db = None
    check_interval = 60
    default_interval = 5 * 60
    default_crawler_timeout = 30
    downloader_timeout = 15
    watchdog_auth: str = ''
    md5_salt: str = ''
    # anti brute force attack
    check_pwd_freq = AsyncFrequency(1, 3)
    # for anti-crawl frequency
    DEFAULT_HOST_FREQUENCY = (1, 1)
    # online cdns
    # cdn_urls = {
    #     'VUE_JS_CDN': 'https://cdn.staticfile.org/vue/2.6.11/vue.min.js',
    #     'ELEMENT_CSS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/theme-chalk/index.css',
    #     'ELEMENT_JS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/index.js',
    #     'VUE_RESOURCE_CDN': 'https://cdn.staticfile.org/vue-resource/1.5.1/vue-resource.min.js',
    #     'CLIPBOARDJS_CDN': 'https://cdn.staticfile.org/clipboard.js/2.0.4/clipboard.min.js',
    # }
    cdn_urls = {
        'VUE_JS_CDN': '/static/js/vue.min.js',
        'ELEMENT_CSS_CDN': '/static/css/index.css',
        'ELEMENT_JS_CDN': '/static/js/index.js',
        'VUE_RESOURCE_CDN': '/static/js/vue-resource.min.js',
        'CLIPBOARDJS_CDN': '/static/js/clipboard.min.js',
    }


def md5(obj, n=32, with_salt=True):
    if not with_salt:
        return _md5(obj, n=n)
    salt = Config.md5_salt
    if not salt:
        raise ValueError('Config.md5_salt should not be null')
    return _md5(f'{obj}{salt}', n=n)


async def md5_checker(string, target):
    async with Config.check_pwd_freq:
        return md5(string) == target
