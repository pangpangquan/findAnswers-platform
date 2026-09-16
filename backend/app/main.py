import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap import init_db
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings.database_url)
        await init_db(engine)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        worker = None
        if settings.enable_worker:
            from app.services.worker import start_worker_loop

            worker = asyncio.create_task(start_worker_loop(app))
        yield
        if worker is not None:
            worker.cancel()

    app = FastAPI(title="面经整理平台", lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    from app.api.ingest import router as ingest_router
    from app.api.questions import router as questions_router
    from app.api.tasks import router as tasks_router
    app.include_router(ingest_router)
    app.include_router(tasks_router)
    app.include_router(questions_router)
    return app


app = create_app()
