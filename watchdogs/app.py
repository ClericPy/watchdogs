from collections import deque
from datetime import datetime
from json import dumps, loads
from pathlib import Path
from time import time
from traceback import format_exc
from typing import Optional

import aiofiles
from fastapi import Cookie, Depends, FastAPI, Header
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import (HTMLResponse, JSONResponse, PlainTextResponse,
                                 RedirectResponse, Response)
from starlette.templating import Jinja2Templates
from torequests.utils import quote_plus, timeago
from uniparser import CrawlerRule
from uniparser.fastapi_ui import app as sub_app
from uniparser.utils import get_host

from . import __version__
from .config import md5, md5_checker
from .crawler import crawl_once
from .models import Task, query_tasks, tasks
from .settings import Config, refresh_token, release_app, setup_app
from .utils import gen_rss

description = f"Watchdogs to keep an eye on the world's change.\nRead more: [https://github.com/ClericPy/watchdogs](https://github.com/ClericPy/watchdogs)\n\n[View Logs](/log)"
app = FastAPI(title="Watchdogs", description=description, version=__version__)
sub_app.openapi_prefix = '/uniparser'
app.mount("/uniparser", sub_app)
app.mount(
    "/static",
    StaticFiles(directory=str((Path(__file__).parent / 'static').absolute())),
    name="static")
logger = Config.logger
templates = Jinja2Templates(
    directory=str((Path(__file__).parent / 'templates').absolute()))


@app.on_event("startup")
async def startup():
    await setup_app(app)


@app.on_event("shutdown")
async def shutdown():
    await release_app(app)


# @app.middleware("http")
# async def add_auth_checker(request: Request, call_next):
#     AUTH_PATH_WHITE_LIST = {'/auth', '/rss', '/lite'}
#     # print(request.scope)
#     # {'type': 'http', 'http_version': '1.1', 'server': ('127.0.0.1', 9901), 'client': ('127.0.0.1', 7037), 'scheme': 'http', 'method': 'GET', 'root_path': '', 'path': '/auth', 'raw_path': b'/auth', 'query_string': b'', 'headers': [(b'host', b'127.0.0.1:9901'), (b'connection', b'keep-alive'), (b'sec-fetch-dest', b'image'), (b'user-agent', b'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36'), (b'dnt', b'1'), (b'accept', b'image/webp,image/apng,image/*,*/*;q=0.8'), (b'sec-fetch-site', b'same-origin'), (b'sec-fetch-mode', b'no-cors'), (b'referer', b'http://127.0.0.1:9901/auth'), (b'accept-encoding', b'gzip, deflate, br'), (b'accept-language', b'zh-CN,zh;q=0.9'), (b'cookie', b'ads_id=lakdsjflakjdf; _ga=GA1.1.1550108461.1583462251')], 'fastapi_astack': <contextlib.AsyncExitStack object at 0x00000165BE69EEB8>, 'app': <fastapi.applications.FastAPI object at 0x00000165A7B738D0>}
#     watchdog_auth = request.cookies.get('watchdog_auth')
#     path = request.scope['path']
#     if not path.startswith('/'):
#         path = urlparse(request.scope['path']).path
#         request.scope['path'] = path
#     if path in AUTH_PATH_WHITE_LIST or Config.watchdog_auth and watchdog_auth == Config.watchdog_auth:
#         # gateway may do better, but kong used too much memory...
#         response = await call_next(request)
#         if path.startswith('/static/'):
#             response.headers['Cache-Control'] = 'max-age=86400'
#         return response
#     else:
#         resp = RedirectResponse('/auth', 302)
#         resp.set_cookie('watchdog_auth', '')
#         return resp


class InvalidCookieError(Exception):
    '''bad cookie redirect to /auth'''


async def check_cookie(watchdog_auth: str = Cookie('')):
    if Config.watchdog_auth and watchdog_auth != Config.watchdog_auth:
        raise InvalidCookieError()


