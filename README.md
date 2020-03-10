# [watchdogs](https://github.com/ClericPy/watchdogs) [![PyPI](https://img.shields.io/pypi/v/watchdogs?style=plastic)](https://pypi.org/project/watchdogs/)![PyPI - Wheel](https://img.shields.io/pypi/wheel/watchdogs?style=plastic)![PyPI - Python Version](https://img.shields.io/pypi/pyversions/watchdogs?style=plastic)![PyPI - Downloads](https://img.shields.io/pypi/dm/watchdogs?style=plastic)![PyPI - License](https://img.shields.io/pypi/l/watchdogs?style=plastic)

Watchdogs to keep an eye on the world's change.

## Intro

1. This is a web app based on [fastapi](https://github.com/tiangolo/fastapi), [databases](https://github.com/encode/databases), [uniparser](https://github.com/ClericPy/uniparser).
2. The implementation of views is to be plug-in and portable, which means it can be mounted on other web apps as a [sub app](https://fastapi.tiangolo.com/advanced/sub-applications-proxy/#mount-the-sub-application):
    1. `app.mount("/uniparser", uniparser_app)`
3. Quite simple to create new crawler with the Web UI.
4. All the crawlers runs in the async environment.
5. Almost all the buttons has a *title* attribute to describe the features in Web UI, so docs will not come very early.

## Usage

1. > pip install -U watchdogs

2. > python -m watchdogs

3. > view the page on browser: http://127.0.0.1:9901

### Args

> python -m watchdogs -- -h

- **db_url**:
> sqlite / mysql / postgresql(not test) url, which [databases](https://github.com/encode/databases) support. Defaults to 'sqlite:///{HOME_PATH}/watchdogs/storage.sqlite'
- **password**:
> init password, if null can be set on the first visit on web.
- **ignore_stdout_log**:
> remove stdout logging
- **ignore_file_log**:
> remove file logging located at {HOME_PATH}/watchdogs folder.
- **md5_salt**:
> md5_salt for custom md5(password) / md5(rss_tag)
- **config_dir**:
> config dir to save the logs and config files, if using sqlite include sqlite file. defaults to {HOME_PATH}/watchdogs
- **\*\*uvicorn_kwargs**:
> uvicorn startup kwargs, such as port, host. Which can be set like: `python -m watchdogs --port=9999 --host=127.0.0.1`



## Screenshots

![image](https://github.com/ClericPy/watchdogs/raw/master/images/2.png)
![image](https://github.com/ClericPy/watchdogs/raw/master/images/3.png)
![image](https://github.com/ClericPy/watchdogs/raw/master/images/4.png)
![image](https://github.com/ClericPy/watchdogs/raw/master/images/5.png)
