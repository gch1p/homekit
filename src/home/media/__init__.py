import importlib
import itertools

__map__ = {
    'types': ['MediaNodeType'],
    'record_client': ['SoundRecordClient', 'CameraRecordClient', 'RecordClient'],
    'node_server': ['MediaNodeServer'],
    'node_client': ['SoundNodeClient', 'CameraNodeClient', 'MediaNodeClient'],
    'storage': ['SoundRecordStorage', 'ESP32CameraRecordStorage', 'SoundRecordFile', 'CameraRecordFile', 'RecordFile'],
    'record': ['SoundRecorder', 'CameraRecorder']
}

__all__ = list(itertools.chain(*__map__.values()))

def __getattr__(name):
    if name in __all__:
        for file, names in __map__.items():
            if name in names:
                module = importlib.import_module(f'.{file}', __name__)
                return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
