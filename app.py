# Copyright © 2020 Randy Barlow
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
A simple message broker.

There are three HTTP APIs, mapping to three in-memory data structures: asyncio.Queue, list, and
collections.deque. The leading component of the HTTP URLs indicates which data structure backs it.

You can post any HTTP body to these URLs to publish a message, filling in the topic of your choice:

    /queue/<topic>
    /list/<topic>
    /deque/<topic>

Clients may GET at similar URLs, but clients must add an additional queue name to the URL to denote
which queue they wish to read from:

    /queue/<topic>/<queue>
    /list/<topic>/<queue>
    /deque/<topic>/<queue>

Queues are created when the first GET request is made to a particular topic and queue name.

GET requests on the /list/ and /deque/ APIs are able to request an offset by including a GET query
parameter called offset that indexes an integer value of the requested offset.

There is a websocket listening at /ws. Connected clients can subscribe to exactly one topic by
sending a string naming the topic they wish to subscribe to, and then messages on that topic will be
sent to the client as they arrive on the server.

Finally, there is a /make_it_slow_number_one/<topic>/<queue> API that you can POST an integer to.
The posted value indicates how many random messages to generate into the given topic and queue for
all three data structures, and is useful to get messages into the queues more quickly than can be
done using the APIs directly for load testing purposes.

For all APIs, topics are created once any reader or writer references them. Queues are created once
GET requests are made referencing them. Topics and queues are never destroyed.

asyncio.Queue is the most obvious data structure to use when building a message broker. It performs
well, and obviously it's already ready for asynchronous use. However, the Queue does not support
indexing into the data, which means this implementation does not support the offset feature. Thus,
the advantages are simplicity and performance, with the disadvantage of missing the offset feature.

The list is the most obvious data structure to use when needing to access elements at arbitrary
offsets. The list starts to degrade in performance once it reaches large numbers of messages (a few
hundred thousand) since it stores data linearly in memory, causing pop and push operations to be
inefficient. The advantage of the list is that is has a natural API for the offset feature, but the
performance is a significant disadvantage, and it needs to be wrapped for asynchronous use.

The API implementation with the deque is slightly more involved than the list, but it performs
similarly to the Queue, and supports clients that request an offset. The advantage to this
data structure is that it performs well and is able to deliver the offset feature. The disadvantages
are that it brings a little extra complexity with the rotate calls and it needs to be wrapped for
asynchronous use.
"""

import asyncio
import collections
import random
import typing

from quart import Quart, Response, request, websocket


class DequeQueue(collections.deque):
    """
    A deque subclass that adds an asynchronous pop_wait() method.

    Attributes:
        event (asyncio.Event): An event that can be awaited when a request wants an item but there
            isn't one in the deque. The event will be set by publishers when items are added.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This can be awaited when a request wants an item but there isn't one in the deque. The
        # event will be set by the append() method.
        self._event = asyncio.Event()

    def append(self, *args, **kwargs):
        """Append and item to the deque."""
        super().append(*args, **kwargs)
        # We set the event so we can signal to anyone waiting on pop_wait().
        self._event.set()

    async def pop_wait(self, offset: int):
        """Pop an item off the deque at the given offset."""
        while len(self) < offset + 1:
            await self._event.wait()
            self._event.clear()

        if offset:
            self.rotate(-offset)

        result = self.popleft()

        if offset:
            self.rotate(offset)

        return result


