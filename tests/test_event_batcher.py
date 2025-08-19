import asyncio

from agent.problems import EventBatcher


def test_event_batcher_serializes_callbacks() -> None:
    active = 0
    max_active = 0

    async def cb(events):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1

    async def run() -> None:
        batcher = EventBatcher(0.01, cb)
        batcher.add({"id": 1})
        await asyncio.sleep(0.02)
        batcher.add({"id": 2})
        await asyncio.sleep(0.2)
        await batcher.flush()

    asyncio.run(run())
    assert max_active == 1
