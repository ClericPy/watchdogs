from asyncio import Lock
import logging
from pathlib import Path


class Config(object):
    CONFIG_DIR = Path.home() / 'watchdogs'
    if not CONFIG_DIR.is_dir():
        CONFIG_DIR.mkdir()
    db = None
    admin = None
    password = None
    logger = logging.getLogger('watchdog')
    check_interval = 60
    default_interval = 5 * 60
    default_crawler_timeout = 60
    db_lock = Lock()
    VUE_JS_CDN = 'https://cdn.staticfile.org/vue/2.6.11/vue.min.js'
    ELEMENT_CSS_CDN = 'https://cdn.staticfile.org/element-ui/2.13.0/theme-chalk/index.css'
    ELEMENT_JS_CDN = 'https://cdn.staticfile.org/element-ui/2.13.0/index.js'
    VUE_RESOURCE_CDN = 'https://cdn.staticfile.org/vue-resource/1.5.1/vue-resource.min.js'
