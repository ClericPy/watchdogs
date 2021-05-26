from base64 import b64encode
from collections import deque
from datetime import datetime
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import Cookie, FastAPI, Header
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import (HTMLResponse, JSONResponse, RedirectResponse,
                                 Response)
from starlette.templating import Jinja2Templates
from torequests.utils import quote_plus, timeago, ttime
from uniparser import CrawlerRule, Uniparser
from uniparser.fastapi_ui import app as sub_app
from uniparser.utils import get_host

from . import __version__
from .config import md5_checker
from .crawler import crawl_once, find_next_check_time
from .models import Task, query_feeds, query_tasks, tasks
from .settings import (Config, get_host_freq_list, refresh_token, release_app,
                       set_host_freq, setup_app)
from .utils import format_size, gen_rss

description = "Watchdogs to keep an eye on the world's change.\nRead more: [https://github.com/ClericPy/watchdogs](https://github.com/ClericPy/watchdogs)"
app = FastAPI(title="Watchdogs", description=description, version=__version__)
sub_app.openapi_prefix = '/uniparser'
app.mount("/uniparser", sub_app)
app.mount("/static",
          StaticFiles(directory=str((Path(__file__).parent /
                                     'static').absolute())),
          name="static")
logger = Config.logger
templates = Jinja2Templates(directory=str((Path(__file__).parent /
                                           'templates').absolute()))


@app.on_event("startup")
async def startup():
    await setup_app(app)


@app.on_event("shutdown")
async def shutdown():
    await release_app(app)


@app.post('/auth')
async def post_auth(request: Request,
                    watchdog_auth: str = Cookie(''),
                    redirect: str = '/'):
    # two scene for set new password, update new password if has password, else return the html
    # 1. not set watchdog_auth; 2. already authenticated
    password = loads(await request.body())['password']
    auth_not_set = not Config.watchdog_auth
    already_authed = watchdog_auth and watchdog_auth == Config.watchdog_auth
    need_new_pwd = auth_not_set or already_authed
    if password:
        if need_new_pwd:
            old_password = Config.password
            Config.password = password
            await refresh_token()
            resp = JSONResponse({'ok': True, 'redirect': redirect})
            resp.set_cookie('watchdog_auth',
                            Config.watchdog_auth,
                            max_age=Config.cookie_max_age,
                            httponly=True)
            logger.warning(
                f'password changed {old_password}->{Config.password}.')
            return resp
        elif (await md5_checker(password, Config.watchdog_auth, freq=True)):
            resp = JSONResponse({'ok': True, 'redirect': redirect})
            resp.set_cookie('watchdog_auth',
                            Config.watchdog_auth,
                            max_age=Config.cookie_max_age,
                            httponly=True)
            logger.info('correct password, login success.')
            return resp
    # invalid password, clear cookie
    resp = JSONResponse({'ok': False})
    # resp.set_cookie('watchdog_auth', '')
    resp.delete_cookie('watchdog_auth')
    logger.info(f'invalid password: {password}')
    return resp


@app.get('/auth')
async def auth(request: Request,
               watchdog_auth: str = Cookie(''),
               redirect: str = '/'):
    auth_not_set = not Config.watchdog_auth
    already_authed = watchdog_auth and watchdog_auth == Config.watchdog_auth
    need_new_pwd = auth_not_set or already_authed
    context: dict = {'request': request}
    context['version'] = __version__
    if need_new_pwd:
        context['action'] = 'Init'
        context['prompt_title'] = 'Set a new password'
    else:
        context['action'] = 'Login'
        context['prompt_title'] = 'Input the password'
    return templates.TemplateResponse("auth.html", context=context)


@app.get("/")
async def index(request: Request, tag: str = ''):
    kwargs: dict = {'request': request}
    kwargs['cdn_urls'] = Config.cdn_urls
    kwargs['version'] = __version__
    quoted_tag = quote_plus(tag)
    rss_sign = Config.get_sign('/rss', f'tag={quoted_tag}')[1]
    lite_sign = Config.get_sign('/lite', f'tag={quoted_tag}')[1]
    feeds_sign = Config.get_sign('/feeds', f'tag={quoted_tag}')[1]
    rss_feeds_sign = Config.get_sign('/rss_feeds', f'tag={quoted_tag}')[1]
    kwargs['rss_url'] = f'/rss?tag={quoted_tag}&sign={rss_sign}'
    kwargs['lite_url'] = f'/lite?tag={quoted_tag}&sign={lite_sign}'
    kwargs['feeds_url'] = f'/feeds?tag={quoted_tag}&sign={feeds_sign}'
    kwargs[
        'rss_feeds_url'] = f'/rss_feeds?tag={quoted_tag}&sign={rss_feeds_sign}'
    init_vars_json = dumps({
        'custom_links': Config.custom_links,
        'callback_workers': Config.callback_handler.workers,
        'custom_tabs': Config.custom_tabs,
        'work_hours_doc': find_next_check_time.__doc__,
    })
    init_vars_b64 = b64encode(init_vars_json.encode('u8')).decode('u8')
    kwargs['init_vars'] = init_vars_b64
    return templates.TemplateResponse("index.html", context=kwargs)


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse('/static/img/favicon.svg', 301)


