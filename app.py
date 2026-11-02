"""Prajwal's JARVIS - web server.

Run:   python app.py          (then open http://localhost:8000)
Host:  uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import hmac
import os
import time
from collections import defaultdict, deque

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from jarvis import __version__, config, tools
from jarvis.agent import run_agent

STATIC = config.BASE_DIR / "static"
_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _guard(request: Request) -> JSONResponse | None:
    """Optional PIN + per-IP rate limit so a public deployment can't drain your free API quota."""
    if config.APP_PIN:
        sent = request.headers.get("x-jarvis-pin", "")
        if not hmac.compare_digest(sent.encode(), config.APP_PIN.encode()):
            return JSONResponse({"error": "pin", "detail": "Access PIN required."}, status_code=401)
    now, window = time.time(), _hits[_client_ip(request)]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= config.RATE_LIMIT_PER_MIN:
        return JSONResponse({"error": "rate", "detail": "Too many requests. Slow down for a moment."}, status_code=429)
    window.append(now)
    return None


def _ctx(src: dict) -> dict:
    try:
        lat, lon = float(src.get("lat")), float(src.get("lon"))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return {"lat": lat, "lon": lon}
    except (TypeError, ValueError):
        pass
    return {}


async def index(request: Request):
    return FileResponse(STATIC / "index.html")


async def health(request: Request):
    return JSONResponse({
        "ok": True, "version": __version__, "user": config.USER_NAME, "assistant": config.ASSISTANT_NAME,
        "llm_ready": bool(config.GROQ_API_KEY), "model": config.GROQ_MODEL,
        "pin_required": bool(config.APP_PIN), "gnews": bool(config.GNEWS_API_KEY),
        "default_city": config.DEFAULT_CITY,
    })


async def chat(request: Request):
    blocked = _guard(request)
    if blocked:
        return blocked
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"detail": "Invalid JSON."}, status_code=400)
    message = str(body.get("message", "")).strip()[:1500]
    if not message:
        return JSONResponse({"detail": "Empty message."}, status_code=400)
    history = body.get("history") if isinstance(body.get("history"), list) else []
    memory = [str(m)[:200] for m in body.get("memory", [])[:30]] if isinstance(body.get("memory"), list) else []
    result = await run_in_threadpool(run_agent, message, history, memory, _ctx(body.get("location") or {}))
    return JSONResponse(result)


async def weather(request: Request):
    blocked = _guard(request)
    if blocked:
        return blocked
    q = request.query_params
    out = await run_in_threadpool(tools.run_tool, "get_weather",
                                  {"location": q.get("city", "")[:80], "days": 3}, _ctx(dict(q)))
    return JSONResponse(out, status_code=502 if "error" in out else 200)


async def news(request: Request):
    blocked = _guard(request)
    if blocked:
        return blocked
    q = request.query_params
    out = await run_in_threadpool(tools.run_tool, "get_news", {
        "topic": q.get("topic", "")[:80], "category": q.get("category", "")[:20], "count": 6})
    return JSONResponse(out, status_code=502 if "error" in out else 200)


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "microphone=(self), geolocation=(self), camera=()"
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/health", health),
        Route("/api/chat", chat, methods=["POST"]),
        Route("/api/weather", weather),
        Route("/api/news", news),
        Mount("/static", StaticFiles(directory=STATIC), name="static"),
    ],
)
app.add_middleware(SecurityHeaders)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "127.0.0.1")
    print(f"\n  {config.ASSISTANT_NAME} online for {config.USER_NAME}  ->  http://localhost:{port}\n")
    uvicorn.run("app:app", host=host, port=port, reload=False)
