import importlib

__all__ = [
    'get_mysql',
    'mysql_now',
    'get_clickhouse',
    'SimpleState',

    'SensorsDatabase',
    'InverterDatabase',
    'BotsDatabase'
]


def __getattr__(name: str):
    if name in __all__:
        if name.endswith('Database'):
            file = name[:-8].lower()
        elif 'mysql' in name:
            file = 'mysql'
        elif 'clickhouse' in name:
            file = 'clickhouse'
        else:
            file = 'simple_state'

        module = importlib.import_module(f'.{file}', __name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
