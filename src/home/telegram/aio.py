import functools
import asyncio

from .telegram import (
    send_message as _send_message_sync,
    send_photo as _send_photo_sync
)


async def send_message(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(_send_message_sync, *args, **kwargs))


async def send_photo(*args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(_send_photo_sync, *args, **kwargs))

