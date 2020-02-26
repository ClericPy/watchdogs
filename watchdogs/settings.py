from pathlib import Path

from databases import Database


class GlobalConfig(object):
    CONFIG_DIR = Path.home() / 'watchdogs'
    if not CONFIG_DIR.is_dir():
        CONFIG_DIR.mkdir()
    db = None
    admin = None
    password = None


def setup_db(db_url=None):
    if db_url is None:
        sqlite_path = GlobalConfig.CONFIG_DIR / 'storage.sqlite'
        db_url = f'sqlite:///{sqlite_path}'
    GlobalConfig.db = Database(db_url)


def setup_uniparser():
    from orjson import JSONDecodeError, dumps, loads
    from uniparser.config import GlobalConfig

    GlobalConfig.JSONDecodeError = JSONDecodeError
    GlobalConfig.json_dumps = dumps
    GlobalConfig.json_loads = loads


def setup(db_url=None, admin=None, password=None):
    GlobalConfig.admin = admin
    GlobalConfig.password = password
    setup_uniparser()
    setup_db(db_url)


async def setup_app():
    db = GlobalConfig.db
    if db:
        await db.connect()
        from .models import tasks, create_table
        create_table(str(db.url))
        query = tasks.insert()
        values = {"name": "example1", "request_args": 'lala'}
        await db.execute(query=query, values=values)


async def release_app():
    if GlobalConfig.db:
        await GlobalConfig.db.disconnect()
