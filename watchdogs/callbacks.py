from abc import ABC, abstractmethod
from json import loads
from logging import getLogger
from traceback import format_exc
from typing import Dict, Type

from .utils import ensure_await_result


class Callback(ABC):
    """
    Constraint: Callback object should has this attribute:
        cls.name: str
        self.callback(task)

    More common notify middleware is coming.
    """
    logger = getLogger('watchdogs')
    # reset by subclass
    name = ''
    doc = ''

    @abstractmethod
    def callback(self, task):
        """task attributes is new crawled"""
        pass


class ServerChanCallback(Callback):
    """
Wechat notify toolkit.

    1. Login with github: http://sc.ftqq.com/
    2. Click http://sc.ftqq.com/?c=code the SCKEY
    3. Set the task.custom_info as: server_chan:{SCKEY}
"""
    name = "server_chan"

    # doc = 'http://sc.ftqq.com/'

    def __init__(self):
        from torequests.dummy import Requests
        self.req = Requests()

    async def callback(self, task):
        name, arg = task.custom_info.split(':', 1)
        if not arg:
            raise ValueError(
                f'{task.name}: custom_info `{task.custom_info}` missing args after `:`'
            )
        latest_result = loads(task.latest_result or '{}')
        text = latest_result.get('text') or ''
        url = latest_result.get('url') or task.origin_url
        title = f'{task.name}#{text[:80]}'
        body = f'{url}\n\n{text}'
        r = await self.req.post(
            f'https://sc.ftqq.com/{arg}.send',
            data={
                'text': title,
                'desp': body
            })
        return r.text


class CallbackHandlerBase(ABC):
    logger = getLogger('watchdogs')

    def __init__(self):
        # lazy init object
        self.callbacks_dict: Dict[str, Type[Callback]] = {}
        for cls in Callback.__subclasses__():
            try:
                assert cls.name
                cls.doc = cls.doc or cls.__doc__
                self.callbacks_dict[cls.name] = cls
            except Exception as err:
                self.logger.error(f'{cls} registers failed: {err!r}')
        self.workers = {cb.name: cb.doc for cb in self.callbacks_dict.values()}

    @abstractmethod
    async def callback(self, task):
        pass

    def get_callback(self, name):
        obj = self.callbacks_dict[name]
        if not isinstance(obj, Callback):
            # here for lazy init
            obj = obj()
            self.callbacks_dict[name] = obj
        return obj


class CallbackHandler(CallbackHandlerBase):

    def __init__(self):
        super().__init__()

    async def callback(self, task):
        custom_info: str = task.custom_info.strip()
        if not custom_info:
            return
        name, arg = custom_info.split(':', 1)
        cb = self.get_callback(name)
        try:
            call_result = await ensure_await_result(cb.callback(task))
            self.logger.info(
                f'{cb.name} callback({arg}) for task {task.name} {call_result}: '
            )
        except Exception:
            self.logger.error(
                f'{cb.name} callback({arg}) for task {task.name} error:\n{format_exc()}'
            )
