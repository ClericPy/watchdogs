import sqlalchemy

metadata = sqlalchemy.MetaData()
tasks = sqlalchemy.Table(
    "tasks",
    metadata,
    sqlalchemy.Column(
        'task_id', sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("name", sqlalchemy.String(64), nullable=False, unique=True),
    sqlalchemy.Column("enable", sqlalchemy.Boolean, default=True),
    sqlalchemy.Column("tags", sqlalchemy.String(128), default=""),
    sqlalchemy.Column("request_args", sqlalchemy.TEXT, nullable=False),
    sqlalchemy.Column("origin_url", sqlalchemy.String(1024), default=""),
    sqlalchemy.Column("interval", sqlalchemy.Integer, default=300),
    sqlalchemy.Column("work_hours", sqlalchemy.String(32), default=300),
    sqlalchemy.Column("max_result_count", sqlalchemy.Integer, default=10),
    sqlalchemy.Column("result_list", sqlalchemy.TEXT,
                      default=''),  # or create a foreign Table.
    sqlalchemy.Column("last_check_time", sqlalchemy.TIMESTAMP, default=None),
    sqlalchemy.Column("last_change_time", sqlalchemy.TIMESTAMP, default=None),
    sqlalchemy.Column("custom_info", sqlalchemy.TEXT, default=''),
)


def create_table(db_url):
    engine = sqlalchemy.create_engine(db_url)
    metadata.create_all(engine)
