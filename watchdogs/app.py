from pathlib import Path

from fastapi import FastAPI
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from uniparser.fastapi_ui import app as sub_app

from .models import Task, tasks
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
    Config.logger.info(f'add crawler rule {JSON}: {result}')
    return result


@app.post("/add_new_task")
async def add_new_task(task: Task):
    try:
        query = tasks.insert()
        values = dict(task)
        _result = await Config.db.execute(query=query, values=values)
        if _result:
            result = {'ok': 'success'}
        else:
            result = {'ok': 'no change'}
    except Exception as e:
        result = {'error': str(e)}
    Config.logger.info(f'add task {task}: {result}')
    return result


# @app.post("/load_tasks")
# async def load_tasks(order_by: str = 'last_change_time'):
#     try:
#         query = tasks.insert()
#         values = dict(task)
#         _result = await Config.db.execute(query=query, values=values)
#         if _result:
#             result = {'ok': 'success'}
#         else:
#             result = {'ok': 'no change'}
#     except Exception as e:
#         result = {'error': str(e)}
#     Config.logger.info(f'add task {task}: {result}')
#     return result


@app.on_event("startup")
async def startup():
    await setup_app(app)


@app.on_event("shutdown")
async def shutdown():
    await release_app(app)
