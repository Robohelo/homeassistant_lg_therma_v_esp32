"""Compatibility helpers for pymodbus API changes across versions.

Home Assistant runs all integrations in a single shared Python
environment, so this integration can't pin its own isolated pymodbus
version - it gets whatever version HA's dependency resolver settles on
(often driven by HA core's own built-in `modbus` integration, which has
moved to newer pymodbus releases faster than this integration's manifest
was updated).

pymodbus 3.10.0 renamed the `slave=`/`slaves=` keyword arguments used on
every client read/write call to `device_id=`/`device_ids=`, and dropped
`slave=` entirely rather than keeping it as a deprecated alias - so the
two names are NOT interchangeable, and calling with the wrong one raises
`TypeError: <method>() got an unexpected keyword argument`. Older
releases (pre-3.10.0) don't have `device_id=` at all. This has to be
selected at runtime based on whatever version actually got installed.

pymodbus 3.8.0 also made `count` (and other non-address parameters)
keyword-only on read calls - passing it positionally now raises
`TypeError: takes 2 positional arguments but 3 were given`. Every call
site in this integration passes `address`/`count`/`value` as keywords
for that reason, not just the device-id parameter.

Fix pattern credited to AntoineL's writeup for the Hitachi Yutaki
integration:
https://community.home-assistant.io/t/managing-pymodbus-versions-in-custom-integrations/823773

Separately: `client.close()` was an `async def` method on older pymodbus
releases, but is a plain synchronous method (returns `None`) on current
releases (confirmed against 3.14.0). `await`-ing a `None` raises
`TypeError: object NoneType can't be used in 'await' expression` /
"'NoneType' object can't be awaited" - use `close_client()` below instead
of calling `client.close()` directly, anywhere in this integration.

Separately again: the shared `asyncio.Lock` that serializes every read
and write onto the physical Modbus connection (see __init__.py) had no
timeout on acquiring it. If a read is stuck retrying against a busy or
noisy bus - which pymodbus's own default timeout/retry settings can
stretch to several seconds per attempt - a write triggered right then
just sits there waiting for the lock with no timeout, no log line, and
no error, since it never reaches pymodbus at all to have anything to
log. From the UI it looks exactly like nothing happened. `locked_for_write()`
below puts a hard ceiling on that wait and raises a clear,
user-visible error instead of hanging silently.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, AsyncIterator

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

# How long a write will wait for a currently-in-progress read (or another
# write) to release the shared lock before giving up loudly. Generous
# enough to let one or two retried/timed-out reads finish naturally
# (pymodbus's own per-call timeout × retries can already take several
# seconds) without making a genuinely stuck write hang indefinitely.
WRITE_LOCK_TIMEOUT = 15


@lru_cache(maxsize=1)
def get_pymodbus_device_param() -> str:
    """Return 'device_id' on pymodbus >=3.10.0, else the older 'slave'.

    Cached after first call - the installed pymodbus version can't change
    during a running Home Assistant process, so there's no need to
    re-parse it on every single Modbus request.
    """
    try:
        import pymodbus
        from packaging import version

        if version.parse(pymodbus.__version__) >= version.parse("3.10.0"):
            return "device_id"
    except (ImportError, AttributeError, TypeError):
        # If we can't tell, assume an older install rather than crash -
        # `slave=` was correct for years and is still the safer default
        # for anything we failed to introspect.
        pass
    return "slave"


async def close_client(client: Any) -> None:
    """Close a pymodbus client, whether close() is sync or async.

    Older pymodbus releases had an `async def close(self)`. Current
    releases (confirmed on 3.14.0) made it a plain synchronous method
    that returns None - calling `await client.close()` unconditionally
    then raises `TypeError: object NoneType can't be used in 'await'
    expression`. Check what actually came back before deciding whether
    to await it, rather than assuming either behaviour.
    """
    result = client.close()
    if inspect.isawaitable(result):
        await result


@asynccontextmanager
async def locked_for_write(
    lock: asyncio.Lock, description: str, timeout: float = WRITE_LOCK_TIMEOUT
) -> AsyncIterator[None]:
    """Acquire the shared Modbus lock for a write, with a hard timeout.

    Logs as soon as the write is attempted (so there's always SOMETHING
    in the log the moment you flip a switch/set a number/pick an option,
    even if what follows is a timeout rather than actual Modbus traffic),
    and raises `HomeAssistantError` - which Home Assistant surfaces as a
    visible error, not a silent no-op - if the bus doesn't free up in
    time.
    """
    _LOGGER.debug("Requesting Modbus bus lock to write %s", description)
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
    except asyncio.TimeoutError as err:
        _LOGGER.error(
            "Timed out after %ss waiting for the Modbus bus to be free to "
            "write %s. The bus is likely busy with retried/failed reads - "
            "check the log for 'No response received' or transaction ID "
            "errors around this time.",
            timeout,
            description,
        )
        raise HomeAssistantError(
            f"Modbus bus busy - timed out writing {description}"
        ) from err
    try:
        _LOGGER.debug("Lock acquired, writing %s", description)
        yield
    finally:
        lock.release()
