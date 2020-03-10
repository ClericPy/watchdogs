from json import loads
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from fastapi import Cookie, FastAPI, Header
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import (HTMLResponse, PlainTextResponse,
                                 RedirectResponse)
from starlette.templating import Jinja2Templates
from torequests.utils import ptime, quote_plus, timeago, urlparse
from uniparser import CrawlerRule
from uniparser.fastapi_ui import app as sub_app
from uniparser.utils import get_host

from . import __version__
from .config import md5, md5_checker
from .crawler import crawl_once
from .models import Task, query_tasks, tasks
from .settings import Config, refresh_token, release_app, setup_app

app = FastAPI(
    title="Watchdogs",
    description=
    "Watchdogs to keep an eye on the world's change. Read more: https://github.com/ClericPy/watchdogs",
    version=__version__)

app.mount("/uniparser", sub_app)
app.mount(
    "/static",
    StaticFiles(directory=str((Path(__file__).parent / 'static').absolute())),
    name="static")

templates = Jinja2Templates(
    directory=str((Path(__file__).parent / 'templates').absolute()))
AUTH_PATH_WHITE_LIST = {'/auth', '/rss'}


@app.on_event("startup")
async def startup():
    await setup_app(app)


@app.on_event("shutdown")
async def shutdown():
    await release_app(app)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    # print(request.scope)
    # {'type': 'http', 'http_version': '1.1', 'server': ('127.0.0.1', 9901), 'client': ('127.0.0.1', 7037), 'scheme': 'http', 'method': 'GET', 'root_path': '', 'path': '/auth', 'raw_path': b'/auth', 'query_string': b'', 'headers': [(b'host', b'127.0.0.1:9901'), (b'connection', b'keep-alive'), (b'sec-fetch-dest', b'image'), (b'user-agent', b'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36'), (b'dnt', b'1'), (b'accept', b'image/webp,image/apng,image/*,*/*;q=0.8'), (b'sec-fetch-site', b'same-origin'), (b'sec-fetch-mode', b'no-cors'), (b'referer', b'http://127.0.0.1:9901/auth'), (b'accept-encoding', b'gzip, deflate, br'), (b'accept-language', b'zh-CN,zh;q=0.9'), (b'cookie', b'ads_id=lakdsjflakjdf; _ga=GA1.1.1550108461.1583462251')], 'fastapi_astack': <contextlib.AsyncExitStack object at 0x00000165BE69EEB8>, 'app': <fastapi.applications.FastAPI object at 0x00000165A7B738D0>}
    watchdog_auth = request.cookies.get('watchdog_auth')
    path = request.scope['path']
    if not path.startswith('/'):
        path = urlparse(request.scope['path']).path
        request.scope['path'] = path
    if path in AUTH_PATH_WHITE_LIST or Config.watchdog_auth and watchdog_auth == Config.watchdog_auth:
        response = await call_next(request)
        if path.startswith('/static/'):
            response.headers['Cache-Control'] = 'max-age=86400'
        return response
    else:
        resp = RedirectResponse('/auth', 302)
        resp.set_cookie('watchdog_auth', '')
        return resp


@app.get('/auth')
async def auth(request: Request,
               password: str = '',
               watchdog_auth: str = Cookie('')):
    # two scene for set new password, update new password if has password, else return the html
    # 1. not set watchdog_auth; 2. already authenticated
    auth_not_set = not Config.watchdog_auth
    already_authed = watchdog_auth and watchdog_auth == Config.watchdog_auth
    need_new_pwd = auth_not_set or already_authed
    if password:
        if need_new_pwd:
            Config.password = password
            await refresh_token()
            resp = RedirectResponse('/')
            resp.set_cookie(
                'watchdog_auth',
                Config.watchdog_auth,
                max_age=86400 * 1,
                httponly=True)
            return resp
        valid = await md5_checker(password, Config.watchdog_auth)
        if valid:
            resp = RedirectResponse('/')
            resp.set_cookie(
                'watchdog_auth',
                Config.watchdog_auth,
                max_age=86400 * 3,
                httponly=True)
            return resp
        elif valid is None:
            return PlainTextResponse('Check password too fast')
        else:
            # invalid password, clear cookie
            resp = RedirectResponse('/auth', 302)
            # resp.set_cookie('watchdog_auth', '')
            resp.delete_cookie('watchdog_auth')
            return resp

    else:
        kwargs: dict = {'request': request}
        kwargs['version'] = __version__
        kwargs[
            'prompt_title'] = 'Set a new password' if need_new_pwd else 'Input the password'
        return templates.TemplateResponse("auth.html", context=kwargs)


