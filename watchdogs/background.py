from asyncio import ensure_future, sleep
from .utils import check_work_time, solo, try_catch
from .config import Config


async def crawl_chunks(crawl_once):
    loop_num = 0
    while 1:
        loop_num += 1
        has_more = await crawl_once()
        Config.logger.info(f'crawl_once [{loop_num}] finished, has_more: {has_more}')
        if not has_more:
            break


async def background_loop(coro_funcs: list = None):
    while 1:
        # non-block running, and be constrained by SoloLock class
        for func in coro_funcs:
            if func.__name__ == 'crawl_once':
                ensure_future(try_catch(crawl_chunks, func))
            else:
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
