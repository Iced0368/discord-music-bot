import asyncio
from collections import deque

class AsyncDeque:
    def __init__(self, maxsize=0):
        """
        maxsize: 큐의 최대 크기 (0이면 무제한)
        """
        self._queue = deque()
        self._maxsize = maxsize
        self._put_event = asyncio.Event()
        self._get_event = asyncio.Event()

    def _wake_putters(self):
        if self._maxsize == 0 or len(self._queue) < self._maxsize:
            self._put_event.set()
        else:
            self._put_event.clear()

    def _wake_getters(self):
        if self._queue:
            self._get_event.set()
        else:
            self._get_event.clear()

    async def put(self, item):
        """
        큐에 요소를 추가합니다. 큐가 가득 차 있으면 공간이 생길 때까지 대기합니다.
        """
        while self._maxsize > 0 and len(self._queue) >= self._maxsize:
            await self._put_event.wait()
        self._queue.append(item)
        self._wake_getters()

    async def put_first(self, item):
        """
        큐의 맨 앞에 요소를 추가합니다. 큐가 가득 차 있으면 공간이 생길 때까지 대기합니다.
        """
        while self._maxsize > 0 and len(self._queue) >= self._maxsize:
            await self._put_event.wait()
        self._queue.appendleft(item)
        self._wake_getters()

    async def get(self):
        """
        큐에서 요소를 가져옵니다. 큐가 비어 있으면 요소가 추가될 때까지 대기합니다.
        """
        while not self._queue:
            await self._get_event.wait()
        item = self._queue.popleft()
        self._wake_putters()
        return item

    def qsize(self):
        """현재 큐의 크기를 반환합니다."""
        return len(self._queue)

    def empty(self):
        """큐가 비어 있는지 확인합니다."""
        return len(self._queue) == 0

    def full(self):
        """큐가 가득 찼는지 확인합니다."""
        return self._maxsize > 0 and len(self._queue) >= self._maxsize
