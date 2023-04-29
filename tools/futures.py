from __future__ import annotations
from typing import (
    Awaitable, 
    Callable, 
    AsyncIterator, 
    Sequence, 
    Optional,
    Generator,
    Coroutine,
    Any,
    Union,
    Generic
)
from .helpers import RET, T, AnyIterable
from .iters import azip
import asyncio
import os 
from functools import partial
from abc import abstractmethod

# This library is inspired by aiomultiprocessing and the ThreadPoolExecutor...


# For the Longest time I didn't like the fact that Queues were never Generic 
# Objects, it always seemed counter intuitive to use queues and have it be annoying 
# so I Made a Solution Remedy that and still keep the docstrings intact...

class AsyncQueueType(asyncio.Queue, Generic[T]):
    """A Typehint for using Queue Objects in python this is merely used for helping with typehinting..."""

    @abstractmethod
    def put_nowait(self, item: T) -> None:
        ...

    @abstractmethod
    async def put(self, item: T):
        ...

    @abstractmethod
    async def get(self) -> T:
        ...

    @abstractmethod
    def get_nowait(self) -> T:
        ...
    
            

class AsyncPoolResult(AsyncIterator[RET], Awaitable[Sequence[RET]]):
    """Used to help tie results togther from it's given assignments.
    It is primarly used to act as a Task Manager and Gatherer
    as well as a Context Manager"""

    def __init__(self, tasks: Sequence[asyncio.Task[RET]]) -> None:
        self.tasks = asyncio.as_completed(tasks)
        """Handles the remaining workflow of all the tasks..."""
        self.gen = self.async_gen()
        self.is_running:bool = True 

    async def results(self) -> Sequence[RET]:
        ret = [t async for t in self.gen]
        # Tasks are no longer running or in limbo and shouldn't be cancelled
        self.is_running = False 
        return ret 

    def __await__(self) -> Generator[Any, None, Sequence[RET]]:
        """Allows for wait to be called on a worker..."""
        return self.results().__await__()

    async def async_gen(self):
        for t in self.tasks:
            yield await t
        self.is_running = False
    
    async def __anext__(self) -> RET:
        return await self.gen.__anext__()

    async def __aiter__(self) -> AsyncIterator[RET]:
        async for r in self.gen:
            yield r
        
    async def cancel_work(self):
        """cancels all running tasks avalible...
        this will do nothing if all the results are already finished..."""
        try:
            if self.is_running:
                for t in self.tasks:
                    t.cancel()
        finally:
            return 
        
# This is version 2 of the Pervious pool Executer which is now depricated for this one if it works better...
class ManyPoolResults(AsyncIterator[RET], Awaitable[Sequence[RET]]):
    """Used to help tie results togther from it's given assignments.
    It is primarly used to act as a Task Manager and Gatherer
    as well as being a Context Manager"""

    def __init__(self,func:Callable[...,Awaitable[RET]], concurrency:int, *iters:AnyIterable[T]) -> None:
        self.func = func 
        self.concurrency = concurrency
        self.iters = azip(iters)
        self.queue: AsyncQueueType[asyncio.Task[RET]] = asyncio.Queue()
        self.dummyqueue: AsyncQueueType[None] = asyncio.Queue(concurrency)
        """This dummy queue acts as a holder to prevent memeory overloading where
        we may have too many futures being made at a time...
        This will ensure that not too many tasks are being ran at a time...
        it carries stuff to help act as a signal to tell the queues when they're done"""
        self.main_task = None 
        self._it = self._iter()

    async def _load_results(self):
        def _on_done(fut:asyncio.Future[RET]):
            # Realease a dumy from the queue since we now have room for another 
            # object to clearly take it's place safely...
            
            self.queue.put_nowait(fut)
            self.dummyqueue.get_nowait()
            self.dummyqueue.task_done()

        async for i in self.iters:
            await self.dummyqueue.put(None)
            fut = asyncio.ensure_future(self.func(*i))
            fut.add_done_callback(_on_done)

        await self.dummyqueue.join()
        self.queue.put_nowait(None)

    async def _iter(self):
        # Run the dummy task and then start enumerating over all the objects 
        # as they start to come back to us...
        self.main_task = asyncio.ensure_future(self._load_results())

        while True:
            ret = await self.queue.get()
            if ret:
                yield await ret 
            else:
                break
            
    async def wait(self) -> Sequence[RET]:
        return [i async for i in self._it]
    
    async def __aiter__(self) -> AsyncIterator[RET]:
        async for i in self._it:
            yield i 
    
    async def __anext__(self) -> RET:
        return await self._it.__anext__()
    
    def __await__(self) -> Generator[Any, None, Sequence[RET]]:
        return self.wait().__await__()
    
    async def cancel_work(self):
        """Meant to kill work if exiting is to be done..."""
        if self.main_task and not self.main_task.done():
            self.main_task.cancel()




