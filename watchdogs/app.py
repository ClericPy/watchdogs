from fastapi import FastAPI
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from uniparser.fastapi_ui import app as sub_app

from .settings import release_app, setup_app

app = FastAPI()

app.mount("/uniparser", sub_app)
templates = Jinja2Templates(directory="templates")
cdn_urls = {
    'VUE_JS_CDN': 'https://cdn.staticfile.org/vue/2.6.11/vue.min.js',
    'ELEMENT_CSS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/theme-chalk/index.css',
    'ELEMENT_JS_CDN': 'https://cdn.staticfile.org/element-ui/2.13.0/index.js',
    'VUE_RESOURCE_CDN': 'https://cdn.staticfile.org/vue-resource/1.5.1/vue-resource.min.js',
    'CLIPBOARDJS_CDN': 'https://cdn.staticfile.org/clipboard.js/2.0.4/clipboard.min.js',
}


@app.get("/")
async def index(request: Request, id: str):
    kwargs = {}
    kwargs.update(cdn_urls)
    return templates.TemplateResponse("index.html", kwargs)


@app.on_event("startup")
async def startup():
    await setup_app(app)


@app.on_event("shutdown")
async def shutdown():
    await release_app(app)
