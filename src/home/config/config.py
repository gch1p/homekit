import toml
import yaml
import logging
import os

from os.path import join, isdir, isfile
from typing import Optional, Any, MutableMapping
from argparse import ArgumentParser


def _get_config_path(name: str) -> str:
    formats = ['toml', 'yaml']

    dirname = join(os.environ['HOME'], '.config', name)

    if isdir(dirname):
        for fmt in formats:
            filename = join(dirname, f'config.{fmt}')
            if isfile(filename):
                return filename

        raise IOError(f'config not found in {dirname}')

    else:
        filenames = [join(os.environ['HOME'], '.config', f'{name}.{format}') for format in formats]
        for file in filenames:
            if isfile(file):
                return file

    raise IOError(f'config not found')


class ConfigStore:
    data: MutableMapping[str, Any]
    app_name: Optional[str]

    def __int__(self):
        self.data = {}
        self.app_name = None

    def load(self, name: Optional[str] = None,
             use_cli=True,
             parser: ArgumentParser = None):
        self.app_name = name

        if (name is None) and (not use_cli):
            raise RuntimeError('either config name must be none or use_cli must be True')

        log_default_fmt = False
        log_file = None
        log_verbose = False
        no_config = name is False

        path = None
        if use_cli:
            if parser is None:
                parser = ArgumentParser()
            if not no_config:
                parser.add_argument('-c', '--config', type=str, required=name is None,
                                    help='Path to the config in TOML format')
            parser.add_argument('-V', '--verbose', action='store_true')
            parser.add_argument('--log-file', type=str)
            parser.add_argument('--log-default-fmt', action='store_true')
            args = parser.parse_args()

            if not no_config and args.config:
                path = args.config

            if args.verbose:
                log_verbose = True
            if args.log_file:
                log_file = args.log_file
            if args.log_default_fmt:
                log_default_fmt = args.log_default_fmt

        if not no_config and path is None:
            path = _get_config_path(name)

        if no_config:
            self.data = {}
        else:
            if path.endswith('.toml'):
                self.data = toml.load(path)
            elif path.endswith('.yaml'):
                with open(path, 'r') as fd:
                    self.data = yaml.safe_load(fd)

        if 'logging' in self:
            if not log_file and 'file' in self['logging']:
                log_file = self['logging']['file']
            if log_default_fmt and 'default_fmt' in self['logging']:
                log_default_fmt = self['logging']['default_fmt']

        setup_logging(log_verbose, log_file, log_default_fmt)

        if use_cli:
            return args

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        raise NotImplementedError('overwriting config values is prohibited')

    def __contains__(self, key):
        return key in self.data

    def items(self):
        return self.data.items()


config = ConfigStore()


def is_development_mode() -> bool:
    if 'FLASK_ENV' in os.environ and os.environ['FLASK_ENV'] == 'development':
        return True

    return ('logging' in config) and ('verbose' in config['logging']) and (config['logging']['verbose'] is True)


def setup_logging(verbose=False, log_file=None, default_fmt=False):
    logging_level = logging.INFO
    if is_development_mode() or verbose:
        logging_level = logging.DEBUG
        _add_logging_level('TRACE', logging.DEBUG-5)

    log_config = {'level': logging_level}
    if not default_fmt:
        log_config['format'] = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    if log_file is not None:
        log_config['filename'] = log_file
        log_config['encoding'] = 'utf-8'

    logging.basicConfig(**log_config)


# https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility/35804945#35804945
def _add_logging_level(levelName, levelNum, methodName=None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
        raise AttributeError('{} already defined in logging module'.format(levelName))
    if hasattr(logging, methodName):
        raise AttributeError('{} already defined in logging module'.format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
        raise AttributeError('{} already defined in logger class'.format(methodName))

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)
    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)