class InvalidTokenError(Exception):
    '''bad token return text: invalid token'''


async def check_token(tag: str = '',
                      sign: str = '',
                      host: str = Header('', alias='Host')):
    valid = await md5_checker(tag, sign, False)
    if not valid:
        raise InvalidTokenError()


@app.exception_handler(InvalidCookieError)
async def cookie_error_handler(request: Request, exc: InvalidCookieError):
    resp = RedirectResponse('/auth', 302)
    resp.set_cookie('watchdog_auth', '')
    return resp


@app.exception_handler(InvalidTokenError)
async def token_error_handler(request: Request, exc: InvalidTokenError):
    return PlainTextResponse('signature expired')


@app.exception_handler(Exception)
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
            old_password = Config.password
            Config.password = password
            await refresh_token()
            resp = RedirectResponse('/')
            resp.set_cookie(
                'watchdog_auth',
                Config.watchdog_auth,
                max_age=86400 * 3,
                httponly=True)
            logger.warning(
                f'password changed {old_password}->{Config.password}.')
            return resp
        valid = await md5_checker(password, Config.watchdog_auth)
        if valid:
            resp = RedirectResponse('/')
            resp.set_cookie(
                'watchdog_auth',
                Config.watchdog_auth,
                max_age=86400 * 3,
                httponly=True)
            logger.info('correct password, login success.')
            return resp
        # elif valid is None:
        #     return PlainTextResponse('Check password too fast')
        else:
            # invalid password, clear cookie
            resp = RedirectResponse('/auth', 302)
            # resp.set_cookie('watchdog_auth', '')
            resp.delete_cookie('watchdog_auth')
            logger.info(f'invalid password: {password}')
            return resp

    else:
        kwargs: dict = {'request': request}
        kwargs['version'] = __version__
        if need_new_pwd:
            kwargs['action'] = 'Init'
            kwargs['prompt_title'] = 'Set a new password'
        else:
            kwargs['action'] = 'Login'
            kwargs['prompt_title'] = 'Input the password'
        return templates.TemplateResponse("auth.html", context=kwargs)


@app.get("/", dependencies=[Depends(check_cookie)])
async def index(request: Request, tag: str = ''):
    kwargs: dict = {'request': request}
    kwargs['cdn_urls'] = Config.cdn_urls
    kwargs['version'] = __version__
    kwargs['rss_url'] = f'/rss?tag={quote_plus(tag)}&sign={md5(tag)}'
    kwargs['lite_url'] = f'/lite?tag={quote_plus(tag)}&sign={md5(tag)}'
    kwargs['callback_workers'] = dumps(Config.callback_handler.workers)
    return templates.TemplateResponse("index.html", context=kwargs)


@app.get("/favicon.ico", dependencies=[Depends(check_cookie)])
async def favicon():
    return RedirectResponse('/static/img/favicon.ico', 301)


@app.post("/add_new_task", dependencies=[Depends(check_cookie)])
async def add_new_task(task: Task):
    try:
        exist = 'unknown'
        if task.interval < 60:
            raise ValueError('interval should not less than 60 seconds.')
        db = Config.db
        # check exist
        if task.task_id is None:
            # insert new task
            query = tasks.insert()
            values = dict(task)
            values.pop('error', None)
            # insert with task_id is None
            await db.execute(query=query, values=values)
        else:
            # update old task
            query = 'update tasks set `name`=:name,`enable`=:enable,`tag`=:tag,`request_args`=:request_args,`origin_url`=:origin_url,`interval`=:interval,`work_hours`=:work_hours,`max_result_count`=:max_result_count,`custom_info`=:custom_info,`next_check_time`=:next_check_time where `task_id`=:task_id'
            values = {
                'task_id': task.task_id,
                'name': task.name,
                'enable': task.enable,
                'tag': task.tag,
                'request_args': task.request_args,
                'origin_url': task.origin_url,
                'interval': task.interval,
                'work_hours': task.work_hours,
                'max_result_count': task.max_result_count,
                'custom_info': task.custom_info,
                'next_check_time': datetime.now(),
            }
            await db.execute(query=query, values=values)
        result = {'msg': 'ok'}
        query_tasks.cache_clear()
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'{"[Update]" if exist else "[Add] new"} task {task}: {result}')
    return result


