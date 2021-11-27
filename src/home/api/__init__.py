import importlib

__all__ = ['WebAPIClient', 'RequestParams']


def __getattr__(name):
    if name in __all__:
        module = importlib.import_module(f'.web_api_client', __name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
