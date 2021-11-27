import toml
import logging
import os

from os.path import join, isdir, isfile
from typing import Optional, Any, MutableMapping
from argparse import ArgumentParser


def _get_config_path(name: str) -> str:
    dirname = join(os.environ['HOME'], '.config', name)
    filename = join(os.environ['HOME'], '.config', f'{name}.toml')
    if isdir(dirname):
        return join(dirname, 'config.toml')
    elif isfile(filename):
        return filename
    else:
        raise IOError(f'configuration file not found (tried {dirname}/config.toml and {filename})')


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

        path = None
        if use_cli:
            if parser is None:
                parser = ArgumentParser()
            parser.add_argument('--config', type=str, required=name is None,
                                help='Path to the config in TOML format')
            parser.add_argument('--verbose', action='store_true')
            parser.add_argument('--log-file', type=str)
            parser.add_argument('--log-default-fmt', action='store_true')
            args = parser.parse_args()

            if args.config:
                path = args.config
            if args.verbose:
                log_verbose = True
            if args.log_file:
                log_file = args.log_file
            if args.log_default_fmt:
                log_default_fmt = args.log_default_fmt

        if name and path is None:
            path = _get_config_path(name)

        self.data = toml.load(path)

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


config = ConfigStore()


def is_development_mode() -> bool:
    if 'FLASK_ENV' in os.environ and os.environ['FLASK_ENV'] == 'development':
        return True

    return ('logging' in config) and ('verbose' in config['logging']) and (config['logging']['verbose'] is True)


def setup_logging(verbose=False, log_file=None, default_fmt=False):
    logging_level = logging.INFO
    if is_development_mode() or verbose:
        logging_level = logging.DEBUG

    log_config = {'level': logging_level}
    if not default_fmt:
        log_config['format'] = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    if log_file is not None:
        log_config['filename'] = log_file
        log_config['encoding'] = 'utf-8'
        
    logging.basicConfig(**log_config)