class AsyncPoolExecutor:
    """A little bit diffrent from :class:`ThreadPoolExecutor` and :class:`ProccessPoolExecutor` 
    it used instead used to Proccess off Coroutines and `async def` functions instead of 
    the normal `def` functions off as it also relies on asyncio itself to handle task 
    cancelations and other important things...
    
    here's an example of how to use it::

        async def example(i:int):
            await asyncio.sleep(i)
            return i
        async def executetasks():
            tasks = [1,2,3,4]
            async with AsyncPoolExecutor(3) as executor:
                async for seconds in executor.map(example , tasks):
                    print(f"slept for {seconds!r} seconds")


    Attributes
    ----------
    max_workers: Optional[:class:`int`]
        Defines the maximum number of workers to used
        This will be brought into the :class:`asyncio.Semaphmore`
        attribute `self.semaphore`\n
        By Default it will check to see if you have a 
        Cpu amount and add 4 to it , 5 will be assigned if cpu count is not obtained...
        Note this this will raise a :class:`ValueError` if the Value is not greater than 0...
    """

    def __init__(self, max_workers:Optional[int]  = None) -> None:
        if max_workers and max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")

        self._max_workers = max_workers or ((os.cpu_count() or 1) + 4)
        """The maximum number of workers that are currently being ran at a given time
        WARNING! DO NOT CHANGES THESE INTERNAL VALUES MANUALLY!"""

        self.workers = self._max_workers
        """The total number of workers that were made..."""

        self.semaphore = asyncio.Semaphore(self._max_workers)

        self.backtracker: list[AsyncPoolResult] = []
        """Used primarly as a backtracker to handle and cancel currently running tasks"""

    async def __aenter__(self):
        return self

    async def __aexit__(self,*args):
        await self.shutdown()
        return 

    def increase(self):
        """Increases the size of the internal semaphore by 1 if the semaphore is currently being locked down...
        otherwise this will be skipped all together
        this can be used to increase concurrency when a corotine is being slow or is misbehaving 
        an example might be a bad sever loading or running slower than usual....."""
        if self.semaphore.locked():
            self.semaphore.release()
            self.workers += 1


    def submit(self, fn:Callable[...,Awaitable[RET]], *args, **kw):
        """Submits a task to the inner asyncpool to be later called upon...
        this will tie in the same as all the others called by map and lmap..."""
        return asyncio.create_task(self.do_work(fn,*args,**kw))
    

    # This is now put outside as a way to be called in a larger execution function....
    async def do_work(self,fn:Callable[...,Awaitable[RET]] , *args, **kw) -> RET:
        """Does the work for the Async executor to call back later..."""
        async with self.semaphore:
            return await fn(*args,**kw)
    

    def map(self,fn:Callable[[T],Awaitable[RET]], *iterables:Sequence[T]):
        """Used to asynchronously execute all avalible iterables 
    ::

        async def example(i:int):
            await asyncio.sleep(i)
            return i
        async def executetasks():
            tasks = [1,2,3,4]
            async with AsyncPoolExecutor(3) as executor:
                async for seconds in executor.map(example , tasks):
                    print("slept for {seconds!r} seconds") 

    
    This will raise a `RuntimeError` if it gets anything besides a normal async function

    NOTE That this function will also act as a starmap function...
    """

        pr = AsyncPoolResult([self.submit(fn, *args) for args in zip(*iterables)])
        self.backtracker.append(pr)
        return pr

    async def shutdown(self):
        """Used to cancel and destory all currently running tasks and 
        is used to be primarly to act as an emergency exit..."""

        # Free up memeory as we go along first used to last used...
        while self.backtracker:
            # It's better to cleanse out the oldest worker first so that all objects in limbo 
            # can be cancelled out faster...
            await self.backtracker.pop(0).cancel_work()
    
    def lmap(self, fn:Callable[[T],Awaitable[RET]], *iterables:Union[AnyIterable[T],Sequence[T]]):
        """Used to asynchronously execute all avalible iterables 
        This allows for execution that is larger than `map`
        beacuse it useses a smater Pool Result algorythm
        for iterating objects over, both asynchronous and synchronous 
        objects and iterators will be merged together using the custom `azip` function"""
        func = partial(self.do_work,fn)
        mpr = ManyPoolResults(func,self.workers,*iterables)
        self.backtracker.append(mpr)
        return mpr



async def example(i:int):
    print(f"sleeping for {i} seconds...")
    await asyncio.sleep(i)
    return i

async def executetasks():
    tasks = [4, 1, 2, 3]
    async with AsyncPoolExecutor(3) as executor:
        async for seconds in executor.lmap(example , tasks):
            print(f"slept for {seconds!r} seconds")

if __name__ == '__main__':
    asyncio.run(executetasks())
