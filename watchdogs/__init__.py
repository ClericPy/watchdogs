import logging

from .config import Config
from .main import init_app

__version__ = '1.6.1'
__all__ = ['Config', 'init_app']
logging.getLogger('watchdogs').addHandler(logging.NullHandler())
