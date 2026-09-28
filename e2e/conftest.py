import asyncio
import json
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from stand import PORT, Stand  # noqa: E402


class Api:
    def __init__(self, stand):
        self.stand = stand

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else (b"" if method != "GET" else None)
        req = urllib.request.Request(self.stand.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw.strip().startswith(("{", "[")) else raw

    get = lambda self, p: self.call("GET", p)
    post = lambda self, p, b=None: self.call("POST", p, b if b is not None else {})
    delete = lambda self, p: self.call("DELETE", p)

    def snapshot(self):
        import websockets

        async def one():
            async with websockets.connect(self.stand.base.replace("http", "ws") + "/ws") as ws:
                return json.loads(await asyncio.wait_for(ws.recv(), 10))

        d = asyncio.run(one())
        return d.get("data", d)


@pytest.fixture(scope="session")
def api():
    with Stand() as s:
        yield Api(s)


@pytest.fixture(scope="module")
def empty_api():
    with Stand(empty=True, port=PORT + 1) as s:
        yield Api(s)
