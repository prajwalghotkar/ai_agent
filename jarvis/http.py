"""One tiny place for every outgoing HTTP call (easy to test, easy to add retries later)."""
import requests

USER_AGENT = "PrajwalJarvis/2.0 (personal AI assistant; https://github.com/)"
TIMEOUT = (6, 15)  # connect, read - Jarvis must never hang on a slow website

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def get(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    return _session.get(url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    return _session.post(url, **kwargs)
