from __future__ import annotations
from typing import (
    AsyncIterator, 
    Sequence, 
    Awaitable, 
    Optional,
    Generic,
    AsyncGenerator,
    Generator,
    Union,
    Any 
)


from .helpers import (
    AnyIterable, 
    Coro, 
    _IN,
    _T
)

import inspect 
import asyncio 


class amap(AsyncIterator[_T], Awaitable[Sequence[_T]], Generic[_T]):
    """Used to map out functions but as coroutines... 
    ::

        async def do_work(b:int):
            await asyncio.sleep(b)
            return b 

        async def do_main():
            data = [1 , 2 ,3 , 4]
            async for result in amap(do_work,data):
                print(f"slept for {result} seconds...")
        
    ::
    you could also await it to end up returning all the data as a :class:`list` if need be
    since you cannot use list(map()) normally...
    ::

        async def do_main():
            data = [1 , 2 ,3 , 4]
            results = await amap(do_work, data)

    Parameters
    ----------

    - func :class:`Callable[[_IN],Awaitable[_T]]` requires an asynchronous function to execute one at a time...
    - it :class:`AnyIteratorOrSequence` used to typehint that a generator,  async generator or Sequence can be used...
    """

    def __init__(self,func:Coro[_IN , _T], it:AnyIterable[_IN]) -> None:
        if not asyncio.iscoroutinefunction(func):
            raise RuntimeError(f"function: {func!r} is not asynchronous...")
        self.func = func
        self.it = it 
        self.gen = self.run()
    
    async def __aiter__(self) -> AsyncIterator[_T]:
        async for r in self.gen:
            yield r 

    async def run(self) -> Generator[_T, None, None]:
        if inspect.isasyncgen(self.it):
            async for i in self.it:
                yield await self.func(i)
        else:
            for i in self.it:
                yield await self.func(i)
    
    async def __anext__(self) -> _T:
        return await self.gen.__anext__()

    async def wait(self) -> Sequence[_T]:
        return [r async for r in self.gen]

    def __await__(self) -> Generator[Any, None, Sequence[_T]]:
        return self.wait().__await__()



async def anext(gen:Union[AsyncGenerator[_T,None,None],AsyncIterator[_T]], defualt:Optional[_T] = None):
    """gets the next item from an asynchronous generator...
    if there is none then the default is returned..."""
    try:
        return await gen.__anext__()
    except StopAsyncIteration:
        return defualt


# async def do_work(b:int):
#     await asyncio.sleep(b)
#     return b 

# async def do_main():
#     data = [1 , 2 , 2, 1]
#     async for result in amap(do_work,data):
#         print(f"slept for {result} seconds...")

# if __name__ == "__main__":
#     asyncio.run(do_main())
