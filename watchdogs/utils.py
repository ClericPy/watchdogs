import re
from datetime import datetime
from inspect import isawaitable
from json import loads
from logging import getLogger
from sys import _getframe
from traceback import format_exc
from typing import Optional
from xml.sax.saxutils import escape

logger = getLogger('watchdogs')


async def ensure_await_result(result):
    if isawaitable(result):
        return await result
    return result


def _check_work_time(work_hours, now: Optional[datetime] = None):
    now = now or datetime.now()
    if '==' in work_hours:
        # check work days, using strftime
        fmt, target = work_hours.split('==')
        current = now.strftime(fmt)
        # check current time format equals to target
        return current == target
    elif '!=' in work_hours:
        # check work days, using strftime
        fmt, target = work_hours.split('!=')
        current = now.strftime(fmt)
        # check current time format equals to target
        return current != target
    else:
        # other hours format
        current_hour = now.hour
        if work_hours[0] == '[' and work_hours[-1] == ']':
            work_hours_list = sorted(loads(work_hours))
        else:
            nums = [int(num) for num in re.findall(r'\d+', work_hours)]
            work_hours_list = sorted(range(*nums))
        # check if current_hour is work hour
        return current_hour in work_hours_list


def check_work_time(work_hours, now: Optional[datetime] = None):
    """Check time if fit work_hours.

    :: Test Code

        from watchdogs.utils import check_work_time, datetime

        now = datetime.strptime('2020-03-14 11:47:32', '%Y-%m-%d %H:%M:%S')

        oks = [
            '0, 24',
            '[1, 2, 3, 11]',
            '[1, 2, 3, 11];%Y==2020',
            '%d==14',
            '16, 24|[11]',
            '16, 24|%M==47',
            '%M==46|%M==47',
            '%H!=11|%d!=12',
            '16, 24|%M!=41',
        ]

        for work_hours in oks:
            ok = check_work_time(work_hours, now)
            print(ok, work_hours)
            assert ok

        no_oks = [
            '0, 5',
            '[1, 2, 3, 5]',
            '[1, 2, 3, 11];%Y==2021',
            '%d==11',
            '16, 24|[12]',
            '%M==17|16, 24',
            '%M==46|[1, 2, 3]',
            '%H!=11&%d!=12',
            '%M!=46;%M!=47',
        ]

        for work_hours in no_oks:
            ok = check_work_time(work_hours, now)
            print(ok, work_hours)
            assert not ok


    """
    now = now or datetime.now()
    if '|' in work_hours:
        if '&' in work_hours or ';' in work_hours:
            raise ValueError('| can not use with "&" or ";"')
        return any((_check_work_time(partial_work_hour, now)
                    for partial_work_hour in work_hours.split('|')))
    else:
        if ('&' in work_hours or ';' in work_hours) and '|' in work_hours:
            raise ValueError('| can not use with "&" or ";"')
        return all((_check_work_time(partial_work_hour, now)
                    for partial_work_hour in re.split('&|;', work_hours)))


