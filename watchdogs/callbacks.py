from abc import ABC, abstractmethod
from inspect import isawaitable
from json import loads
from traceback import format_exc
from typing import Dict

from .config import Config


class Callback(ABC):
    """
    Constraint: subclasses should has this attribute:
        cls.name: str
        self.callback(task)

    More common notify middleware is coming.
    """

    @abstractmethod
    def callback(self, task):
        """task attributes is new crawled"""
        pass

    @property
    def logger(self):
        return Config.logger


class ServerChanCallback(Callback):
    """for wechat notify"""
    name = "server_chan"
    doc = 'http://sc.ftqq.com/'

    def __init__(self):
        from torequests.dummy import Requests
        self.req = Requests()

    async def callback(self, task):
        name, arg = task.custom_info.split(':', 1)
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


class CallbackHandler(object):

    def __init__(self):
        self.callback_objects: Dict[str, Callback] = {}
        for cls in Callback.__subclasses__():
            if not hasattr(cls, 'name'):
                self.logger.error(f'{cls} missing class attribute: `name`.')
                continue
            self.callback_objects[cls.name] = cls()

    @property
    def workers(self) -> str:
        return '\n'.join([
            f'{str(index)+".":<3}{name:<10}: {obj.__class__.__name__}'
            for index, (name,
                        obj) in enumerate(self.callback_objects.items(), 1)
        ])

    @property
    def logger(self):
        return Config.logger

    async def callback(self, task):
        custom_info: str = task.custom_info.strip()
        if not custom_info:
            return
        name, arg = custom_info.split(':', 1)
        cb = self.callback_objects.get(name)
        if not cb:
            self.logger.info(f'callback not found: {name}')
            return
        try:
            call_result = cb.callback(task)
            if isawaitable(call_result):
                call_result = await call_result
            else:
                call_result = call_result
            self.logger.info(
                f'{cb.name} callback({arg}) for task {task.name} {call_result}: '
            )
        except Exception:
            self.logger.error(
                f'{cb.name} callback({arg}) for task {task.name} error:\n{format_exc()}'
            )
