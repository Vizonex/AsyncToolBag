from .helpers import _T , AnyIterable
from typing import AsyncIterator, Awaitable, Sequence,Generic
import sys 
from ._tools import amap
import asyncio 
import inspect



class Iterhelper(Generic[_T]):
    """Same conecpt as aiter but is used as a helper for making all iterables asynchronous
    this is mainly for version compatability"""
    async def _itr(self) -> AsyncIterator[_T]:
        if inspect.isasyncgen(self._it):
            async for i in self._it:
                yield i 
        else:
            for i in self._it:
                yield i 

    def __init__(self,i:AnyIterable[_T]):
        self._it = i
        self._genr = self._itr()
    
    async def __anext__(self) -> _T:
        return await self._genr.__anext__()

    def __aiter__(self) -> AsyncIterator[_T]:
        return self._genr.__aiter__()


class azip(AsyncIterator[AnyIterable[Sequence[_T]]]):
    """Used to make `zip` asynchronous
    while keeping all behaviors the same..."""

    async def _itr(self):
        while True:
            try:
                yield tuple([await x.__anext__() for x in self._iters])
            except StopAsyncIteration:
                break

    def __init__(self,_iter:Sequence[AnyIterable[_T]]) -> None:
        self._iters: tuple[AsyncIterator[_T]] = tuple(map(Iterhelper, _iter))
        self._genr = self._itr()
    
    def __aiter__(self) -> AsyncIterator[Sequence[_T]]:
        return self._genr.__aiter__()

    def __anext__(self) -> Awaitable[AnyIterable[_T]]:
        return self._genr.__anext__()
    

