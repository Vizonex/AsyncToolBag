from __future__ import annotations
from .helpers import _T, Coro, _IN, RET
from typing import Generic, Optional, Union , Callable, Awaitable
from .futures import AsyncPoolExecutor
import asyncio 

# this was based on my own gist I made a while back on github I slightly modfied the variable's names here 
# to not be confused by asyncio's Event class name




class EventWrapper(Generic[_T]):
    """
    Inspired by discordpy's bot configurations, flask , aiohttp and fastapi.
    Not to be confused with :class:`asyncio.Event`. An :class:`EventWrapper` allows for 
    events to be quickly executed this is different from an :class:`EventGroupWrapper` because it can only 
    have one unique variable assigned to each of them
::

    # You can also use enums with event wrappers if you 
    # find that to be easier to write and configure...
    class BotEvent(IntEnum):
        Bot_Online = 1

    class StalkerBot:
        def __init__(self) -> None:
            # EventWrappers are very Type-Hint Friendly...
            self.user_event:EventWrapper[str] = EventWrapper()
            self.event:EventWrapper[BotEvent] = EventWrapper()

        async def run(self):
            await self.event.invoke(BotEvent.Bot_Online)
            # you'll have to use your imagination a 
            # little bit with my example...
        
        async def loop_forever(self):
            user = await internet_request(...)
            if user.isonline:
                await self.user_event.invoke("user_online", 
                    username=user.name)

    # setting up your stalker bot
    bot = StalkerBot()

    @bot.user_event("user_online")
    async def user_online(username:str):
        print(f"[+] User: {username!r} is online")

    @bot.event(BotEvent.On_Online)
    async def report_bot_up():
        print("Stalkerbot 1.0 is now online...")

    """
    def __init__(self) -> None:
        self.cache: dict[_T , Coro[...,None]] = dict()

    def __call__(self, key:Optional[_T] = None):
        """Wraps an asynchornous funciton the the cache"""
        def decorator(func: Coro[_IN,RET]):
            if not asyncio.iscoroutinefunction(func):
                raise TypeError(f"Function: {func.__name__!r} must be an asynchronous function")

            # One at a time!
            _key = key or func.__name__
            if self.cache.get(key): # type: ignore
                raise AttributeError(f"Key : {_key!r} already has an assigned function called {self.cache[_key].__name__!r}")
            
            self.cache[_key] = func # type: ignore
            return func 
        
        return decorator


    async def invoke(self,key:_T,*args,**kwargs):
        """Executes the event chosen as a callback , it will return nothing if the key isn't avalible"""
        return await self.cache[key](*args, **kwargs) if self.cache.get(key) else None 



class EventGroupWrapper(Generic[_T]):
    """allows for more than one event to be called from a simple cache of coroutine functions
    This can allow for multiple asynchonous objects to be attached to the same event
::

    event = EventWrapper()

    # Multiple things can be tied together using these...

    @event("on_login")
    async def on_login():
        print("bot is logged in")

    @event("on_login")
    async def check_mail():
        ...

    """
    def __init__(self) -> None:
        self.cache : dict[_T , set[Coro[_IN,RET]]] = dict()
    
    def __call__(self,key:Optional[_T] = None):
        """Wraps an asynchornous funciton the the cache"""
        def decorator(func: Coro[_IN,RET]):
            if not asyncio.iscoroutinefunction(func):
                raise TypeError("Function: '%s' must be an asynchronous function" % func.__name__)

            if self.cache.get(key or func.__name__):
                self.cache[key or func.__name__].add(func)

            else:
                self.cache[key or func.__name__] = {func}

            return func 
        
        return decorator


    async def invoke(self,name:_T, _concurrency:Optional[int] = None, *args,**kwargs) -> list[RET]:
        """Does execution but for many different tasks at one time 
        using the :class:`AsyncPoolExecutor`"""

        async def execute(f:Coro[_IN, RET]):
            return await f(*args, **kwargs)

        if self.cache.get(name):
            async with AsyncPoolExecutor(_concurrency) as pool:
                results = await pool.map(execute,self.cache[name])
            return results
        