@app.get("/delete_task", dependencies=[Depends(check_cookie)])
async def delete_task(task_id: int):
    try:
        query = tasks.delete().where(tasks.c.task_id == task_id)
        await Config.db.execute(query=query)
        result = {'msg': 'ok'}
        query_tasks.cache_clear()
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[Delete] task {task_id}: {result}')
    return result


@app.get("/force_crawl", dependencies=[Depends(check_cookie)])
async def force_crawl(task_name: str):
    try:
        task = await crawl_once(task_name=task_name)
        task['timeago'] = timeago(
            (datetime.now() - task['last_change_time']).seconds,
            1,
            1,
            short_name=True)
        result = {'msg': 'ok', 'task': task}
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[Force] crawl {task_name}: {result}')
    return result


@app.get("/load_tasks", dependencies=[Depends(check_cookie)])
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
        _result = [task for task in _result]
        now = datetime.now()
        for item in _result:
            item['timeago'] = timeago(
                (now - item['last_change_time']).seconds, 1, 1, short_name=True)
        result = {'msg': 'ok', 'tasks': _result, 'has_more': has_more}
    except Exception as e:
        result = {'msg': str(e), 'tasks': [], 'has_more': False}
    return result


@app.get("/enable_task", dependencies=[Depends(check_cookie)])
async def enable_task(task_id: int, enable: int = 1):
    query = 'update tasks set `enable`=:enable where `task_id`=:task_id'
    values = {'task_id': task_id, 'enable': enable}
    try:
        _result = await Config.db.execute(query, values)
        result = {'msg': 'ok', 'updated': _result}
        query_tasks.cache_clear()
    except Exception as e:
        result = {'msg': repr(e)}
    return result


@app.get('/load_hosts', dependencies=[Depends(check_cookie)])
async def load_hosts(host: str = ''):
    host = get_host(host) or host
    query = 'select `host` from host_rules'
    if host:
        query += ' where `host` like :host'
        values = {'host': f'%{host}%'}
    else:
        values = {}
    query += ' order by `host` asc'
    _result = await Config.db.fetch_all(query, values)
    return {'hosts': [getattr(i, 'host') for i in _result], 'host': host}


@app.get("/get_host_rule", dependencies=[Depends(check_cookie)])
async def get_host_rule(host: str):
    try:
        if not host:
            raise ValueError('host name should not be null')
        query = 'select `host_rule` from host_rules where `host`=:host'
        values = {'host': host}
        _result = await Config.db.fetch_one(query, values)
        result = {
            'msg': 'ok',
            'host_rule': getattr(_result, 'host_rule')
            if _result else '{"host": "%s"}' % host
        }
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[Get] host_rule {host}: {result}')
    return result


@app.post("/crawler_rule.{method}", dependencies=[Depends(check_cookie)])
async def crawler_rule(method: str, rule: CrawlerRule,
                       force: Optional[int] = 0):
    try:
        if not rule['name']:
            raise ValueError('rule name can not be null')
        if method == 'add':
            if force:
                exist_rule = await Config.rule_db.find_crawler_rule(
                    rule['request_args']['url'])
                if exist_rule:
                    logger.info(
                        f'add crawler_rule force=1, old rule removed: {exist_rule}'
                    )
                    await Config.rule_db.pop_crawler_rule(exist_rule)
            _result = await Config.rule_db.add_crawler_rule(rule)
        elif method == 'pop':
            _result = await Config.rule_db.pop_crawler_rule(rule)
        else:
            raise ValueError(f'method only support add and pop')
        result = {'msg': 'ok', 'result': _result}
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[{method.title()}] crawler rule {rule}: {result}')
    return result


