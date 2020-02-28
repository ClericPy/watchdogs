from pathlib import Path

from fastapi import FastAPI, Body
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from uniparser import CrawlerRule, Uniparser, __version__
from uniparser.utils import ensure_request, get_available_async_request

from ..config import Config

app = FastAPI(openapi_prefix="/watchdog")

adapter = get_available_async_request()
if not adapter:
    raise RuntimeError(
        "one of these libs should be installed: ('requests', 'httpx', 'torequests')"
    )
uni = Uniparser(adapter())

GLOBAL_RESP = None
templates = Jinja2Templates(directory=str(Path(__file__).parent.absolute()))


@app.get('/init_app')
def init_app():
    parser_name_choices = [{'value': i.name} for i in uni.parser_classes]
    parser_name_docs = {i.name: i.__doc__ for i in uni.parser_classes}
    parser_name_docs[''] = 'Choose a parser_name'
    return {
        'parser_name_choices': parser_name_choices,
        'parser_name_docs': parser_name_docs,
    }


@app.get("/")
def index(request: Request):
    cdn_urls = dict(
        VUE_JS_CDN=Config.VUE_JS_CDN,
        ELEMENT_CSS_CDN=Config.ELEMENT_CSS_CDN,
        ELEMENT_JS_CDN=Config.ELEMENT_JS_CDN,
        VUE_RESOURCE_CDN=Config.VUE_RESOURCE_CDN,
    )
    return templates.TemplateResponse(
        'index.html',
        dict(cdn_urls=cdn_urls, version=__version__, request=request))


@app.post("/request")
async def send_request(request_args: dict):
    global GLOBAL_RESP
    rule = CrawlerRule(**request_args)
    body, r = await uni.adownload(rule)
    GLOBAL_RESP = r
    return {
        'text': body,
        'status': f'[{getattr(r, "status_code", 0)}]',
        'ok': getattr(r, "status_code", 0) in range(200, 300)
    }


@app.post("/curl_parse")
async def curl_parse(request: Request):
    req = (await request.body()).decode('u8')
    result = ensure_request(req)
    return {'result': result, 'ok': True}


@app.post("/parse")
def parse_rule(kwargs: dict):
    input_object = kwargs['input_object']
    if not input_object:
        return 'Null input_object?'
    rule_json = kwargs['rule']
    rule = CrawlerRule.loads(rule_json)
    # print(rule)
    result = uni.parse(input_object, rule, GLOBAL_RESP)
    return {'type': str(type(result)), 'data': repr(result)}