def get_watchdog_result(item):
    """
    Parse result format like:
    {'text': 'xxx'}
    {'text': 'xxx', 'url': 'xxx'}
    {'rule_name': {'text': 'xxx'}}
    {'__result__': {'rule_name': {'text': 'xxx'}}}

def test_result_schema():
    # standard result
    result = get_watchdog_result({
        'url': 'https://www.python.org/dev/peps/pep-0001',
        'text': 'text'
    })
    # print(result)
    assert result == {
        'url': 'https://www.python.org/dev/peps/pep-0001',
        'text': 'text'
    }
    # only text
    result = get_watchdog_result('https://www.python.org/dev/peps/pep-0001')
    # print(result)
    assert result == {'text': 'text not found'}
    # embed request
    result = get_watchdog_result({
        '__request__': 'https://www.python.org/dev/peps/pep-0001',
        '__result__': {
            'detail': {
                'text': 'PEP 1 -- PEP Purpose and Guidelines'
            }
        }
    })
    # print(result)
    assert result == {'text': 'PEP 1 -- PEP Purpose and Guidelines'}
    # embed request list
    result = get_watchdog_result({
        '__request__': 'https://www.python.org/dev/peps/pep-0001',
        '__result__': {
            'detail': [{
                'text': 'PEP 1 -- PEP Purpose and Guidelines'
            }]
        }
    })
    # print(result)
    assert result == [{'text': 'PEP 1 -- PEP Purpose and Guidelines'}]
    # embed request list2
    result = get_watchdog_result({
        '__request__': 'https://www.python.org/dev/peps/pep-0001',
        '__result__': {
            'rule_name': {
                '__result__': {
                    'detail': [{
                        'text': 'PEP 1 -- PEP Purpose and Guidelines'
                    }]
                }
            }
        }
    })
    # print(result)
    assert result == [{'text': 'PEP 1 -- PEP Purpose and Guidelines'}]
    # child rule result
    result = get_watchdog_result({
        'url': 'https://www.python.org/dev/peps/pep-0001',
        'text': 'text'
    })
    # print(result)
    assert result == {
        'text': 'text',
        'url': 'https://www.python.org/dev/peps/pep-0001'
    }
    result = get_watchdog_result({
        'list': {
            'detail': [{
                'text': 'Wake up to WonderWidgets!',
                'url': 'all'
            }, {
                'text': 'Overview',
                'url': 'all'
            }]
        }
    })
    # print(result)
    assert result == [{
        'text': 'Wake up to WonderWidgets!',
        'url': 'all'
    }, {
        'text': 'Overview',
        'url': 'all'
    }]

    """
    result = {'text': 'text not found'}
    if isinstance(item, dict):
        __result__ = item.pop('__result__', None)
        if __result__:
            return get_watchdog_result(__result__.popitem()[1])
        text = item.get('text')
        if text is None:
            return get_watchdog_result(item.popitem()[1])
        result = {'text': str(text)}
        url = item.get('url')
        if url:
            result['url'] = url
    elif isinstance(item, (list, tuple)):
        result = [get_watchdog_result(i) for i in item]
    return result


class SoloLock:

    def __init__(self):
        self.runnings: set = set()

    @property
    def current_name(self):
        return _getframe(2).f_code.co_name

    def acquire(self, name=None):
        name = name or self.current_name
        if name in self.runnings:
            raise RuntimeError(f'[{name}] is still running.')
        self.runnings.add(name)

    def release(self, name=None):
        name = name or self.current_name
        self.runnings.discard(name)

    def __enter__(self):
        self.acquire(self.current_name)
        return self

    def __exit__(self, *args):
        self.release(self.current_name)
        return self


async def try_catch(func, *args, **kwargs):
    try:
        return await ensure_await_result(func(*args, **kwargs))
    except Exception as err:
        logger.error(
            f'Catch an error while running {func.__name__}: {format_exc()}')
        return err


def gen_rss(data):
    nodes = []
    channel = data['channel']
    item_keys = ['title', 'description', 'link', 'guid', 'pubDate']
    for item in data['items']:
        item_nodes = []
        for key in item_keys:
            value = item.get(key)
            if value:
                item_nodes.append(f'<{key}>{escape(value)}</{key}>')
        nodes.append(''.join(item_nodes))
    items_string = ''.join((f'<item>{tmp}</item>' for tmp in nodes))
    return rf'''<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>{channel['title']}</title>
  <link>{channel['link']}</link>
  <description>{channel['description']}</description>
  <image>
    <url>{channel['link']}/static/img/favicon.ico</url>
    <title>{channel['title']}</title>
    <link>{channel['link']}</link>
    <width>32</width>
    <height>32</height>
   </image>
  {items_string}
</channel>
</rss>
'''


solo = SoloLock()
