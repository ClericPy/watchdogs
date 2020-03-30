# [watchdogs](https://github.com/ClericPy/watchdogs) [![PyPI](https://img.shields.io/pypi/v/watchdogs?style=plastic)](https://pypi.org/project/watchdogs/)![PyPI - Wheel](https://img.shields.io/pypi/wheel/watchdogs?style=plastic)![PyPI - Python Version](https://img.shields.io/pypi/pyversions/watchdogs?style=plastic)![PyPI - Downloads](https://img.shields.io/pypi/dm/watchdogs?style=plastic)![PyPI - License](https://img.shields.io/pypi/l/watchdogs?style=plastic)

Keep an eye on the change of web world.

Such as `post articles` / `news on the web portal` / `server api health` / `binge-watching` / `steam price fluctuation` / `github events` / `updates of comic and novel`, and so on...

## Intro

1. This is a web app based on [fastapi](https://github.com/tiangolo/fastapi), [databases](https://github.com/encode/databases), [uniparser](https://github.com/ClericPy/uniparser), [torequests](https://github.com/ClericPy/torequests).
2. Smoothly deploy it by pip: `pip install -U watchdogs;python3 -m watchdogs`
3. Simple to create a new crawler with the Web UI, not like old ways to write duplicate code.
4. All the crawlers keep runing in the async environment.
5. Almost all the elements have a *title* attribute to describe the features in the Web UI, which means docs lay on the UI.
6. Release your hands from repetitive refreshing pages on the browser.
    1. Subscribe the change events with RSS reminder extensions, such as [Feedbro](https://chrome.google.com/webstore/detail/feedbro/mefgmmbdailogpfhfblcnnjfmnpnmdfa) or RSS Feed Reader.
    2. Implement a class which inherits from `watchdogs.callbacks.Callback`.

## Usage

1. > pip install -U watchdogs

2. > python -m watchdogs

3. > Open the browser: http://127.0.0.1:9901

### Command line args

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
> If Config.cdn_urls not set, and use_default_cdn is True, will use online js/css cdn links from staticfile.org.
- **\*\*uvicorn_kwargs**:
> uvicorn startup kwargs, such as port, host. Which can be set like: `python -m watchdogs --port=9999 --host=127.0.0.1 --access-log=False`

### Quick Start to Create New Task

[Quick Start Screenshots](https://github.com/ClericPy/watchdogs/blob/master/quick_start.md)


## Web UI

<details>
        <summary>Screenshots</summary>

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

</details>
