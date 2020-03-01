import datetime
import re
from asyncio import ensure_future, sleep, wait

from uniparser.crawler import Crawler

from orjson import dumps, loads

from .config import Config


def get_result(item: dict):
    if 'result' in item:
        return item['result']
    elif '__result__' in item:
        return get_result(item['__result__'])
    return ''


async def crawl(task, crawler: Crawler, logger):
    logger.info(f'start crawling {task.name}')
    result = await crawler.acrawl(task.request_args)
    if result is None:
        logger.warn(
            f'{task.name} crawl result is None, maybe crawler rule is not found')
    else:
        result = str(get_result(list(result.values())[0]))

    return task, result or ''


class UpdateTaskQuery:
    __slots__ = ('_query', 'values')

    def __init__(self, task_id):
        self._query = []
        self.values = {'task_id': task_id}

    def add(self, key, value):
        self._query.append(f'`{key}`=:{key}')
        self.values[key] = value

    @property
    def set_values(self):
        if self._query:
            return f'set {", ".join(self._query)}'
        else:
            return ''

    @property
    def kwargs(self):
        return {
            'query': f'update tasks {self.set_values} where `task_id`=:task_id',
            'values': self.values
        }


async def crawl_once(tasks, crawler, task_name=None):
    """task_name means force crawl"""
    db = crawler.storage.db
    now = datetime.datetime.now()
    logger = Config.logger
    # sqlite do not has datediff...
    if task_name:
        query = tasks.select().where(tasks.c.enable == 1).where(
            tasks.c.name == task_name)
    else:
        query = tasks.select().where(tasks.c.enable == 1).where(
            tasks.c.next_check_time < now)
    todo = []
    current_hour = datetime.datetime.now().hour
    async with Config.db_lock:
        async for task in db.iterate(query=query):
            if not task_name:
                # check work hours
                work_hours = task.work_hours or '0, 24'
                if work_hours[0] == '[':
                    formated_work_hours = loads(work_hours)
                else:
                    nums = [int(num) for num in re.findall('\d+', work_hours)]
                    formated_work_hours = range(*nums)
                if current_hour not in formated_work_hours:
                    continue
            t = ensure_future(crawl(task, crawler, logger))
            # add task_name for logger
            t.task_name = task.name
            todo.append(t)
    logger.info(f'{len(todo)} tasks crawling.')
    if todo:
        done, pending = await wait(todo, timeout=Config.default_crawler_timeout)
        if pending:
            names = [t.name for t in pending]
            logger.error(f'crawl timeout: {names}')
        async with Config.db_lock:
            now = datetime.datetime.now()
            for t in done:
                task, result = t.result()
                query = UpdateTaskQuery(task.task_id)
                query.add('last_check_time', now)
                query.add('next_check_time',
                          now + datetime.timedelta(seconds=task.interval))
                if result != task.latest_result:
                    logger.info(f'{task.name} updated.')
                    query.add('last_change_time', now)
                    query.add('latest_result', result)
                    results: list = loads(task.result_list or '[]')
                    results.insert(0, result)
                    query.add('result_list',
                              dumps(results[:task.max_result_count]))
                await db.execute(**query.kwargs)
        logger.info(
            f'crawl finished. done: {len(done)}, timeout: {len(pending)}')


async def crawler_loop(tasks, db):
    crawler = Crawler(storage=Config.rule_db)
    while 1:
        await crawl_once(tasks, crawler)
        await sleep(Config.check_interval)
