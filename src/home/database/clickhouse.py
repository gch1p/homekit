from clickhouse_driver import Client as ClickhouseClient

_links = {}


def get_clickhouse(db: str) -> ClickhouseClient:
    if db not in _links:
        _links[db] = ClickhouseClient.from_url(f'clickhouse://localhost/{db}')

    return _links[db]
