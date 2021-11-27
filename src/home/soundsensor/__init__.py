import importlib

__all__ = [
    'SoundSensorNode',
    'SoundSensorHitHandler',
    'SoundSensorServer',
    'SoundSensorServerGuardClient'
]


def __getattr__(name):
    if name in __all__:
        if name == 'SoundSensorNode':
            file = 'node'
        elif name == 'SoundSensorServerGuardClient':
            file = 'server_client'
        else:
            file = 'server'
        module = importlib.import_module(f'.{file}', __name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