@app.post("/find_crawler_rule", dependencies=[Depends(check_cookie)])
async def find_crawler_rule(request_args: dict):
    try:
        url = request_args.get('url')
        rule: CrawlerRule = await Config.rule_db.find_crawler_rule(url)
        if not rule:
            raise ValueError(f'rule not found for given url: {url}')
        result = {'msg': 'ok', 'result': rule.dumps()}
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[Find] crawler rule: {result}')
    return result


@app.get("/delete_host_rule", dependencies=[Depends(check_cookie)])
async def delete_host_rule(host: str):
    try:
        if not host:
            raise ValueError('host should not be null')
        await Config.rule_db.pop_host_rule(host)
        result = {'msg': 'ok'}
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[Delete] host rule {host}: {result}')
    return result


@app.get("/log", dependencies=[Depends(check_cookie)])
async def log(max_lines: int = 100,
              refresh_every: int = 0,
              log_names: str = 'info-server-error'):
    html = '<style>body{background-color:#FAFAFA;padding:1em;}pre,p{background-color:#ECEFF1;padding: 1em;}</style>'
    html += f'<meta http-equiv="refresh" content="{refresh_every};">' if refresh_every else ''
    html += f'<p><a href="?max_lines={max_lines}&refresh_every={refresh_every}&log_names={log_names}">?max_lines={max_lines}&refresh_every={refresh_every}&log_names={log_names}</a></p>'
    window: deque = deque((), max_lines)
    names: list = log_names.split('-')
    for name in names:
        async with aiofiles.open(
                Config.CONFIG_DIR / f'{name}.log',
                encoding=Config.ENCODING) as f:
            async for line in f:
                window.append(line)
        html += f'<hr><h3>{name}.log</h3><hr><pre><code>{"".join(window)}</code></pre>'
        window.clear()
    response = HTMLResponse(html)
    return response


@app.get("/rss", dependencies=[Depends(check_token)])
async def rss(request: Request,
              tag: str = '',
              sign: str = '',
              host: str = Header('', alias='Host')):
    valid = await md5_checker(tag, sign, False)
    if not valid:
        return PlainTextResponse('signature expired')
    tasks, _ = await query_tasks(tag=tag)
    source_link = f'https://{host}'
    # print(source_link)
    xml_data: dict = {
        'channel': {
            'title': f'Watchdogs',
            'description': f'Watchdog on web change, v{__version__}.',
            'link': source_link,
        },
        'items': []
    }
    for task in tasks:
        pubDate: str = task['last_change_time'].strftime(
            format='%a, %d %b %Y %H:%M:%S')
        latest_result: dict = loads(task['latest_result'] or '{}')
        if isinstance(latest_result, list):
            logger.error(f'latest_result is list: {latest_result}')
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
    response = Response(
        content=xml,
        media_type="application/xml",
        headers={'Content-Type': 'text/xml; charset=utf-8'})
    return response


@app.get("/lite", dependencies=[Depends(check_token)])
async def lite(request: Request,
               tag: str = '',
               sign: str = '',
               task_id: Optional[int] = None):
    valid = await md5_checker(tag, sign, False)
    if not valid:
        return PlainTextResponse('signature expired')
    tasks, _ = await query_tasks(tag=tag, task_id=task_id)
    if task_id is None:
        now = datetime.now()
        for task in tasks:
            result = loads(task['latest_result'] or '{}')
            # for cache...
            task['url'] = task.get('url') or result.get(
                'url') or task['origin_url']
            task['text'] = task.get('text') or result.get('text') or ''
            task['timeago'] = timeago(
                (now - task['last_change_time']).seconds, 1, 1, short_name=True)
        kwargs = {'tasks': tasks, 'request': request}
        kwargs['version'] = __version__
        return templates.TemplateResponse("lite.html", context=kwargs)
    else:
        if tasks:
            task = tasks[0]
            items = loads(task['result_list'] or '[]')
            return {'result_list': items}
        else:
            return {'result_list': []}
