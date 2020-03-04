import datetime
import re
from asyncio import ensure_future, sleep, wait
from json import dumps, loads

from torequests.utils import ttime
from uniparser.crawler import Crawler

from .config import Config


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


async def crawl(task, crawler: Crawler, logger):
    logger.info(f'start crawling {task.name}')
    crawl_result = await crawler.acrawl(task.request_args)
    if crawl_result is None:
        logger.warn(
            f'{task.name} crawl_result is None, maybe crawler rule is not found'
        )
        result = None
    else:
        assert len(
            crawl_result
        ) == 1, 'Crawl result should be a dict as: {rule_name: result_dict}'
        result = chain_result(crawl_result.popitem()[1])
        result = dumps(result, sort_keys=True)
        logger.info(f'{task.name} crawl success: {str(result)}')
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
                    nums = [int(num) for num in re.findall(r'\d+', work_hours)]
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
            ttime_now = ttime()
            for t in done:
                task, result = t.result()
                query = UpdateTaskQuery(task.task_id)
                query.add('last_check_time', now)
                query.add('next_check_time',
                          now + datetime.timedelta(seconds=task.interval))
                if result not in (None, task.latest_result):
                    logger.info(f'{task.name} updated.')
                    query.add('last_change_time', now)
                    query.add('latest_result', result)
                    results: list = loads(task.result_list or '[]')
                    results.insert(0, {'result': result, 'time': ttime_now})
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
