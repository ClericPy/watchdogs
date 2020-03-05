import datetime
import re
from asyncio import ensure_future, sleep, wait
from json import dumps, loads
from typing import Optional, Tuple

from torequests.utils import ttime
from uniparser import Crawler
from uniparser.utils import TorequestsAsyncAdapter

from .config import Config
from .models import tasks


def chain_result(item: dict):
    """
    print(
    chain_result({
        '__request__': 'https://www.python.org/dev/peps/pep-0001',
        '__result__': {
            'detail': {
                'title': 'PEP 1 -- PEP Purpose and Guidelines'
            }
        }
    }))
    # {'title': 'PEP 1 -- PEP Purpose and Guidelines'}
    """
    if not isinstance(item, dict):
        return {}
    __result__ = item.pop('__result__', None)
    if __result__ and isinstance(__result__, dict):
        item.pop('__request__', None)
        item.update(chain_result(__result__.popitem()[1]))
    return item


async def crawl(task):
    crawler: Crawler = Config.crawler
    logger = Config.logger
    if logger:
        logger.info(f'Start crawling: {task.name}')
    crawl_result = await crawler.acrawl(task.request_args)
    if crawl_result is None:
        if logger:
            logger.warn(
                f'{task.name} crawl_result is None, maybe crawler rule is not found'
            )
        result = '{"text": "Result is null, please ensure the crawler rule."}'
    else:
        if len(crawl_result) == 1:
            # chain result for __request__ which fetch a new request
            result = chain_result(crawl_result.popitem()[1])
            result = dumps(result, sort_keys=True)
            if logger:
                logger.info(f'{task.name} Crawl success: {str(result)}')
        else:
            msg = 'Crawl result should be a single key dict like: {rule_name: result_dict}'
            logger.error(msg)
            result = msg
    return task, result


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


def find_next_check_time(
        work_hours: str,
        interval: int,
        now: Optional[datetime.datetime] = None,
) -> Tuple[bool, datetime.datetime]:
    if work_hours[0] == '[' and work_hours[-1] == ']':
        work_hours_list = sorted(loads(work_hours))
    else:
        nums = [int(num) for num in re.findall(r'\d+', work_hours)]
        work_hours_list = sorted(range(*nums))
    # find the latest hour fit work_hours, if not exist, return next day 00:00
    now = now or datetime.datetime.now()
    current_hour = now.hour
    if current_hour in work_hours_list:
        # on work hour
        ok = True
        next_check_time = now + datetime.timedelta(seconds=interval)
    else:
        ok = False
        # find the latest hour, or next day earlist hour
        for hour in work_hours_list:
            if hour >= current_hour:
                next_check_time = now.replace(hour=hour)
                break
        else:
            date = now + datetime.timedelta(days=1)
            next_check_time = date.replace(
                hour=work_hours_list[0], minute=0, second=0, microsecond=0)
    return ok, next_check_time


async def crawl_once(task_name=None):
    """task_name means force crawl"""
    crawler: Crawler = Config.crawler
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
    now = datetime.datetime.now()
    update_query = 'update tasks set `last_check_time`=:last_check_time,`next_check_time`=:next_check_time where task_id=:task_id'
    update_values = []
    async for task in db.iterate(query=query):
        # check work hours
        ok, next_check_time = find_next_check_time(task.work_hours or '0, 24',
                                                   task.interval, now)
        if task_name:
            # always crawl for given task_name
            ok = True
        if ok:
            t = ensure_future(crawl(task))
            # add task_name for logger
            t.task_name = task.name
            todo.append(t)
        # update next_check_time
        values = {
            'last_check_time': now,
            'next_check_time': next_check_time,
            'task_id': task.task_id
        }
        update_values.append(values)
        if not ok:
            logger.info(
                f'Task [{task.name}] is not on work, next_check_time reset to {next_check_time}'
            )
    async with Config.db_lock:
        await db.execute_many(query=update_query, values=update_values)
    logger.info(f'Crawling {len(todo)} tasks.')
    if todo:
        done, pending = await wait(todo, timeout=Config.default_crawler_timeout)
        if pending:
            names = [t.name for t in pending]
            logger.error(f'crawl timeout: {names}')
        ttime_now = ttime()
        for t in done:
            task, result = t.result()
            if result != task.latest_result:
                query = UpdateTaskQuery(task.task_id)
                logger.info(f'Updated {task.name}. +++')
                query.add('last_change_time', now)
                query.add('latest_result', result)
                results: list = loads(task.result_list or '[]')
                results.insert(0, {'result': result, 'time': ttime_now})
                query.add('result_list', dumps(results[:task.max_result_count]))
                async with Config.db_lock:
                    await db.execute(**query.kwargs)
        logger.info(
            f'Crawl finished. done: {len(done)}, timeout: {len(pending)}')
    if task_name:
        query = tasks.select().where(tasks.c.name == task_name)
        task = await db.fetch_one(query=query)
        return dict(task)


async def crawler_loop():
    crawler = Crawler(storage=Config.rule_db)
    crawler.uniparser.request_adapter = TorequestsAsyncAdapter(
        default_host_frequency=Config.default_host_frequency)
    Config.logger.info(
        f'Downloader middleware installed: {crawler.uniparser.request_adapter.__class__.__name__}'
    )
    Config.crawler = crawler
    while 1:
        await crawl_once()
        await sleep(Config.check_interval)