@app.get("/")
async def index(request: Request, tag: str = ''):
    kwargs: dict = {'request': request}
    kwargs['cdn_urls'] = Config.cdn_urls
    kwargs['version'] = __version__
    kwargs['rss_url'] = f'/rss?tag={quote_plus(tag)}&sign={md5(tag)}'
    return templates.TemplateResponse("index.html", context=kwargs)


@app.post("/add_new_task")
async def add_new_task(task: Task):
    try:
        exist = 'unknown'
        if task.interval < 60:
            raise ValueError('interval should not less than 60 seconds.')
        db = Config.db
        # check exist
        query = tasks.select().where(tasks.c.name == task.name)
        exist = await db.fetch_one(query=query)
        if exist:
            query = 'update tasks set `enable`=:enable,`tag`=:tag,`request_args`=:request_args,`origin_url`=:origin_url,`interval`=:interval,`work_hours`=:work_hours,`max_result_count`=:max_result_count,`custom_info`=:custom_info where `name`=:name'
            values = {
                'name': task.name,
                'enable': task.enable,
                'tag': task.tag,
                'request_args': task.request_args,
                'origin_url': task.origin_url,
                'interval': task.interval,
                'work_hours': task.work_hours,
                'max_result_count': task.max_result_count,
                'custom_info': task.custom_info,
            }
            _result = await db.execute(query=query, values=values)
        else:
            query = tasks.insert()
            values = dict(task)
            _result = await db.execute(query=query, values=values)
        result = {'msg': 'ok', 'result': 'ok' if _result else 'no change'}
        query_tasks.cache_clear()
    except Exception as e:
        result = {'msg': str(e)}
    Config.logger.info(
        f'{"[Update]" if exist else "[Add] new"} task {task}: {result}')
    return result


@app.get("/delete_task")
async def delete_task(task_id: int):
    try:
        query = tasks.delete().where(tasks.c.task_id == task_id)
        await Config.db.execute(query=query)
        result = {'msg': 'ok'}
        query_tasks.cache_clear()
    except Exception as e:
        result = {'msg': str(e)}
    Config.logger.info(f'[Delete] task {task_id}: {result}')
    return result


@app.get("/force_crawl")
async def force_crawl(task_name: str):
    try:
        task = await crawl_once(task_name=task_name)
        task['timeago'] = timeago(
            ptime() - ptime(
                task['last_change_time'].strftime('%Y-%m-%d %H:%M:%S')),
            1,
            1,
            short_name=True)
        result = {'msg': 'ok', 'task': task}
    except Exception as e:
        result = {'msg': str(e)}
    Config.logger.info(f'[Force] crawl {task_name}: {result}')
    return result


@app.get("/load_tasks")
async def load_tasks(
        task_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
        order_by: str = 'last_change_time',
        sort: str = 'desc',
        tag: str = '',
):
    try:
        _result, has_more = await query_tasks(
            task_name=task_name,
            page=page,
            page_size=page_size,
            order_by=order_by,
            sort=sort,
            tag=tag,
        )
        now_ts = ptime()
        for item in _result:
            item['timeago'] = timeago(
                now_ts - ptime(
                    item['last_change_time'].strftime('%Y-%m-%d %H:%M:%S')),
                1,
                1,
                short_name=True)
        result = {'msg': 'ok', 'tasks': _result, 'has_more': has_more}
    except Exception as e:
        import traceback
        traceback.print_exc()
        result = {'msg': str(e), 'tasks': [], 'has_more': False}
    return result


@app.get("/enable_task")
async def enable_task(task_id: int, enable: int = 1):
    query = 'update tasks set `enable`=:enable where `task_id`=:task_id'
    values = {'task_id': task_id, 'enable': enable}
    try:
        _result = await Config.db.execute(query, values)
        result = {'msg': 'ok', 'updated': _result}
        query_tasks.cache_clear()
    except Exception as e:
        result = {'msg': str(e)}
    return result


