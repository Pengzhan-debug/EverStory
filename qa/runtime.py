"""Serve the real ASGI application on loopback for HTTP/browser/load experiments."""

from contextlib import contextmanager
from pathlib import Path
import socket
import tempfile
from threading import Thread
import time
from unittest.mock import patch

import requests
import uvicorn


@contextmanager
def local_server(log_path=None):
    # Import before creating the disposable app; never replace production source code.
    from everstory.api import main as api
    from everstory.llm.client import LLMClient
    from everstory.redis_runtime import RedisRuntime
    from everstory.storage import DatabaseStorage

    with tempfile.TemporaryDirectory(prefix="everstory-qa-") as folder:
        storage = DatabaseStorage(f"sqlite:///{(Path(folder) / 'runtime.sqlite').as_posix()}")
        app = api.create_app(storage, RedisRuntime())

        @app.middleware("http")
        async def identify_qa_server(request, call_next):
            response = await call_next(request)
            response.headers["X-EverStory-QA"] = "stub-sqlite-memory"
            return response

        # Binding before starting eliminates the ephemeral-port race.
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        # Each experiment is a separate pytest/runner process. Restore both patches on exit.
        with patch.dict("os.environ", {"LLM_MODE": "stub", "CSRF_ENFORCE": "true",
                                       "LIVE_LLM_REQUIRE_ACCOUNT": "true"}), \
             patch.object(api, "build_client", lambda: LLMClient(mode="stub")):
            thread.start()
            try:
                with requests.Session() as session:
                    session.trust_env = False
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        try:
                            response = session.get(url + "/api/health", timeout=(1, 2))
                            if response.ok and response.headers.get("X-EverStory-QA") == "stub-sqlite-memory":
                                break
                        except requests.RequestException:
                            pass
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("QA server readiness timed out")
                yield url
            finally:
                server.should_exit = True
                thread.join(timeout=15)
                listener.close()
                if thread.is_alive():
                    raise RuntimeError("QA server did not stop")
                storage.engine.dispose()
                if log_path:
                    Path(log_path).write_text("Real loopback server stopped; Stub/SQLite/memory.\n", encoding="utf-8")
