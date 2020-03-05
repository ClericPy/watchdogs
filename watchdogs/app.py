from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from torequests.utils import ptime, timeago
from uniparser.fastapi_ui import app as sub_app

from .crawler import crawl_once
from .models import Task, query_tasks, tasks
from .settings import Config, release_app, setup_app

app = FastAPI()

app.mount("/uniparser", sub_app)
templates = Jinja2Templates(
    directory=str((Path(__file__).parent / 'templates').absolute()))
cdn_urls = {
    'VUE_JS_CDN': 'https://cdn.staticfile.org/vue/2.6.11/vue.min.js',
    'ELEMENT_CSS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/theme-chalk/index.css',
    'ELEMENT_JS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/index.js',
    'VUE_RESOURCE_CDN': 'https://cdn.staticfile.org/vue-resource/1.5.1/vue-resource.min.js',
    'CLIPBOARDJS_CDN': 'https://cdn.staticfile.org/clipboard.js/2.0.4/clipboard.min.js',
}


@app.get("/")
async def index(request: Request):
    kwargs: dict = {'request': request}
    kwargs['cdn_urls'] = cdn_urls
    return templates.TemplateResponse("index.html", context=kwargs)


@app.post("/add_crawler_rule")
async def add_crawler_rule(request: Request):
    JSON = (await request.body()).decode('u8')
    try:
        _result = await Config.rule_db.add_crawler_rule(JSON)
        if _result:
            result = {'ok': 'success'}
        else:
            result = {'ok': 'no change'}
    except Exception as e:
        result = {'error': str(e)}
    Config.logger.info(f'[Add] crawler rule {JSON}: {result}')
    return result


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
            query = 'update tasks set `enable`=:enable,`tags`=:tags,`request_args`=:request_args,`origin_url`=:origin_url,`interval`=:interval,`work_hours`=:work_hours,`max_result_count`=:max_result_count,`custom_info`=:custom_info where `name`=:name'
            values = {
                'name': task.name,
                'enable': task.enable,
                'tags': task.tags,
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
        if _result:
            result = {'ok': 'success'}
        else:
            result = {'ok': 'no change'}
    except Exception as e:
        result = {'error': str(e)}
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
):
    try:
        _result, has_more = await query_tasks(
            task_name=task_name,
            page=page,
            page_size=page_size,
            order_by=order_by,
            sort=sort)
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


@app.on_event("startup")
async def startup():
    await setup_app(app)


@app.on_event("shutdown")
async def shutdown():
    await release_app(app)
