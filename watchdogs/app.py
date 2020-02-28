from fastapi import FastAPI

from .settings import release_app, setup_app
from .uniparser_app import sub_app

app = FastAPI()

app.mount("/watchdog", sub_app)


@app.on_event("startup")
async def startup():
    await setup_app(app)


@app.on_event("shutdown")
async def shutdown():
    await release_app(app)
