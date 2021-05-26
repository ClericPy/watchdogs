from abc import ABC, abstractmethod
from json import loads
from logging import getLogger
from traceback import format_exc
from typing import Dict, Type

from torequests.utils import ttime

from .utils import ensure_await_result


class CallbackHandlerBase(ABC):
    logger = getLogger('watchdogs')

    def __init__(self):
        # lazy init object
        self.callbacks_dict: Dict[str, Type[Callback]] = {}
        for cls in Callback.__subclasses__():
            try:
                assert cls.name is not None
                cls.doc = cls.doc or cls.__doc__
                self.callbacks_dict[cls.name] = cls
            except Exception as err:
                self.logger.error(f'{cls} registers failed: {err!r}')
        self.workers = {cb.name: cb.doc for cb in self.callbacks_dict.values()}

    @abstractmethod
    async def callback(self, task):
        pass

    def get_callback(self, name):
        obj = self.callbacks_dict.get(name)
        if not obj:
            # not found callback
            return None
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
        name = custom_info.split(':', 1)[0]
        cb = self.get_callback(name) or self.get_callback('')
        if not cb:
            # not found callback, ignore
            return
        try:
            call_result = await ensure_await_result(cb.callback(task))
            self.logger.info(
                f'{cb.name or "default"} callback({custom_info}) for task {task.name} {call_result}: '
            )
        except Exception:
            self.logger.error(
                f'{cb.name or "default"} callback({custom_info}) for task {task.name} error:\n{format_exc()}'
            )


class Callback(ABC):
    """
    Constraint: Callback object should has this attribute:
        cls.name: str
        self.callback(task)
    if name == '': It's the default callback for null custom info.
    More common notify middleware is coming.
    """
    logger = getLogger('watchdogs')
    # reset by subclass
    name: str = None
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
    TEXT_SLICE_LENGTH = 200

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
        title = f'{task.name}#{text[:self.TEXT_SLICE_LENGTH]}'
        body = f'{url}\n\n{text}'
        oks = []
        for key in set(arg.strip().split()):
            if not key or not key.strip():
                continue
            key = key.strip()
            r = await self.req.post(f'https://sc.ftqq.com/{key}.send',
                                    data={
                                        'text': title,
                                        'desp': body
                                    })
            self.logger.info(f'ServerChanCallback ({key}): {r.text}')
            oks.append((key, bool(r)))
        return f'{len(oks)} sended, {oks}'


class DingTalkCallback(Callback):
    """
DingDing robot notify toolkit. Will auto check msg type as text / card.

    1. Create a group.
    2. Create a robot which contains word ":"
    3. Set the task.custom_info as: dingding:{access_token}

    Doc: https://ding-doc.dingtalk.com/doc#/serverapi2/qf2nxq/e9d991e2
"""
    name = "dingding"

    def __init__(self):
        from torequests.dummy import Requests
        self.req = Requests()

    def make_data(self, task):
        latest_result = loads(task.latest_result or '{}')
        title = latest_result.get('title') or ''
        url = latest_result.get('url') or task.origin_url
        text = latest_result.get('text') or ''
        cover = latest_result.get('cover') or ''
        if cover:
            text = f'![cover]({cover})\n{text}'
        if url or cover:
            # markdown
            title = f'# {task.name}: {title}\n> {ttime()}'
            return {
                "actionCard": {
                    "title": title,
                    "text": f'{title}\n\n{text}',
                    "singleTitle": "Read More",
                    "singleURL": url
                },
                "msgtype": "actionCard"
            }
        return {
            "msgtype": "text",
            "text": {
                "content": f"{task.name}: {title}\n{text}"
            }
        }

    async def callback(self, task):
        name, arg = task.custom_info.split(':', 1)
        if not arg:
            raise ValueError(
                f'{task.name}: custom_info `{task.custom_info}` missing args after `:`'
            )

        data = self.make_data(task)
        oks = []
        for access_token in set(arg.strip().split()):
            if not access_token or not access_token.strip():
                continue
            access_token = access_token.strip()
            r = await self.req.post(
                f'https://oapi.dingtalk.com/robot/send?access_token={access_token}',
                json=data)
            self.logger.info(
                f'{self.__class__.__name__} ({access_token}): {r.text}')
            oks.append((access_token, bool(r)))
        return f'{len(oks)} sended, {oks}'
