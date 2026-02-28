from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from app.api.routes import router
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager
import os
import signal

# Provide a definitive force-quit hook on Windows for CTRL+C
def handle_force_quit(signum, frame):
    logger.info("Received CTRL+C, forcing immediate shutdown...")
    os._exit(0)

try:
    signal.signal(signal.SIGINT, handle_force_quit)
except Exception:
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(router, prefix=settings.API_V1_STR)
# Determine the absolute path to the frontend/dist directory
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react_app(full_path: str):
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "React build not found. Please run 'npm run build' in frontend/."}
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": "Server running. React frontend not built yet."}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    ico_bytes = b'\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x006\x00\x00\x00\x16\x00\x00\x00(\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x18\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\xff\x00\x00\x00\x00\x00\x00'
    return Response(content=ico_bytes, media_type="image/x-icon")