@app.post("/add_new_task")
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
            if not values.get('error'):
                values['error'] = ''
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


@app.get("/delete_task")
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


@app.get("/force_crawl")
async def force_crawl(task_name: str):
    try:
        task = await crawl_once(task_name=task_name)
        task['timeago'] = timeago(
            (datetime.now() - task['last_change_time']).total_seconds(),
            1,
            1,
            short_name=True)
        result = {'msg': 'ok', 'task': task}
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[Force] crawl {task_name}: {result}')
    return result


@app.get("/load_tasks")
async def load_tasks(
    task_name: Optional[str] = None,
    page: int = 1,
    page_size: int = Config.default_page_size,
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
                (now - item['last_change_time']).total_seconds(),
                1,
                1,
                short_name=True)
        result = {'msg': 'ok', 'tasks': _result, 'has_more': has_more}
    except Exception as e:
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
        result = {'msg': repr(e)}
    return result


@app.get('/load_hosts')
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
    host_freqs = Uniparser._HOST_FREQUENCIES
    hosts = [{
        'name': getattr(i, 'host', None),
        'freq': getattr(i, 'host', None) in host_freqs
    } for i in _result]
    return {'hosts': hosts, 'host': host}


@app.get("/get_host_rule")
async def get_host_rule(host: str):
    try:
        if not host:
            raise ValueError('host name should not be null')
        query = 'select `host_rule` from host_rules where `host`=:host'
        values = {'host': host}
        _result = await Config.db.fetch_one(query, values)
        host_rule = getattr(_result, 'host_rule', None)
        host_rule = loads(host_rule) if host_rule else {"host": host}
        host_rule['n'], host_rule['interval'] = get_host_freq_list(host)
        result = {'msg': 'ok', 'host_rule': host_rule}
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[Get] host_rule {host}: {result}')
    return result


