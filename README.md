# [watchdogs](https://github.com/ClericPy/watchdogs) [![PyPI](https://img.shields.io/pypi/v/watchdogs?style=plastic)](https://pypi.org/project/watchdogs/)![PyPI - Wheel](https://img.shields.io/pypi/wheel/watchdogs?style=plastic)![PyPI - Python Version](https://img.shields.io/pypi/pyversions/watchdogs?style=plastic)![PyPI - Downloads](https://img.shields.io/pypi/dm/watchdogs?style=plastic)![PyPI - License](https://img.shields.io/pypi/l/watchdogs?style=plastic)

Watchdogs to keep an eye on the world's change.

## Intro

1. This is a web app based on [fastapi](https://github.com/tiangolo/fastapi), [databases](https://github.com/encode/databases), [uniparser](https://github.com/ClericPy/uniparser), [torequests](https://github.com/ClericPy/torequests).
2. Smoothly deploy by pip: `pip install -U watchdogs;python3 -m watchdogs`
3. Simple to create new crawler with the Web UI, not like old ways to duplicate crawler code.
4. All the crawlers run in the async environment.
5. Almost all the buttons have the *title* attribute to describe the features in Web UI, which means doc lay on the UI.
6. Release your hands from repetitive refreshing on the browser, subscribe the tasks with RSS reminder extensions, such as Feedbro or RSS Feed Reader. Even some custom reminder inherit watchdogs.callbacks.Callback.

## Usage

1. > pip install -U watchdogs

2. > python -m watchdogs

3. > Open with a browser: http://127.0.0.1:9901

### Args

> python -m watchdogs -- -h

- **db_url**:
> sqlite / mysql / postgresql(not test) url, which [databases](https://github.com/encode/databases) supports. Defaults to 'sqlite:///{HOME_PATH}/watchdogs/storage.sqlite'
- **password**:
> init password, if null can be set on the first visit on web.
- **mute_std_log**:
> remove stdout log for clean stream
- **mute_file_log**:
> ignore file log located at {HOME_PATH}/watchdogs folder.
- **md5_salt**:
> md5_salt for custom md5(password) / md5(rss_tag)
- **config_dir**:
> config dir to save the logs and config files, if using sqlite include sqlite file. defaults to {HOME_PATH}/watchdogs
- **use_default_cdn**:
> If Config.cdn_urls not set, and use_default_cdn is True, will use online js/css cdn from staticfile.org.
- **\*\*uvicorn_kwargs**:
> uvicorn startup kwargs, such as port, host. Which can be set like: `python -m watchdogs --port=9999 --host=127.0.0.1`

### Quick Start to Create New Task

[Quick Start Screenshots](https://github.com/ClericPy/watchdogs/blob/master/quick_start.md)

## Screenshots

1. Welcome Page (Tasks Page).
> Here you can see all the tasks meta, goto RSS / Mobile Lite Page, and do some operations to the tasks.

![image](https://github.com/ClericPy/watchdogs/raw/master/images/1.png)

2. New Task Page.
> Here based on the latest [uniparser](https://github.com/ClericPy/uniparser) web app, to create new rules and also tasks.

![image](https://github.com/ClericPy/watchdogs/raw/master/images/2.png)

3. Rules Page.
> Do some operations for the rules.

![image](https://github.com/ClericPy/watchdogs/raw/master/images/3.png)

4. API page.
> Based on [fastapi](https://github.com/tiangolo/fastapi) `/docs` which is generated automatically.

![image](https://github.com/ClericPy/watchdogs/raw/master/images/4.png)

5. Mobile Page (Lite View).
> For mobile phone to glimpse the latest result for the current 30 tasks.

![image](https://github.com/ClericPy/watchdogs/raw/master/images/5.png)
