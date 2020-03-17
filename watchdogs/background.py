from asyncio import ensure_future, sleep
from .utils import check_work_time, solo, try_catch
from .config import Config


async def background_loop(coro_funcs: list = None):
    while 1:
        # non-block running, and be constrained by SoloLock class
        for func in coro_funcs:
            ensure_future(try_catch(func))
        await sleep(Config.check_interval)


async def db_backup_handler():
    logger = Config.logger
    if check_work_time(Config.db_backup_time):
        logger.warning(f'Backup DB start: {Config.db_backup_time}.')
        # may raise solo error
        with solo:
            result = await try_catch(Config.db_backup_function)
        logger.info(f'Backup DB finished: {result!r}')