class ListQueue(list):
    """A list subclass that adds an asynchronous pop_wait() method."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This can be awaited when a request wants an item but there isn't one in the list. The
        # event will be set by the append() method.
        self._event = asyncio.Event()

    def append(self, *args, **kwargs):
        """Append and item to the list."""
        super().append(*args, **kwargs)
        # We set the event so we can signal to anyone waiting on pop_wait().
        self._event.set()

    async def pop_wait(self, offset):
        """Pop an item off the list at the given offset."""
        while len(self) < offset + 1:
            await self._event.wait()
            self._event.clear()
        return self.pop(offset)


app = Quart(__name__)
# Maps a topic to a dictionary that maps queue names to DequeQueues.
deque_topics: typing.DefaultDict[str, typing.DefaultDict[str, DequeQueue]] = \
    collections.defaultdict(lambda: collections.defaultdict(lambda: DequeQueue()))
# Maps a topic to a dictionary that maps queue names to ListQueues.
list_topics: typing.DefaultDict[str, typing.DefaultDict[str, ListQueue]] = \
    collections.defaultdict(lambda: collections.defaultdict(lambda: ListQueue()))
# Maps a topic to a dictionary that maps queue names to asyncio.Queues.
queue_topics: typing.DefaultDict[str, typing.DefaultDict[str, asyncio.Queue]] = \
    collections.defaultdict(lambda: collections.defaultdict(asyncio.Queue))
# Maps a topic to a set of asyncio.Queues used to push messages to connected websockets.
websockets: typing.DefaultDict[str, typing.Set] = collections.defaultdict(set)


@app.route('/queue/<topic>/<queue>', methods=['GET'])
async def get_queue(topic: str, queue: str) -> Response:
    """
    Retrieve a message on the requested topic for the requested queue using asyncio.Queue.

    The Queue is created if it doesn't exist.
    """
    return Response(await queue_topics[topic][queue].get(), 200)


@app.route('/queue/<topic>', methods=['POST'])
async def post_queue(topic: str) -> Response:
    """Publish a message on the given topic to all queues and websockets using asyncio.Queues."""
    message = await request.get_data()
    [await q.put(message) for q in queue_topics[topic].values()]
    await _publish_to_websockets(message, topic)
    return Response('Success!', 200)


@app.route('/list/<topic>/<queue>', methods=['GET'])
async def get_list(topic: str, queue: str) -> Response:
    """
    Retrieve a message on the requested topic for the requested queue, using a list.

    The queue is created if it does not exist.
    """
    return await _get(list_topics, topic, queue)


@app.route('/list/<topic>', methods=['POST'])
async def post_list(topic: str) -> Response:
    """Publish a message on the given topic to all queues and websockets using lists."""
    return await _post(list_topics, topic)


@app.route('/deque/<topic>/<queue>', methods=['GET'])
async def get_deque(topic: str, queue: str) -> Response:
    """
    Retrieve a message on the requested topic for the requested queue, using a deque.

    The queue is created if it does not exist.
    """
    return await _get(deque_topics, topic, queue)


@app.route('/deque/<topic>', methods=['POST'])
async def post_deque(topic: str) -> Response:
    """Publish a message on the given topic to all queues and websockets using deques."""
    return await _post(deque_topics, topic)


@app.websocket('/ws')
async def ws():
    """Handle websocket client connections."""
    topic = await websocket.receive()

    my_queue = asyncio.Queue()
    websockets[topic].add(my_queue)

    try:
        while True:
            await(websocket.send(await my_queue.get()))
    finally:
        websockets[topic].remove(my_queue)


@app.route('/make_it_slow_number_one/<topic>/<queue>', methods=['POST'])
async def use_moar_ram(topic: str, queue: str) -> Response:
    """
    Generate random messages into each queue type.

    This API exists as a faster way to insert objects into the various data structures more
    quickly. The message body is interpreted as an int of how many messages you want to generate.
    """
    num = await request.get_data()
    try:
        num = int(num)
    except ValueError:
        return Response(f'You must POST an integer, but the body was {num}', 400)

    list_topics[topic][queue] = ListQueue([f'{random.randint(0, 1024)}' for x in range(num)])
    deque_topics[topic][queue] = DequeQueue(list_topics)
    [await queue_topics[topic][queue].put(f'{random.randint(0, 1024)}') for x in range(num)]

    return Response('It is so.', 200)


async def _get(topics: dict, topic: str, queue: str) -> Response:
    """Return the item found at the requested offset."""
    try:
        offset = _get_offset()
    except ValueError as e:
        return Response(str(e), 400)

    return Response(await topics[topic][queue].pop_wait(offset), 200)


def _get_offset() -> int:
    """Return the offset of the queue requested by the client."""
    offset = request.args.get('offset', 0)
    try:
        return int(offset)
    except ValueError:
        raise ValueError(f'offset must be an integer, but was {offset}')


async def _post(topics: dict, topic: str) -> Response:
    """Append the given message to the queues for the topic."""
    message = await request.get_data()

    for queue in topics[topic].values():
        queue.append(message)

    await _publish_to_websockets(message, topic)
    return Response('Success!', 200)


async def _publish_to_websockets(message: str, topic: str):
    """Publish the given message to each websocket queue associated with the given topic."""
    [await ws.put(message) for ws in websockets[topic]]


app.run()
