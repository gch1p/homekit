import importlib

__all__ = ['RelayClient', 'RelayServer']


def __getattr__(name):
    _map = {
        'RelayClient': '.client',
        'RelayServer': '.server'
    }

    if name in __all__:
        module = importlib.import_module(_map[name], __name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
