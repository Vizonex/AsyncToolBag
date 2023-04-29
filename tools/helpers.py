from __future__ import annotations
from typing import (
    AsyncIterator, 
    TypeVar, 
    Awaitable, 
    Callable, 
    Iterator,
    Union,
    Sequence
)



RET = TypeVar("RET")
"""Keyword for Return variable"""
T = TypeVar("T")
_T = TypeVar("_T")
_IN = TypeVar("_IN")
"""Used to hint it an input variable to or for a function to be using..."""

AnyIterable = Union[AsyncIterator[_T], Iterator[_T], Sequence[_T]]
"""Used to describe a generator or async generator"""

Coro = Callable[[_IN], Awaitable[_T]]
"""Describes an awaitable async function"""
