# -*- coding: utf-8 -*-

from asyncio import ensure_future, wait
from datetime import datetime, timedelta
from json import JSONDecodeError, dumps, loads
from traceback import format_exc
from typing import Optional, Tuple

from torequests.utils import timeago, ttime
from uniparser import Crawler, RuleNotFoundError

from .config import Config
from .models import Database, Task, query_feeds, query_tasks, tasks
from .utils import check_work_time, get_watchdog_result, solo, try_catch


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
        task: Task,
        now: Optional[datetime] = None,
) -> Tuple[bool, datetime]:
    '''
Three kinds of format:

        1. Tow numbers splited by ', ', as work_hours:
            0, 24           means from 00:00 ~ 23:59, for everyday
        2. JSON list of int, as work_hours:
            [1, 19]         means 01:00~01:59 a.m.  07:00~07:59 p.m. for everyday
        3. Standard strftime format, as work_days:
            > Split work_hours by '==', then check
                if datetime.now().strftime(wh[0]) == wh[1]
            %A==Friday      means each Friday
            %m-%d==03-13    means every year 03-13
            %H==05          means everyday morning 05:00 ~ 05:59
        4. Mix up work_days and work_hours:
            > Split work_days and work_hours with ';'/'&' => 'and', '|' => 'or'.
            > Support == for equal, != for unequal.
            %w==5;20, 24        means every Friday 20:00 ~ 23:59
            [1, 2, 15];%w==5    means every Friday 1 a.m. 2 a.m. 3 p.m., the work_hours is on the left side.
            %w==5|20, 24        means every Friday or everyday 20:00 ~ 23:59
            %w==5|%w==2         means every Friday or Tuesday
            %w!=6&%w!=0         means everyday except Saturday & Sunday.
        5. Set a ensure change interval
            > If work_hours string endswith `#` and `x` seconds, will check the next_change_time first.
            > In other words, I am very sure that the interval between two changes is more than `x` seconds
            > So the crawler of this task will not run until the time is `last_change_time + change_interval`
            %w==5#86400        means every Friday if it didn't change within 1 day
            0, 24#3600         means each hour if it didn't change within this hour. The task will only be crawled once if it has changed.
    '''
    # find the latest hour fit work_hours, if not exist, return next day 00:00
    now = now or datetime.now()
    work_hours = task.work_hours or '0, 24'
    if '#' in work_hours:
        # check if changed
        last_change_time = task.last_change_time or datetime.fromtimestamp(0)
        # split work_hours and change_interval
        work_hours, change_interval_str = work_hours.split('#')
        change_interval = int(change_interval_str)
        # not fit change interval, will wait for left seconds.
        next_change_time = last_change_time + timedelta(seconds=change_interval)
        if now < next_change_time:
            Config.logger.info(
                f'Task [{task.name}] has changed in {timeago(change_interval, accuracy=1, format=1, short_name=1)} ago.'
            )
            return False, next_change_time

    need_crawl = check_work_time(work_hours, now)
    if need_crawl:
        # current time is need_crawl, next_check_time is now+interval
        next_check_time = now + timedelta(seconds=task.interval)
        return need_crawl, next_check_time
    else:
        # current time is not need_crawl
        next_check_time = now
        # time machine to update next_check_time fast
        for _ in range(60):
            # next interval
            next_check_time = next_check_time + timedelta(seconds=task.interval)
            _need_crawl = check_work_time(work_hours, next_check_time)
            if _need_crawl:
                # current time is still False, but next_check_time is True
                break
        return need_crawl, next_check_time


async def crawl(task: Task):
    crawler: Crawler = Config.crawler
    logger = Config.logger
    logger.info(f'Start crawling: {task.name}')
    crawl_result = await try_catch(crawler.acrawl, task.request_args)
    error = ''
    if isinstance(crawl_result, RuleNotFoundError):
        error = repr(crawl_result)
        logger.error(f'{task.name}: {error}')
        result_list = [{"text": error}]
    elif isinstance(crawl_result, BaseException):
        error = getattr(crawl_result, 'text', repr(crawl_result))
        logger.error(f'{task.name}: {error}')
        result_list = None
    else:
        if len(crawl_result) == 1:
            # crawl_result schema: {rule_name: list_or_dict}
            formated_result = get_watchdog_result(
                item=crawl_result.popitem()[1])
            if formated_result == {'text': 'text not found'}:
                error = f'{task.name} text not found, crawl result given: {crawl_result}'
                logger.error(error)
                result_list = None
            else:
                if isinstance(formated_result, list):
                    result_list = formated_result
                else:
                    result_list = [formated_result]
                # use force crawl one web UI for more log
                logger.info(f'{task.name} Crawl success: {result_list}'[:150])
        else:
            error = 'Invalid crawl_result against schema {rule_name: [{"text": "Required", "url": "Optional", "__key__": "Optional"}]}, given is %r' % crawl_result
            logger.error(f'{task.name}: {error}')
            result_list = [{"text": error}]
    return task, error, result_list


