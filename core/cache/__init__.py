"""
FUOOM Core Cache Module
=======================
Namespace-enforced cache operations for all sports.
"""

from .cache_writer import (
    SportCacheWriter,
    CacheContextGuard,
    CacheNamespaceError,
    assert_sport_context,
    get_writer,
    nba_writer,
    cbb_writer,
    nfl_writer,
    tennis_writer,
    golf_writer,
    soccer_writer,
)

__all__ = [
    'SportCacheWriter',
    'CacheContextGuard', 
    'CacheNamespaceError',
    'assert_sport_context',
    'get_writer',
    'nba_writer',
    'cbb_writer',
    'nfl_writer',
    'tennis_writer',
    'golf_writer',
    'soccer_writer',
]
