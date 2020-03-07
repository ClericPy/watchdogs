from pathlib import Path


class Config(object):
    CONFIG_DIR = Path.home() / 'watchdogs'
    if not CONFIG_DIR.is_dir():
        CONFIG_DIR.mkdir()
    db = None
    logger = None
    admin = None
    password = None
    rule_db = None
    check_interval = 60
    default_interval = 5 * 60
    default_crawler_timeout = 30
    downloader_timeout = 15
    # for anti-crawl frequency
    DEFAULT_HOST_FREQUENCY = (1, 1)
    cdn_urls = {
        'VUE_JS_CDN': 'https://cdn.staticfile.org/vue/2.6.11/vue.min.js',
        'ELEMENT_CSS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/theme-chalk/index.css',
        'ELEMENT_JS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/index.js',
        'VUE_RESOURCE_CDN': 'https://cdn.staticfile.org/vue-resource/1.5.1/vue-resource.min.js',
        'CLIPBOARDJS_CDN': 'https://cdn.staticfile.org/clipboard.js/2.0.4/clipboard.min.js',
    }
