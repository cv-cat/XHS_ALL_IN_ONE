from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from collections.abc import Iterator


PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)

_proxy_env_lock = threading.RLock()


@contextmanager
def direct_xhs_request_env() -> Iterator[None]:
    """Run Spider_XHS SDK calls without inheriting a broken local proxy."""
    with _proxy_env_lock:
        original = {key: os.environ.get(key) for key in PROXY_ENV_KEYS}
        for key in PROXY_ENV_KEYS:
            os.environ.pop(key, None)
        try:
            yield
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