async def _crawl_once(task_name: Optional[str] = None, chunk_size: int = 20):
    """task_name means force crawl"""
    db: Database = Config.db
    now = datetime.now()
    logger = Config.logger
    logger.info(f'crawl_once task_name={task_name} start.')
    # sqlite do not has datediff...
    if task_name:
        query = tasks.select().where(tasks.c.name == task_name)
    else:
        query = tasks.select().where(tasks.c.enable == 1).where(
            tasks.c.next_check_time <= now)
        query = query.limit(chunk_size)
    todo = []
    now = datetime.now()
    update_values = []
    CLEAR_CACHE_NEEDED = False
    fetched_tasks = await db.fetch_all(query=query)
    has_more = len(fetched_tasks) >= chunk_size
    for _task in fetched_tasks:
        task = Task(**dict(_task))
        # check work hours
        need_crawl, next_check_time = find_next_check_time(task, now)
        if task_name:
            # always crawl for given task_name
            need_crawl = True
        if need_crawl:
            t = ensure_future(crawl(task))
            # add task_name for logger
            setattr(t, 'task_name', task.name)
            todo.append(t)
        # update next_check_time
        values = {
            'last_check_time': now,
            'next_check_time': next_check_time,
            'task_id': task.task_id
        }
        # update task variable for callback
        task.__dict__.update(values)
        update_values.append(values)
        if not need_crawl:
            logger.info(
                f'Task [{task.name}] is not on work time, next_check_time reset to {next_check_time}'
            )
    update_query = 'update tasks set `last_check_time`=:last_check_time,`next_check_time`=:next_check_time where task_id=:task_id'
    await db.execute_many(query=update_query, values=update_values)
    if update_values:
        CLEAR_CACHE_NEEDED = True
    logger.info(f'crawl_once crawling {len(todo)} valid tasks.')
    if todo:
        done, pending = await wait(todo, timeout=Config.default_crawler_timeout)
        if pending:
            names = [getattr(t, 'task_name', None) for t in pending]
            logger.error(f'crawl timeout {len(names)}: {names}')
        ttime_now = ttime()
        changed_tasks = []
        update_counts = 0
        crawl_errors = []
        for t in done:
            task, error, result_list = t.result()
            if error != task.error:
                crawl_errors.append({'task_id': task.task_id, 'error': error})
            if error or result_list is None:
                # ignore update this task
                continue
            # compare latest_result and new list
            # later first, just like the saved result_list sortings
            old_latest_result = loads(task.latest_result)
            # try to use the __key__
            old_latest_result_key = old_latest_result.get(
                '__key__', old_latest_result)
            # list of dict
            to_insert_result_list = []
            for result in result_list:
                result_key = result.get('__key__', result)
                if result_key == old_latest_result_key:
                    break
                to_insert_result_list.append(result)
            if to_insert_result_list:
                # update db
                update_counts += 1
                # new result updated
                query = UpdateTaskQuery(task.task_id)
                # JSON
                new_latest_result = dumps(to_insert_result_list[0],
                                          sort_keys=True)
                query.add('latest_result', new_latest_result)
                query.add('last_change_time', now)
                try:
                    old_result_list = loads(
                        task.result_list) if task.result_list else []
                except JSONDecodeError:
                    old_result_list = []
                # older insert first, keep the newer is on the top
                for result in to_insert_result_list[::-1]:
                    # result is dict, not json string
                    old_result_list.insert(0, {
                        'result': result,
                        'time': ttime_now
                    })
                new_result_list = dumps(old_result_list[:task.max_result_count])
                query.add('result_list', new_result_list)
                logger.info(f'[Updated] {task.name}. +++')
                await db.execute(**query.kwargs)
                task.latest_result = new_latest_result
                task.last_change_time = now
                task.result_list = new_result_list
                changed_tasks.append(task)
        if crawl_errors:
            update_query = 'update tasks set `error`=:error where task_id=:task_id'
            await db.execute_many(query=update_query, values=crawl_errors)
        logger.info(
            f'Crawl task_name={task_name} finished. Crawled: {len(done)}, Error: {len(crawl_errors)}, Timeout: {len(pending)}, Update: {update_counts}.{" +++" if update_counts else ""}'
        )
        for task in changed_tasks:
            ensure_future(try_catch(Config.callback_handler.callback, task))
        await save_feeds(changed_tasks, db, since_time=ttime_now)
    else:
        logger.info(f'Crawl task_name={task_name} finished. 0 todo.')
    if CLEAR_CACHE_NEEDED:
        logger.info('Clear cache for crawling new tasks.')
        query_tasks.cache_clear()
    if task_name:
        query = tasks.select().where(tasks.c.name == task_name)
        _task = await db.fetch_one(query=query)
        return dict(_task)
    else:
        return has_more


async def crawl_once(task_name: Optional[str] = None):
    if task_name is not None:
        return await _crawl_once(task_name)
    with solo:
        result = await try_catch(_crawl_once, task_name)
        return result


async def save_feeds(tasks, db, since_time=None):
    if not tasks:
        return
    try:
        values = []
        for task in tasks:
            result_list = loads(task.result_list) if task.result_list else []
            if not result_list:
                continue
            for index, item in enumerate(result_list):
                _result = item.get('result')
                if not _result:
                    continue
                item_time = item.get('time', '')
                if since_time:
                    if item_time and item_time < since_time:
                        continue
                elif index > 0:
                    break
                text = _result.get('title') or _result.get('text') or ''
                value = {
                    'task_id': task.task_id,
                    'name': task.name,
                    'text': text,
                    'url': _result.get('url') or task.origin_url,
                    'ts_create': datetime.now(),
                }
                values.append(value)

        query = "INSERT INTO feeds (`task_id`, `name`, `text`, `url`, `ts_create`) values (:task_id, :name, :text, :url, :ts_create)"
        result = await db.execute_many(query=query, values=values)
        Config.logger.info(f'Insert task logs success: ({len(values)})')
        query_feeds.cache_clear()
        return result
    except Exception:
        Config.logger.error(f'Inserting task logs failed: {format_exc()}')
