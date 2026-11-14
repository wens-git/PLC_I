"""Local-only FastAPI host. Modbus is owned exclusively by CommWorker."""
import asyncio
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .xj_protocol import ROOT, SPEC

from .service import (VERSION, Host, HmiService, ConnectRequest, SessionRequest, CommandRequest, ConfigRequest, NameRequest, NameWriteRequest, PointRequest, JogToken, JogStart)


def create_app(persistence_path=None, testing=False):
    service = HmiService(persistence_path)
    host = service.host
    csrf = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await asyncio.to_thread(service.close)

    app = FastAPI(title="FM_GPTPRO", version=VERSION, lifespan=lifespan)
    app.state.host = host
    allowed_hosts = ("127.0.0.1", "localhost", "::1") + (("testserver",) if testing else ())

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        hostname = urlsplit("//" + request.headers.get("host", "")).hostname
        if hostname not in allowed_hosts:
            return JSONResponse({"detail": "仅允许本机访问"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "拒绝跨站请求"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), csrf):
                return JSONResponse({"detail": "请求令牌无效"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, error):
        return JSONResponse({"detail": str(error)}, status_code=422)

    @app.exception_handler(RuntimeError)
    async def runtime_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.get("/api/meta")
    def meta():
        return {"version": VERSION, "csrf_token": csrf, "rejections": SPEC["rejections"], "commands": SPEC["commands"]}

    @app.get("/api/state")
    def state():
        return host.state()

    @app.post("/api/connect")
    def connect(body: ConnectRequest):
        return host.connect(body)

    @app.post("/api/disconnect")
    def disconnect():
        host.disconnect()
        return host.state()

    @app.post("/api/command")
    def command(body: CommandRequest):
        return service.command(body)

    @app.post("/api/config")
    def config(body: ConfigRequest):
        return service.config(body)

    @app.post("/api/name")
    def name(body: NameWriteRequest):
        return service.name(body)

    @app.delete("/api/name")
    def delete_name(body: NameRequest):
        return service.delete_name(body)

    @app.delete("/api/point/{index}")
    def delete_point(index: int, body: SessionRequest):
        return service.delete_point(index, body)

    @app.post("/api/point")
    def point(body: PointRequest):
        return service.point(body)

    @app.post("/api/jog/start")
    def jog_start(body: JogStart):
        return service.jog_start(body)

    @app.post("/api/jog/renew")
    def jog_renew(body: JogToken):
        return service.jog_renew(body)

    @app.post("/api/jog/stop")
    def jog_stop(body: JogToken):
        return service.jog_stop(body)

    @app.websocket("/ws")
    async def websocket(ws: WebSocket):
        origin = ws.headers.get("origin")
        hostname = urlsplit("//" + ws.headers.get("host", "")).hostname
        scheme = "https" if ws.url.scheme == "wss" else "http"
        if hostname not in allowed_hosts or (origin and origin != f"{scheme}://{ws.headers.get('host')}") or (not origin and not testing):
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            while True:
                await ws.send_json({"type": "snapshot", "state": host.state()})
                await asyncio.sleep(0.1)
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass
        finally:
            with host.lock:
                if host.worker:
                    host.worker.end_jog()

    dist = ROOT / "web/dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    else:
        @app.get("/")
        def missing_build():
            return JSONResponse({"error": "Frontend build missing. Run npm run build in web/."}, status_code=503)
    return app
