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
"""
from __future__ import annotations

from functools import lru_cache


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