@app.get('/load_hosts')
async def load_hosts(host: str = ''):
    host = get_host(host) or host
    query = 'select `host` from host_rules'
    if host:
        query += ' where `host`=:host'
        values = {'host': host}
    else:
        values = {}
    query += ' order by `host` asc'
    _result = await Config.db.fetch_all(query, values)
    return {'hosts': [i.host for i in _result], 'host': host}


@app.get("/get_host_rule")
async def get_host_rule(host: str):
    try:
        if not host:
            raise ValueError('host name should not be null')
        query = 'select `host_rule` from host_rules where `host`=:host'
        values = {'host': host}
        _result = await Config.db.fetch_one(query, values)
        result = {
            'msg': 'ok',
            'host_rule': _result.host_rule
            if _result else '{"host": "%s"}' % host
        }
    except Exception as e:
        result = {'msg': str(e)}
    Config.logger.info(f'[Get] host_rule {host}: {result}')
    return result


@app.post("/crawler_rule.{method}")
async def crawler_rule(method: str, rule: CrawlerRule):
    try:
        if method == 'add':
            _result = await Config.rule_db.add_crawler_rule(rule)
        elif method == 'pop':
            _result = await Config.rule_db.pop_crawler_rule(rule)
        else:
            raise ValueError(f'method only support add and pop')
        result = {'msg': 'ok', 'result': _result}
    except Exception as e:
        result = {'msg': str(e)}
    Config.logger.info(f'[{method.title()}] crawler rule {rule}: {result}')
    return result


@app.get("/delete_host_rule")
async def delete_host_rule(host: str):
    try:
        if not host:
            raise ValueError('host should not be null')
        _result = await Config.rule_db.pop_host_rule(host)
        result = {'msg': 'ok'}
    except Exception as e:
        result = {'msg': str(e)}
    Config.logger.info(f'[Delete] host rule {host}: {result}')
    return result


def gen_rss(data):
    nodes = []
    channel = data['channel']
    channel_title = channel['title']
    channel_desc = channel['description']
    channel_link = channel['link']
    channel_language = channel.get('language', 'zh-cn')
    item_keys = ['title', 'description', 'link', 'guid', 'pubDate']
    for item in data['items']:
        item_nodes = []
        for key in item_keys:
            value = item.get(key)
            if value:
                item_nodes.append(f'<{key}>{escape(value)}</{key}>')
        nodes.append(''.join(item_nodes))
    items_string = ''.join((f'<item>{tmp}</item>' for tmp in nodes))
    return rf'''<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>{channel_title}</title>
  <link>{channel_link}</link>
  <description>{channel_desc}</description>
  <language>{channel_language}</language>
  <image>
    <url>{channel_link}/icon.png</url>
    <title>{channel_title}</title>
    <link>{channel_link}</link>
    <width>32</width>
    <height>32</height>
   </image>
  {items_string}
</channel>
</rss>
'''


@app.get("/rss")
async def rss(request: Request,
              tag: str = '',
              sign: str = '',
              host: str = Header('', alias='Host')):
    valid = await md5_checker(tag, sign)
    if not valid:
        return PlainTextResponse('signature expired')
    tasks, _ = await query_tasks(tag=tag)
    source_link = f'{request.scope["scheme"]}://{host}'
    # print(source_link)
    xml_data: dict = {
        'channel': {
            'title': f'Watchdogs',
            'description': 'Watchdog on web change, v{__version__}.',
            'link': source_link,
        },
        'items': []
    }
    for task in tasks:
        pubDate: str = task['last_change_time'].strftime(
            format='%a, %d %b %Y %H:%M:%S')
        latest_result: dict = loads(task['latest_result'] or '{}')
        link: str = latest_result.get('url') or task['origin_url']
        description: str = latest_result.get('text') or ''
        title: str = f'{task["name"]}#{description[:80]}'
        item: dict = {
            'title': title,
            'link': link,
            'guid': title,
            'description': description,
            'pubDate': pubDate
        }
        xml_data['items'].append(item)
    xml: str = gen_rss(xml_data)
    response = HTMLResponse(
        xml, headers={'Content-Type': 'text/xml; charset=utf-8'})
    response.headers['Content-Type'] = 'text/xml; charset=utf-8'
    return response
