import sqlalchemy
from sqlalchemy.sql import func, text

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
        "last_check_time",
        sqlalchemy.TIMESTAMP,
        server_default="1970-01-01 08:00:00",
        nullable=False),
    sqlalchemy.Column(
        "last_change_time",
        sqlalchemy.TIMESTAMP,
        server_default="1970-01-01 08:00:00",
        nullable=False),
    sqlalchemy.Column(
        "custom_info", sqlalchemy.TEXT, server_default="", nullable=False),
)
host_rules = sqlalchemy.Table(
    "host_rules",
    metadata,
    sqlalchemy.Column('host', sqlalchemy.String(128), primary_key=True),
    sqlalchemy.Column('host_rule', sqlalchemy.TEXT, primary_key=True),
)
task_logs = sqlalchemy.Table(
    "task_logs",
    metadata,
    sqlalchemy.Column('task_id', sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('log', sqlalchemy.TEXT, primary_key=True),
    sqlalchemy.Column(
        "create_time", sqlalchemy.TIMESTAMP, server_default=func.now()),
)


def create_tables(db_url):
    engine = sqlalchemy.create_engine(db_url)
    metadata.create_all(engine)
