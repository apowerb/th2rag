import os
from logging import getLogger
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from th2rag.auth.router import router as auth_router
from th2rag.config import settings
from th2rag.conversations.router import router as conversations_router
from th2rag.dataset.router import router as datasets_router
from th2rag.knowledge.router import router as knowledge_router
from th2rag.users.router import router as users_router
from th2rag.utils.welcome_router import router as welcome_router

print(f"BYPASS_AUTH setting: {settings.bypass_auth}")

logger = getLogger(__name__)

# Resolu depuis le module, pas depuis le repertoire courant : une librairie
# publiee doit s'importer de n'importe ou. Les assets voyagent dans le wheel.
STATIQUES = Path(__file__).parent / "static"


os.getenv("SHINYPROXY_PUBLIC_PATH")
route_path = settings.root_path
route_path = None

if os.getenv("SHINYPROXY_PUBLIC_PATH"):
    route_path =  "/app_direct/th2rag_api/"

logger.info("Route Path is {route_path}")

app = FastAPI(root_path = route_path)
# Mount static files directory (optional, for other static assets)
app.mount("/static", StaticFiles(directory=STATIQUES), name="static")

# Add favicon endpoint
@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(STATIQUES / "favicon.ico")


app.include_router(auth_router)
app.include_router(welcome_router)
app.include_router(users_router)
app.include_router(conversations_router)
app.include_router(knowledge_router)
app.include_router(auth_router)
app.include_router(datasets_router)



