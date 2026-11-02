import json as _json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis import config, http  # noqa: E402


def resp(status=200, data=None, text=None, content=None):
    r = requests.Response()
    r.status_code = status
    if data is not None:
        r._content = _json.dumps(data).encode()
    elif content is not None:
        r._content = content if isinstance(content, bytes) else content.encode()
    else:
        r._content = (text or "").encode()
    r.url = "http://fake"
    return r


class FakeNet:
    """Route outgoing calls by URL substring. Records every call."""

    def __init__(self):
        self.routes = []
        self.calls = []

    def on(self, needle, handler):
        self.routes.append((needle, handler))

    def _do(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for needle, handler in self.routes:
            if needle in url:
                return handler(url, **kw) if callable(handler) else handler
        raise requests.exceptions.ConnectionError(f"no fake route for {url}")

    def get(self, url, **kw):
        return self._do("GET", url, **kw)

    def post(self, url, **kw):
        return self._do("POST", url, **kw)


@pytest.fixture
def net(monkeypatch):
    n = FakeNet()
    monkeypatch.setattr(http, "get", n.get)
    monkeypatch.setattr(http, "post", n.post)
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "GNEWS_API_KEY", "")
    return n
