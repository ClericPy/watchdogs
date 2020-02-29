import datetime
from asyncio import sleep, wait, ensure_future

from uniparser.crawler import Crawler

from .config import Config
from sqlalchemy import func


async def crawl(task, crawler):
    pass


async def crawl_once(tasks, crawler, task_name=None):
    """task_name means force crawl"""
    db = crawler.storage.db
    now = datetime.datetime.now()
    logger = Config.logger
    # sqlite do not has datediff...
    if task_name:
        query = tasks.select().where(tasks.c.name == task_name)
    else:
        query = tasks.select().where(tasks.c.next_check_time < now)
    todo = []
    async with Config.db_lock:
        async for task in db.iterate(query=query):
            # print(dict(task), 'crawl_once')
            # not reach interval
            logger.info(f'start crawling {task.name}')
            todo.append(ensure_future(crawl(task, crawler)))
            # task.interval = 299
            # query = tasks.update()
            # values = {"name": "example1", "completed": True}
            # await db.execute(query=query, values=values)
    return
    if todo:
        done, pending = wait(todo, timeout=Config.default_crawler_timeout)
        async with Config.db_lock:
            for task in done:
                pass


async def crawler_loop(tasks, db):
    from .models import RuleStorageDB
    rule_db = RuleStorageDB(db)
    crawler = Crawler(storage=rule_db)
    while 1:
        await crawl_once(tasks, crawler)
        await sleep(Config.check_interval)
