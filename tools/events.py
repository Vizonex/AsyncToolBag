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
        self.cache: dict[_T , Coro[_IN,RET]] = dict()

    def __call__(self, key:Optional[_T] = None):
        """Wraps an asynchornous funciton the the cache"""
        def decorator(func: Coro[_IN,RET]):
            if not asyncio.iscoroutinefunction(func):
                raise TypeError(f"Function: {func.__name__!r} must be an asynchronous function")

            # One at a time!
            if self.cache.get(key or func.__name__):
                raise AttributeError(f"Key : {key or func.__name__!r} already has an assigned function called {self.cache[key or func.__name__]!r}")
            
            self.cache[key or func.__name__] = func
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
        


class TimedCondition(asyncio.Condition):
    """A Condition that is a subclass of :class:`asyncio.Condition` but is made to act as a timeout before 
    any execution being waited upon can run"""
    
    def __init__(self, delay:Union[int,float], lock:Optional[asyncio.Lock] = None) -> None:
        super().__init__(lock=lock)

        if delay < 0:
            raise ValueError(f"default argument cannot use a number less than 0 but you chose {delay!r}")

        self._delay = delay

    @property
    def delay(self):
        """Obtains the delay you set up for use..."""
        return self._delay

    @delay.setter
    def set_new_target_delay(self,delay:Union[int,float]):
        """Used to setup new delays to the internal dealy variable
        this will take effect whenever the :class:`TimedCondition` is not sleeping"""
        if not isinstance(delay,(int,float)):
            raise ValueError(f"delay argument must be a float or integer , got {type(delay)} from {delay!r}")
        self._delay = delay
        return self 

    async def sleep(self, unlock_all:bool=True) -> None:
        """Sleeps for amount of seconds chosen for the `.delay` argument and releases all tasks inside of it... 
        Note that if notify all is called before this timer is over then it will be immediately relased 
        and this timer will not matter at all, note that this is made not to cause a `RuntimeError` and it 
        can therefore be bailed out...
        
        if `unlock_all` is True then `notify_all()` gets invoked otherwise `notify()` will be used intead
        default is True"""
        await asyncio.sleep(self._delay)
        if self.locked():
            self.notify_all() if unlock_all else self.notify()

class RateLimitCondition:
    """Used to help moderate a ratelimit.
    A Greate Example Can be a class that is used to help an http client obey RateLimits and pevent  
    Too many requests from going to the server at a time.
    
    Note that this does not take into account the concurrency until the it 
    has hit the limit and if the time hasn't cycled yet then it will be locked.
    it will then wait the timeout and then resume 
    execution as normal once the cycles have cycled"""

    async def _cycle(self):
        # Run Forever!
        while True:
            async with self._timer_cond:
                await self._timer_cond.sleep()
                # a cycle was completed so reset the task limit back to 0
                self._tl = 0
        
    async def __aenter__(self):
        """Note that this Value returns with nothing because it uses lockdown behaviors..."""
        # if it is the first time running then invoke the _cycle ...
        if not self._cycle_task:
            self._cycle_task = asyncio.create_task(self._cycle())

        if self._killed:
            raise RuntimeError(f"RateLimit {self.__name__!r} was already killed!")

        await self._timer_cond.acquire()
        if self._tl == self._task_limit:
            await self._timer_cond.wait()

        # add one to the counter 
        self._tl += 1 
        return None 
    
    async def __aexit__(self):
        # Release the coroutine the we gave to the rate_limit 
        self._timer_cond.release()


    def __init__(self, task_limit:int, delay:int, lock:Optional[asyncio.Lock] = None) -> None:
        self._tl = 0
        """The task limit is an internal varibale that keeps track of how many 
        tasks were executed in the time that it has left"""
        self._task_limit = task_limit 
        self._delay = delay 
        self._timer_cond = TimedCondition(delay,lock)
        self._cycle_task = None 
        self._killed = False 


    @property
    def task_count(self):
        """Returns back the number of tasks that have been executed within it's own iterval"""
        return self._tl
    
    def kill(self):
        """Kills the ratelimit's inner cycle, this should only be done when you're no longer going to be 
        interating with the target server for example...
        WARNING! Once the Rate-Limit is killed, if there are still running tasks that are wating for a current cycle to end 
        then they will all be freed!"""
        self._timer_cond.notify_all()
        if self._cycle_task:
            self._cycle_task.cancel()
        self._killed = True 
        

