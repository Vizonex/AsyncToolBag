# AsyncToolBag
Another Library for handing asynchronous code. 


# Inspiration for this library 
Inspired by the amazing aiomultiprocess library , I had decided to go out and tackle the remaining parts and things that I wanted to implement 
You will find this library to come very handy with heavier coroutines that require moderation on the concurrency. 

In my inspiration with all the different Pool Executors I have came up with the `AsyncPoolExecutor` used to acting more like the `ThreadPoolExecutor`
There are still a couple of things still left to do before I can make this into a python library but here is the gist of what I have for this concept.

```python
async def example(i:int):
    print(f"sleeping for {i} seconds...")
    await asyncio.sleep(i)
    return i

async def executetasks():
    tasks = [3, 1, 1, 2]
    async with AsyncPoolExecutor(3) as executor:
        async for seconds in executor.map(example , tasks):
            print(f"slept for {seconds!r} seconds")
```
My goal with this library is to keep things as easy as possible and non-complex.
As well as developing new ways to type-hint queue that id like to introduce called the `AsyncQueueType`What the AsyncQueueType does is that it merely acts as a typehint for displaying what a `asyncio.Queue` object is carrying. I found it rather annoying that the Queue Object doesn't show exactly what it is that it's carrying around with it so that was my solution. an example of this can be seen in a new poolresult object that I'm developing 
```python
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
```

Another Idea I had was an `amap` object that could have the ability to handel coroutine objects as well as different iterators both sync and async. 
This is a little bit like the aioitertools library but it is instead wrapped to around class object and can be both awaited and iterated over 

```python 

async def do_work(b:int):
    await asyncio.sleep(b)
    return b 

async def do_main():
    data = [1 , 2 ,3 , 4]
    async for result in amap(do_work,data):
        print(f"slept for {result} seconds...")
        
# you could also await it to end up returning all the data as a :class:`list` if need be
# since you cannot use list(amap()) normally...

async def do_main():
    data = [1 , 2 ,3 , 4]
    results = await amap(do_work, data)
    
# amaps can be chained as well sort of like a list comphrehension

async def longlistcomp():
   return await amap(do_data, amap(read_data,[1,2,3,4,5]))
```

one of my favroite objects I did recently was a helper for 3.9 python users that id like to call the `azip` function (this is also a class object)
It can also handle both async and synchronous iterables. 
```python
async def test_main():
    tests = ["ABC", (1,2,3), "XYZ"]
    async for a in azip(tests):
        print(a)

if __name__ == "__main__":
     asyncio.run(test_main())
```