@app.post("/crawler_rule.{method}")
async def crawler_rule(method: str,
                       rule: CrawlerRule,
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
            raise ValueError('method only support add and pop')
        result = {'msg': 'ok', 'result': _result}
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[{method.title()}] crawler rule {rule}: {result}')
    return result


@app.post("/find_crawler_rule")
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


@app.get("/delete_host_rule")
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


@app.get("/log")
async def log(request: Request,
              max_lines: int = 50,
              refresh_every: int = 0,
              log_names: str = 'info-server-error'):
    window: deque = deque((), max_lines)
    names: list = log_names.split('-')
    items = []
    for name in names:
        file_name = f'{name}.log'
        fp: Path = Config.CONFIG_DIR / file_name
        if not fp.is_file():
            continue
        fp_stat = fp.stat()
        file_size = format_size(fp_stat.st_size)
        st_mtime = ttime(fp_stat.st_mtime)
        line_no = 0
        async with aiofiles.open(fp, encoding=Config.ENCODING) as f:
            async for line in f:
                line_no += 1
                window.append(line)
        item = {
            'name': name,
            'line_no': line_no,
            'file_size': file_size,
            'st_mtime': st_mtime,
            'log_text': "".join(window),
            'file_size_mb': Config.LOGGING_FILE_CONFIG.get(file_name, {}).get(
                'file_size_mb', '-1'),
        }
        items.append(item)
        window.clear()
    context = {
        'request': request,
        'items': items,
        'log_names': log_names,
        'refresh_every': refresh_every,
        'max_lines': max_lines,
    }
    return templates.TemplateResponse("logs.html", context=context)


@app.get("/log.clear")
async def log_clear(log_names: str = 'info-server-error',
                    current_names: str = 'info-server-error'):
    names: list = log_names.split('-')
    for name in names:
        fp: Path = Config.CONFIG_DIR / f'{name}.log'
        if not fp.is_file():
            continue
        # use sync writing to block the main thread
        fp.write_bytes(b'')
        logger.info(f'{name}.log cleared')
    html = f'<meta http-equiv="refresh" content="0; url=/log?log_names={current_names}" />{log_names} log cleared. Redirecting back.'
    return HTMLResponse(html)


@app.get("/update_host_freq")
async def update_host_freq(host: str,
                           n: Optional[int] = 0,
                           interval: Optional[int] = 0):
    try:
        if not host:
            raise ValueError('host should not be null')
        await set_host_freq(host, n=n, interval=interval)
        result = {'msg': 'ok'}
    except Exception as e:
        result = {'msg': repr(e)}
    logger.info(f'[Update] host frequency {host}: {result}')
    return result


@app.get("/rss")
async def rss(request: Request,
              tag: str = '',
              sign: str = '',
              host: str = Header('', alias='Host')):
    tasks, _ = await query_tasks(tag=tag)
    source_link = f'https://{host}'
    xml_data: dict = {
        'channel': {
            'title': 'Watchdogs',
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
        title: str = f'{task["name"]}#{latest_result.get("title", description[:Config.TEXT_SLICE_LENGTH])}'
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
        headers={'Content-Type': 'application/xml; charset="utf-8"'})
    return response


@app.post("/lite")
async def post_lite(request: Request,
                    tag: str = '',
                    sign: str = '',
                    page: int = 1):
    task_id = loads(await request.body())['task_id']
    tasks, _ = await query_tasks(tag=tag, task_id=task_id)
    if tasks:
        task = tasks[0]
        try:
            result_list = loads(
                task['result_list']) if task['result_list'] else []
        except JSONDecodeError:
            result_list = []
        return {'result_list': result_list}
    else:
        return {'result_list': []}


@app.get("/lite")
async def lite(request: Request,
               tag: str = '',
               sign: str = '',
               page: int = 1,
               page_size: int = Config.default_page_size):
    tasks, has_more = await query_tasks(tag=tag, page=page, page_size=page_size)
    now = datetime.now()
    for task in tasks:
        result = loads(task['latest_result'] or '{}')
        # set / get cache from task
        task['url'] = task.get('url') or result.get('url') or task['origin_url']
        task['text'] = task.get('text') or result.get('title') or result.get(
            'text') or ''
        task['timeago'] = timeago(
            (now - task['last_change_time']).total_seconds(),
            1,
            1,
            short_name=True)
    context = {'tasks': tasks, 'request': request}
    context['version'] = __version__
    quoted_tag = quote_plus(tag)
    if has_more:
        next_page = page + 1
        sign = Config.get_sign('/lite', f'tag={quoted_tag}&page={next_page}')[1]
        next_page_url = f'/lite?tag={quoted_tag}&page={next_page}&sign={sign}'
    else:
        next_page_url = ''
    context['next_page_url'] = next_page_url
    if page > 1:
        last_page = page - 1
        sign = Config.get_sign('/lite', f'tag={quoted_tag}&page={last_page}')[1]
        last_page_url = f'/lite?tag={quoted_tag}&page={last_page}&sign={sign}'
    else:
        last_page_url = ''
    context['last_page_url'] = last_page_url
    rss_sign = Config.get_sign('/rss', f'tag={quoted_tag}')[1]
    context['rss_url'] = f'/rss?tag={quoted_tag}&sign={rss_sign}'
    return templates.TemplateResponse("lite.html", context=context)


@app.get("/feeds")
async def feeds(
    request: Request,
    tag: str = '',
    # user: str = '',
    sign: str = '',
    page: int = 1,
    page_size: int = Config.default_page_size,
):
    feeds, has_more = await query_feeds(tag=tag, page=page, page_size=page_size)
    now = datetime.now()
    _feeds = []
    current_date = None
    today = datetime.today().strftime('%Y-%m-%d')
    for feed in feeds:
        date = feed['ts_create'].strftime('%Y-%m-%d')
        if date != current_date:
            current_date = date
            if date == today:
                date += ' [Today]'
            _feeds.append({'current_date': date})
        feed['timeago'] = timeago((now - feed['ts_create']).total_seconds(),
                                  1,
                                  1,
                                  short_name=True)
        _feeds.append(feed)
    context = {'feeds': _feeds, 'request': request}
    context['version'] = __version__
    quoted_tag = quote_plus(tag)
    if has_more:
        next_page = page + 1
        sign = Config.get_sign('/feeds',
                               f'tag={quoted_tag}&page={next_page}')[1]
        next_page_url = f'/feeds?tag={quoted_tag}&page={next_page}&sign={sign}'
    else:
        next_page_url = ''
    context['next_page_url'] = next_page_url
    if page > 1:
        last_page = page - 1
        sign = Config.get_sign('/feeds',
                               f'tag={quoted_tag}&page={last_page}')[1]
        last_page_url = f'/feeds?tag={quoted_tag}&page={last_page}&sign={sign}'
    else:
        last_page_url = ''
    context['last_page_url'] = last_page_url
    rss_sign = Config.get_sign('/rss_feeds', f'tag={quoted_tag}')[1]
    context['rss_url'] = f'/rss_feeds?tag={quoted_tag}&sign={rss_sign}'
    return templates.TemplateResponse("feeds.html", context=context)


@app.get("/rss_feeds")
async def rss_feeds(request: Request,
                    tag: str = '',
                    sign: str = '',
                    host: str = Header('', alias='Host')):
    feeds, _ = await query_feeds(tag=tag)
    source_link = f'https://{host}'
    xml_data: dict = {
        'channel': {
            'title': 'Watchdogs Timeline',
            'description': f'Watchdog on web change, v{__version__}.',
            'link': source_link,
        },
        'items': []
    }
    for feed in feeds:
        pubDate: str = feed['ts_create'].strftime(
            format='%a, %d %b %Y %H:%M:%S')
        link: str = feed['url']
        description: str = feed['text']
        title: str = f'{feed["name"]}#{description[:Config.TEXT_SLICE_LENGTH]}'
        item: dict = {
            'title': title,
            'link': link,
            'guid': str(feed['id']),
            'description': description,
            'pubDate': pubDate
        }
        xml_data['items'].append(item)
    xml: str = gen_rss(xml_data)
    response = Response(
        content=xml,
        media_type="application/xml",
        headers={'Content-Type': 'application/xml; charset="utf-8"'})
    return response
