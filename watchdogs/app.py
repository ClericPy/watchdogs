from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates
from torequests.utils import ptime, timeago
from uniparser import CrawlerRule
from uniparser.fastapi_ui import app as sub_app
from uniparser.utils import get_host

from . import __version__
from .crawler import crawl_once
from .models import Task, query_tasks, tasks
from .settings import Config, release_app, setup_app

app = FastAPI()

app.mount("/uniparser", sub_app)
app.mount(
    "/static",
    StaticFiles(directory=str((Path(__file__).parent / 'static').absolute())),
    name="static")

templates = Jinja2Templates(
    directory=str((Path(__file__).parent / 'templates').absolute()))


# @app.middleware("http")
# async def add_process_time_header(request: Request, call_next):
#     valid = False
#     if not valid and request.scope.get('raw_path') != b'/login':
#         return RedirectResponse('/login', 302)
#     response = await call_next(request)
#     return response


@app.get('/login')
async def login():
    return 'login'


@app.get("/")
async def index(request: Request):
    kwargs: dict = {'request': request}
    kwargs['cdn_urls'] = Config.cdn_urls
    kwargs['version'] = __version__
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


@app.on_event("startup")
async def startup():
    await setup_app(app)


@app.on_event("shutdown")
async def shutdown():
    await release_app(app)
