import sqlalchemy
from sqlalchemy.sql import text
from uniparser import CrawlerRule, HostRule
from uniparser.crawler import RuleStorage, get_host

from .config import Config

metadata = sqlalchemy.MetaData()

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
        "tags", sqlalchemy.String(128), server_default="", nullable=False),
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
    sqlalchemy.Column(
        "result_list", sqlalchemy.TEXT, nullable=False,
        server_default='[]'),  # JSON list
    sqlalchemy.Column(
        "last_check_time",
        sqlalchemy.TIMESTAMP,
        server_default="1970-01-01 08:00:00",
        nullable=False),
    sqlalchemy.Column(
        "next_check_time",
        sqlalchemy.TIMESTAMP,
        server_default="1970-01-01 08:00:00",
        nullable=False),
    sqlalchemy.Column(
        "last_change_time",
        sqlalchemy.TIMESTAMP,
        server_default="1970-01-01 08:00:00",
        nullable=False),
    sqlalchemy.Column("custom_info", sqlalchemy.TEXT),
)
host_rules = sqlalchemy.Table(
    "host_rules",
    metadata,
    sqlalchemy.Column('host', sqlalchemy.String(128), primary_key=True),
    sqlalchemy.Column('host_rule', sqlalchemy.TEXT),
)


def create_tables(db_url):
    engine = sqlalchemy.create_engine(db_url)
    metadata.create_all(engine)


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
        host = get_host(url)
        host_rule = await self.get_host_rule(host)
        if host_rule:
            return host_rule.find(url)

    async def add_crawler_rule(self, rule: CrawlerRule, commit=None):
        url = rule.get('request_args', {}).get('url')
        if not url:
            self.logger.error(f'rule {rule["name"]} not found url.')
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

    async def pop_crawler_rule(self,
                               rule_name: str,
                               host: str = None,
                               commit=None):
        query = "SELECT host_rule FROM host_rules"
        values = {}
        if host:
            query += ' WHERE host = :host'
            values['host'] = host
        async for row in self.db.iterate(query=query):
            host_rule = HostRule.loads(row.host_rule)
            crawler_rule = host_rule.pop(rule_name, None)
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