class RateLimitCondition:
    """Used to help moderate ratelimiting.
    A Great Example Can be a class that is used to help an http client obey RateLimits and pevent  
    the client from getting a `Too Many Requests` (429) response.
    
    Note that this does not take into account the concurrency limit of whatever your site has set until the  
    the limit has been hit and if the time hasn't cycled over yet then it will have to wait until the next interval can be called.
    it will then wait the timeout and then resume 
    execution as normal once the cycles have cycled

    This Ratelimit-Condition can be used along-side aiohttp to keep 
    track of a target website's rate-limit
::

    # 3 requests for every 15 seconds...
    limit = RateLimitCondition(3,15)
    # later in the code...
    async with aiohttp.ClientSession("https://www.example.com") as client:
        async with limit , client.get("/") as response:
        ...
    """

    async def _cycle(self):
        while not self.is_killed:
            await asyncio.sleep(self.interval)
            # Allow the rest to leak through until another is required...
            # Set all underlying tasks back to zero before calling so that 
            # a roll-call of all pending tasks can now be called back up if 
            # we have any that are still pending by removing the limit from the amount...
            self.tasks = 0
            self._timer.set()
            # Clear afterwards and restart...
            self._timer.clear()

    def __init__(self,limit:int,interval:Union[float,int]) -> None:
        self.limit = limit 
        self.interval = interval
        # NOTE I'm using an event since it's easier to moderate vs using a condition...
        self._timer = asyncio.Event()
        self.is_killed = False
        self.pending:int = 0
        """tracks all tasks that are still inside of `__aenter__()` before `__aexit__()` can be called
        this tracker is used to wait for all tasks to end gracefully..."""

        self.tasks:int = 0
        """keeps track of all currently running tasks"""
        self._inner_cycle = asyncio.create_task(self._cycle())

    async def _add_task(self):
        """acts as a lock to moderate tasks easily, so that when one rate-limit cycle is over another 
        will be made and all pedning tasks that were blocked out are then let in..."""
        if self.is_killed:
            raise RuntimeError("RateLimit's Condition has already been killed off...")
        self.tasks += 1
        if self.tasks >= self.limit:
            await self._timer.wait()
            # all tasks needs re_adding...
            await self._add_task()

    async def __aenter__(self):
        """Used to act as a lock of it's own...
        this is equivilent to waiting for a slot to be opened via `_add_task()`..."""
        self.pending += 1
        await self._add_task()
            # Re-add all of our tasks that were being wated on since they've now been unlocked...

    async def __aexit__(self,*args):
        # gets rid of the currently pending task...
        self.pending -= 1
        return 

    def stop(self):
        """Stop rate_limit's neverending inner `self._cycle` raises a RuntimeError if there's any remaining tasks left"""
        if self.pending != 0:
            raise RuntimeError("stop() couldn't be called because there's still %i tasks left to be ran" % self.pending)
        try:
            self._inner_cycle.cancel()
        finally:
            self.is_killed = True 
            return 

    async def stop_gracefully(self):
        """Wait for all remaining tasks to be done and then exit everything out and end the rate-limit..."""
        while self.pending > 0:
            await asyncio.sleep(0.005)
        return self.stop()
    
    async def limited_function(self,func:Coro[_IN,RET]):
        """Used as a drop in replacement wrapper for wrapping coroutines with a ratelimit to better 
        control an outgoing rate-limit if needed... this can also work with def functions but 
        can yeild side effects if your're not super careful about it and the return type of the
        normal def funcion is not a future or task or coroutine afterwards...
    ::

        rate_limit = RateLimitCondition(3,60)
        @rate_limit.limited_function
        async def make_get_request(site:str):
            ...
        """

        async def decorator(*args,**kwargs):
            async with self:
                return await func(*args,**kwargs)
        return decorator
    
