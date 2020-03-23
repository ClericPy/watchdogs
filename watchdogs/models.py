from datetime import datetime
from traceback import format_exc
from typing import Optional, Tuple

import sqlalchemy
from async_lru import alru_cache
from databases import Database
from pydantic import BaseModel
from sqlalchemy.sql import func, text
from uniparser import CrawlerRule, HostRule
from uniparser.crawler import RuleStorage, get_host

from .config import Config
from .utils import ignore_error

metadata = sqlalchemy.MetaData()
date0 = datetime.strptime('1970-01-01 08:00:00', '%Y-%m-%d %H:%M:%S')
# server_default works instead of default, issue: https://github.com/encode/databases/issues/72
tasks = sqlalchemy.Table(
    "tasks",
    metadata,
    sqlalchemy.Column(
        'task_id', sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column(
        "name", sqlalchemy.String(64), nullable=False, index=True, unique=True),
    sqlalchemy.Column(
        "enable", sqlalchemy.Integer, server_default=text('1'), nullable=False),
    sqlalchemy.Column(
        "tag", sqlalchemy.String(128), server_default="default",
        nullable=False),
    sqlalchemy.Column("error", sqlalchemy.TEXT),
    sqlalchemy.Column("request_args", sqlalchemy.TEXT, nullable=False),
    sqlalchemy.Column(
        "origin_url",
        sqlalchemy.String(1024),
        nullable=False,
        server_default=""),
    sqlalchemy.Column(
        "interval",
        sqlalchemy.Integer,
        server_default=text('300'),
        nullable=False),
    sqlalchemy.Column(
        "work_hours",
        sqlalchemy.String(32),
        server_default='0, 24',
        nullable=False),
    sqlalchemy.Column(
        "max_result_count",
        sqlalchemy.Integer,
        server_default=text('10'),
        nullable=False),
    sqlalchemy.Column("latest_result", sqlalchemy.TEXT),
    sqlalchemy.Column("result_list", sqlalchemy.TEXT),  # JSON list
    sqlalchemy.Column(
        "last_check_time",
        sqlalchemy.DATETIME,
        server_default="1970-01-01 08:00:00",
        nullable=False),
    sqlalchemy.Column(
        "next_check_time",
        sqlalchemy.DATETIME,
        server_default="1970-01-01 08:00:00",
        nullable=False),
    sqlalchemy.Column(
        "last_change_time",
        sqlalchemy.DATETIME,
        server_default="1970-01-01 08:00:00",
        index=True,
        nullable=False),
    sqlalchemy.Column("custom_info", sqlalchemy.TEXT),
)
host_rules = sqlalchemy.Table(
    "host_rules",
    metadata,
    sqlalchemy.Column('host', sqlalchemy.String(128), primary_key=True),
    sqlalchemy.Column('host_rule', sqlalchemy.TEXT),
)
metas = sqlalchemy.Table(
    "metas",
    metadata,
    sqlalchemy.Column('key', sqlalchemy.String(64), primary_key=True),
    sqlalchemy.Column('value', sqlalchemy.TEXT),
)
if Config.db_url.startswith('mysql://'):
    for table in [tasks, host_rules, metas]:
        table.append_column(
            sqlalchemy.Column(
                "ts_create",
                sqlalchemy.DATETIME,
                server_default=func.now(),
                nullable=False))
        table.append_column(
            sqlalchemy.Column(
                "ts_update",
                sqlalchemy.DATETIME,
                server_default=func.now(),
                onupdate=func.now(),
                nullable=False))


def create_tables(db_url):
    try:
        engine = sqlalchemy.create_engine(db_url)
        metadata.create_all(engine)
        # backward compatibility for tasks table without error column
        sqls = [
            'ALTER TABLE `tasks` ADD COLUMN `error` TEXT',
            'CREATE INDEX change_time_idx ON tasks (last_change_time)',
        ]
        if Config.db_url.startswith('mysql://'):
            sqls.extend([
                'ALTER TABLE `tasks` ADD COLUMN `ts_create` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP',
                'ALTER TABLE `host_rules` ADD COLUMN `ts_create` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP',
                'ALTER TABLE `metas` ADD COLUMN `ts_create` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP',
                'ALTER TABLE `tasks` ADD COLUMN `ts_update` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
                'ALTER TABLE `host_rules` ADD COLUMN `ts_update` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
                'ALTER TABLE `metas` ADD COLUMN `ts_update` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
            ])
        for sql in sqls:
            ignore_error(engine.execute, sql)
    except Exception:
        Config.logger.critical(f'Fatal error on creating Table: {format_exc()}')
        import os
        os._exit(1)


class RuleStorageDB(RuleStorage):

    def __init__(self, db):
        self.db = db
        self.logger = Config.logger

    async def commit(self):
        pass

    async def get_host_rule(self, host: str, default=None):
        query = "SELECT host_rule FROM host_rules WHERE host = :host"
        host_rule = await self.db.fetch_one(query=query, values={"host": host})
        if host_rule:
            return HostRule.loads(host_rule[0])
        else:
            return default

    async def find_crawler_rule(self, url, method='find') -> CrawlerRule:
        if not url:
            return None
        host = get_host(url)
        host_rule = await self.get_host_rule(host)
        if host_rule:
            return host_rule.find(url)

    async def add_crawler_rule(self, rule: CrawlerRule, commit=None):
        if isinstance(rule, str):
            rule = CrawlerRule.loads(rule)
        elif isinstance(rule, dict) and not isinstance(rule, CrawlerRule):
            rule = CrawlerRule(**rule)
        if not rule.get('regex'):
            raise ValueError('regex should not be null')
        url = rule.get('request_args', {}).get('url')
        if not url:
            self.logger.error(f'[Rule] {rule["name"]} not found url.')
            return False
        host = get_host(url)
        if not host:
            return False
        exist_host_rule = await self.get_host_rule(host)
        if exist_host_rule:
            exist_host_rule.add_crawler_rule(rule)
            query = "update host_rules set host_rule=:host_rule_string WHERE host = :host"
            return await self.db.execute(
                query=query,
                values={
                    'host_rule_string': exist_host_rule.dumps(),
                    'host': host
                })
        else:
            host_rule = HostRule(host)
            host_rule.add_crawler_rule(rule)
            query = "INSERT INTO host_rules (host, host_rule) values (:host, :host_rule_string)"
            return await self.db.execute(
                query=query,
                values={
                    'host_rule_string': host_rule.dumps(),
                    'host': host
                })

    async def pop_crawler_rule(self, rule: CrawlerRule, commit=False):
        query = "SELECT host_rule FROM host_rules"
        host = get_host(rule['request_args'].get('url'))
        values = {}
        if host:
            query += ' WHERE host = :host'
            values['host'] = host
        rows = await self.db.fetch_all(query=query, values=values)
        for row in rows:
            host_rule = HostRule.loads(row.host_rule)
            crawler_rule = host_rule.pop_crawler_rule(rule['name'])
            if crawler_rule:
                # update host_rule
                await self.add_host_rule(host_rule)
                return crawler_rule

    async def add_host_rule(self, rule: HostRule, commit=None):
        """insert or update HostRule"""
        # some sql not support upsert: insert replace, replace into, on conflict
        query = "SELECT host_rule FROM host_rules WHERE host = :host"
        exist_host_rule = await self.get_host_rule(rule['host'])
        if exist_host_rule:
            query = "update host_rules set host_rule=:host_rule_string WHERE host = :host"
            return await self.db.execute(
                query=query,
                values={
                    'host_rule_string': rule.dumps(),
                    'host': rule['host']
                })
        else:
            query = "INSERT INTO host_rules (host, host_rule) values (:host, :host_rule_string)"
            return await self.db.execute(
                query=query,
                values={
                    'host_rule_string': rule.dumps(),
                    'host': rule['host']
                })

    async def pop_host_rule(self, host: str, commit=None):
        exist_host_rule = await self.get_host_rule(host)
        host_rule = HostRule.loads(exist_host_rule) if exist_host_rule else None
        if host_rule:
            query = "delete FROM host_rules WHERE host = :host"
            await self.db.execute(query=query, values={'host': host})
        return host_rule


class TaskController:

    def __init__(self, db):
        self.db = db
        self.logger = Config.logger


class Task(BaseModel):
    task_id: Optional[int] = None
    name: str
    enable: int = 0
    tag: str = 'default'
    error: str = ''
    request_args: str
    origin_url: str = ''
    interval: int = 300
    work_hours: str = '0, 24'
    max_result_count: int = 10
    latest_result: str = '{}'
    result_list = '[]'
    last_check_time: datetime = date0
    next_check_time: datetime = date0
    last_change_time: datetime = date0
    custom_info: str = ''
    if Config.db_url.startswith('mysql://'):
        ts_create: Optional[datetime] = datetime.now()
        ts_update: Optional[datetime] = datetime.now()


@alru_cache()
async def query_tasks(
        task_name: Optional[str] = None,
        task_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 30,
        order_by: str = 'last_change_time',
        sort: str = 'desc',
        tag: str = '',
        task_ids: Tuple[int] = None,
) -> Tuple[list, bool]:
    offset = page_size * (page - 1)
    query = tasks.select()
    if task_ids:
        query = query.where(tasks.c.task_id.in_(task_ids))
    else:
        if task_id is not None:
            query = query.where(tasks.c.task_id == task_id)
        if task_name is not None:
            query = query.where(tasks.c.name == task_name)
        if tag:
            query = query.where(tasks.c.tag == tag)
    if order_by and sort:
        ob = getattr(tasks.c, order_by, None)
        if ob is None:
            raise ValueError(f'bad order_by {order_by}')
        if sort.lower() == 'desc':
            ob = sqlalchemy.desc(ob)
        elif sort.lower() == 'asc':
            ob = sqlalchemy.asc(ob)
        else:
            raise ValueError(
                f"bad sort arg {sort} not in ('desc', 'asc', 'DESC', 'ASC')")
        query = query.order_by(ob)
    query = query.limit(page_size + 1).offset(offset)
    _result = await Config.db.fetch_all(query=query)
    has_more = len(_result) > page_size
    result = [dict(i) for i in _result][:page_size]
    Config.logger.info(
        f'[Query] {len(result)} tasks (has_more={has_more}): {query}')
    return result, has_more


class Metas(object):
    """Save & Load some variables with db"""

    def __init__(self, db: Database):
        self.db = db

    async def set(self, key, value):
        query = 'replace into metas (`key`, `value`) values (:key, :value)'
        await Config.db.execute(query, values={'key': key, 'value': value})
        self.clear_cache()
        if (await self.get(key)) == value:
            return True
        else:
            return False

    async def remove(self, key):
        query = 'delete from metas where `key`=:key'
        await Config.db.execute(query, values={'key': key})
        self.clear_cache()
        if not (await self.get(key)):
            return True
        else:
            return False

    @alru_cache()
    async def _get(self, key, default=None):
        query = 'select `value` from metas where `key`=:key'
        result = await self.db.fetch_one(query, values={'key': key})
        if result:
            return result.value
        else:
            return default

    async def get(self, key, default=None, cache=True):
        if not cache:
            self.clear_cache()
        return await self._get(key, default=default)

    def clear_cache(self):
        self._get.cache_clear()
