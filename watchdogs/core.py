from orjson import loads, dumps, JSONDecodeError

from uniparser.config import GlobalConfig

GlobalConfig.JSONDecodeError = JSONDecodeError
GlobalConfig.json_dumps = dumps
GlobalConfig.json_loads = loads
