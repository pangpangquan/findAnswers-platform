# P1 后端管线（截图上传 → 自动抽题 → 搜索/导出）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现设计文档中 P1 期的完整后端：批量上传面经截图，自动 OCR → DeepSeek 抽题 → 生成答案 → 入库，并提供题目 CRUD、中文全文搜索、Markdown 导出与任务重试 API。

**Architecture:** FastAPI 单服务，任务队列用 PostgreSQL 表 + `FOR UPDATE SKIP LOCKED`，Worker 以 asyncio 后台任务跑在同一进程；PaddleOCR 本地识别（懒加载，可注入 fake），LLM 统一走 OpenAI 兼容接口调 DeepSeek；全文搜索用 zhparser 生成列 + GIN 索引。所有处理结果可追溯 source_post/source_image。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.0 (async) + asyncpg、pydantic v2、PaddleOCR 2.7.3 + paddlepaddle 2.6.2 (CPU)、httpx、pytest + pytest-asyncio、Docker Compose（postgres:16 + 源码编译 zhparser）。

**Spec:** `docs/DESIGN.md`（§1.2 决策表、§4 管线、§5 数据模型、§6 API、§6.3 导出格式）。本计划从 spec 出发；执行者需同时持有两份文档。

## Global Constraints

- Python 3.11；所有注释、Prompt、答案内容用中文。
- `paddleocr==2.7.3`、`paddlepaddle==2.6.2`（CPU 版）；SQLAlchemy 2.x async；pydantic v2。
- 数据库：PostgreSQL 16，库名 `mianjing`，用户/密码 `app/app`；测试库 `mianjing_test`。
- `answer_source` 取值仅 `original | ai`；`question_type` 取值仅 `eight_legged | handwritten_code | scenario | project`。
- LLM 抽题输出必须通过 `QuestionExtractionResult` 校验，失败自动带错误重试，最多 3 次（`llm_max_retries=3`）。
- 抽题 Prompt 必须包含"只提取原文明确出现的题目，禁止编造"约束（对应 spec §11 幻觉对策）。
- 帖内去重规则：题干经 `normalize_question_text()` 归一化后相同即合并，只保留第一条。
- 任一题目 `confidence < 0.6`（`low_confidence_threshold`）→ 任务状态 `done_with_warnings`，仍全部入库。
- 任务失败 → `failed` + `error_message` + `retry_count += 1`；重试仅允许 `failed` 状态，重试前删除该源帖已有题目（幂等重跑）。
- 答案风格：AI 答案 = 口述版（3-5 分点）+ `---` 分隔线 + 长文解释（Markdown）；原帖答案原样保留。
- 导出 Markdown 格式严格按 spec §6.3 示例；`question_type` 中文标签映射：八股/手撕代码/场景设计/项目深挖。
- 后端端口 8000；上传单图 ≤ 20MB；仅接受 `image/png|jpeg|webp`。
- 测试：单元测试不得依赖 paddleocr（懒加载 + importorskip）；集成测试依赖 Docker 里的 `mianjing_test` 库。

### 与 spec 的偏差记录（计划评审时确认）

1. spec §9 写 Alembic 迁移；P1 改用启动时 `init_db()`（CREATE EXTENSION + create_all + search_vector 生成列 ALTER）。理由：单用户 MVP、schema 尚在快速演进，YAGNI；P3 引入 Alembic。
2. spec §2.1 postgres"不暴露宿主（可选 5432）"→ P1 暴露 5432，供本地 pytest 直连测试库。
3. spec §4 的视觉模型复核路由、裁剪图、`/settings` API 属 P3 范围，本计划不实现（P1 一律走 DeepSeek 文本抽题，LLM key 走 `.env`）。

---

## File Structure（P1 后端全量）

```text
.
├── .gitignore
├── README.md
├── docker-compose.yml                 # Task1: postgres；Task12: +backend
├── docker/postgres-zhparser/Dockerfile
├── data/                              # 运行时上传文件（gitignore）
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── requirements-ocr.txt
│   ├── Dockerfile
│   ├── pytest.ini
│   ├── conftest.py                    # 测试库创建/schema/截断/app fixture
│   ├── app/
│   │   ├── main.py                    # create_app() 工厂 + lifespan(worker loop)
│   │   ├── config.py                  # Settings(pydantic-settings)
│   │   ├── db.py                      # engine/session_factory/get_db
│   │   ├── bootstrap.py               # init_db: 扩展+建表+search_vector
│   │   ├── models/__init__.py         # 5 张表 ORM（一个文件，表小）
│   │   ├── schemas/extraction.py      # LLM 抽题 Schema
│   │   ├── schemas/question.py        # QuestionOut/QuestionUpdate/TaskOut API 模型
│   │   ├── utils/text.py              # normalize_question_text
│   │   ├── services/
│   │   │   ├── queue.py               # claim_next_task
│   │   │   ├── worker.py              # run_task 管线编排
│   │   │   ├── ocr.py                 # OcrResult/parse_ocr_result/PaddleOcrService/DummyOcrService
│   │   │   ├── exporters/md.py        # build_markdown
│   │   │   └── llm/
│   │   │       ├── deepseek.py        # DeepSeekClient
│   │   │       └── prompts.py         # 抽题/答案 Prompt
│   │   └── api/
│   │       ├── ingest.py              # POST /api/ingest/images
│   │       ├── tasks.py               # GET /api/tasks, GET /{id}, POST /{id}/retry
│   │       ├── questions.py           # GET / PATCH / DELETE /api/questions
│   │       ├── search.py              # GET /api/search
│   │       └── export.py              # GET /api/export
│   └── tests/
│       ├── conftest 依赖根 conftest（同目录场景见 Task2 说明）
│       ├── test_models.py
│       ├── test_extraction_schema.py
│       ├── test_text_utils.py
│       ├── test_llm_deepseek.py
│       ├── test_ocr.py
│       ├── test_queue_worker.py
│       ├── test_api_ingest.py
│       ├── test_api_tasks.py
│       ├── test_api_questions.py
│       ├── test_api_search.py
│       └── test_export.py
```

> 约定：pytest 从 `backend/` 目录运行，`conftest.py`、`pytest.ini` 放在 `backend/` 根；测试文件放 `backend/tests/`。模型集中在一个 `models/__init__.py`（5 张表都很小，拆文件反而碎）。

---

### Task 1: 仓库初始化 + Postgres(zhparser) 环境

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `docker-compose.yml`
- Create: `docker/postgres-zhparser/Dockerfile`

**Interfaces:**
- Consumes: 无
- Produces: 宿主 `localhost:5432` 可用的 Postgres 16，`zhparser` 扩展可创建；后续所有任务的 DB 前提

- [ ] **Step 1: git init 与基础文件**

```bash
cd /Users/zyj/Desktop/面经整理平台
git init
mkdir -p docker/postgres-zhparser backend
```

`.gitignore`：

```gitignore
__pycache__/
*.pyc
.venv/
.env
data/
node_modules/
dist/
.pytest_cache/
.DS_Store
```

`README.md`：

```markdown
# 面经整理平台

个人自用：从小红书/牛客/截图收集面经，自动整理成一题一答案的规范题库。

- 设计文档：`docs/DESIGN.md`
- 实施计划：`docs/superpowers/plans/`
```

- [ ] **Step 2: 写 Postgres(zhparser) 构建文件**

`docker/postgres-zhparser/Dockerfile`：

```dockerfile
FROM postgres:16
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential postgresql-server-dev-16 wget git ca-certificates \
    && wget -q http://www.xunsearch.com/scws/down/scws-1.2.3.tar.bz2 \
    && tar xf scws-1.2.3.tar.bz2 \
    && cd scws-1.2.3 && ./configure && make install && cd .. \
    && git clone --depth 1 https://github.com/amutu/zhparser.git /tmp/zhparser \
    && cd /tmp/zhparser && make && make install \
    && apt-get purge -y build-essential postgresql-server-dev-16 wget git \
    && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /scws-1.2.3* /tmp/zhparser
```

`docker-compose.yml`：

```yaml
services:
  postgres:
    build: ./docker/postgres-zhparser
    environment:
      POSTGRES_DB: mianjing
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

- [ ] **Step 3: 构建并验证 zhparser 可用**

```bash
docker compose up -d --build postgres
docker compose exec postgres psql -U app -d mianjing -c \
  "CREATE EXTENSION IF NOT EXISTS zhparser; SELECT to_tsvector('zhparser','讲讲TCP三次握手的过程');"
```

Expected: 返回一行 tsvector（含 `tcp`、`三次` 等词位），无报错。

- [ ] **Step 4: Commit**

```bash
git add .gitignore README.md docker-compose.yml docker/
git commit -m "chore: init repo with postgres+zhparser compose env"
```

---

### Task 2: FastAPI 骨架 + ORM 模型 + init_db + 测试基建

**Files:**
- Create: `backend/requirements.txt`、`backend/requirements-ocr.txt`、`backend/.env.example`、`backend/pytest.ini`、`backend/conftest.py`
- Create: `backend/app/config.py`、`backend/app/db.py`、`backend/app/bootstrap.py`、`backend/app/models/__init__.py`、`backend/app/main.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: Task 1 的 postgres 容器
- Produces:
  - `create_app(settings: Settings) -> FastAPI`（挂 `app.state.settings` / `app.state.session_factory`，带 `/health`）
  - `Settings` 字段：`database_url: str`、`upload_dir: Path`、`deepseek_api_key: str`、`deepseek_base_url: str`、`deepseek_model: str`、`llm_max_retries: int`、`low_confidence_threshold: float`
  - `init_db(engine) -> None`（幂等）
  - ORM：`SourcePost, SourceImage, Question, IngestTask, AppSetting`（`from app.models import ...`）
  - conftest fixture：`app`（含建库/建表/每测试截断）、`PNG_1PX: bytes`

- [ ] **Step 1: 写依赖与配置文件**

`backend/requirements.txt`：

```text
fastapi==0.115.6
uvicorn[standard]==0.30.6
sqlalchemy[asyncio]==2.0.36
asyncpg==0.29.0
pydantic==2.9.2
pydantic-settings==2.6.1
httpx==0.27.2
python-multipart==0.0.17
pillow==10.4.0
pytest==8.3.3
pytest-asyncio==0.24.0
```

`backend/requirements-ocr.txt`（本地开发可不装，Docker 内必装）：

```text
paddleocr==2.7.3
paddlepaddle==2.6.2
```

`backend/.env.example`：

```text
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/mianjing
UPLOAD_DIR=./data/images
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

`backend/pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
markers =
    slow: 需要真实 paddleocr 的慢速测试
```

- [ ] **Step 2: 写 config / db / models / bootstrap / main**

`backend/app/config.py`：

```python
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/mianjing"
    upload_dir: Path = Path("./data/images")
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_max_retries: int = 3
    low_confidence_threshold: float = 0.6


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/app/db.py`：

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def make_engine(url: str):
    return create_async_engine(url, pool_pre_ping=True)


def make_session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)
```

`backend/app/models/__init__.py`：

```python
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourcePost(Base):
    __tablename__ = "source_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(20))  # xhs | niuke | manual
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceImage(Base):
    __tablename__ = "source_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("source_posts.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(Text)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_lines: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("source_posts.id"), index=True)
    image_id: Mapped[int | None] = mapped_column(ForeignKey("source_images.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(30))
    answer_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_source: Mapped[str] = mapped_column(String(10), default="ai")  # original | ai
    company: Mapped[str | None] = mapped_column(String(100), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    interview_round: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    crop_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IngestTask(Base):
    __tablename__ = "ingest_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("source_posts.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(30))  # manual_images | xhs | niuke
    status: Mapped[str] = mapped_column(String(30), default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage_stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`backend/app/bootstrap.py`：

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import Base

SEARCH_VECTOR_SQL = """
ALTER TABLE questions ADD COLUMN IF NOT EXISTS search_vector tsvector
GENERATED ALWAYS AS (
  to_tsvector('zhparser',
    coalesce(content, '') || ' ' || coalesce(company, '') || ' ' ||
    coalesce(direction, '') || ' ' || coalesce(answer_markdown, ''))
) STORED
"""

GIN_SQL = "CREATE INDEX IF NOT EXISTS ix_questions_search_vector ON questions USING GIN (search_vector)"


async def init_db(engine: AsyncEngine) -> None:
    """幂等：建扩展、建表、加 search_vector 生成列与 GIN 索引。"""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS zhparser"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(SEARCH_VECTOR_SQL))
        await conn.execute(text(GIN_SQL))
```

`backend/app/main.py`：

```python
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
        from app.services.worker import start_worker_loop
        worker = asyncio.create_task(start_worker_loop(app))
        yield
        worker.cancel()

    app = FastAPI(title="面经整理平台", lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    from app.api import export, ingest, questions, search, tasks
    app.include_router(ingest.router)
    app.include_router(tasks.router)
    app.include_router(questions.router)
    app.include_router(search.router)
    app.include_router(export.router)
    return app


import asyncio  # noqa: E402  （置于 create_app 后避免循环导入展示混乱）

app = create_app()
```

> 实现注意：`import asyncio` 放到文件顶部；`start_worker_loop` 在 Task 6 才创建，Task 2 先写占位 `async def start_worker_loop(app): while True: await asyncio.sleep(3600)`（真实实现 Task 6 替换）。

- [ ] **Step 3: 写 conftest（测试基建）**

`backend/conftest.py`：

```python
import base64

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.bootstrap import init_db
from app.config import Settings
from app.db import make_session_factory
from app.main import create_app
from app.models import Base

TEST_DB_URL = "postgresql+asyncpg://app:app@localhost:5432/mianjing_test"
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _test_database():
    admin = create_async_engine(
        "postgresql+asyncpg://app:app@localhost:5432/postgres", isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as conn:
        exists = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'mianjing_test'")
        )
        if exists.scalar() is None:
            await conn.execute(text("CREATE DATABASE mianjing_test"))
    await admin.dispose()


@pytest_asyncio.fixture
async def app(tmp_path):
    settings = Settings(
        database_url=TEST_DB_URL, upload_dir=tmp_path / "images", deepseek_api_key="test-key"
    )
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with application.state.session_factory() as session:
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        yield application


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

> 前置：`cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`；postgres 容器已启动（Task 1）。

- [ ] **Step 4: 写失败测试**

`backend/tests/test_models.py`：

```python
from app.models import IngestTask, Question, SourceImage, SourcePost


async def test_create_post_image_task_question(app):
    async with app.state.session_factory() as session:
        post = SourcePost(platform="manual", title="测试帖")
        session.add(post)
        await session.flush()
        image = SourceImage(post_id=post.id, index=0, file_path="/tmp/a.png")
        session.add(image)
        await session.flush()
        task = IngestTask(post_id=post.id, task_type="manual_images")
        session.add(task)
        session.add(
            Question(
                post_id=post.id,
                image_id=image.id,
                content="讲讲 TCP 三次握手",
                question_type="eight_legged",
                answer_source="ai",
                confidence=0.9,
            )
        )
        await session.commit()

        assert post.id is not None
        assert task.status == "pending"
        assert task.retry_count == 0
```

再追加验证 search_vector 生成列存在：

```python
async def test_search_vector_column_exists(app):
    async with app.state.connect() as conn:  # placeholder——见下方修正
        pass
```

**修正**：`app.state` 上没有裸 connect，改为：

```python
async def test_search_vector_column_exists(app):
    from sqlalchemy import text

    async with app.state.engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'questions' AND column_name = 'search_vector'"
            )
        )
        assert rows.scalar() == "search_vector"
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_models.py -v
```

Expected: 2 passed（本任务模型/建表逻辑简单，直接写测试即验证；后续任务恢复"先红后绿"节奏）

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat(backend): fastapi skeleton, orm models, init_db, test infra"
```

---

### Task 3: 抽题 Schema + 题干归一化（纯函数，TDD）

**Files:**
- Create: `backend/app/schemas/extraction.py`
- Create: `backend/app/utils/text.py`
- Test: `backend/tests/test_extraction_schema.py`、`backend/tests/test_text_utils.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `ExtractedQuestion(BaseModel)`：`content: str`、`question_type: Literal["eight_legged","handwritten_code","scenario","project"]`、`answer_full: str | None = None`、`follow_ups: list[str] = []`、`company: str | None = None`、`direction: str | None = None`、`interview_round: str | None = None`、`source_image_indexes: list[int] = []`、`source_text_spans: list[str] = []`、`confidence: float = 0.0`（ge=0, le=1）；validator：`content` 去空白后长度 ≥ 4
  - `QuestionExtractionResult(BaseModel)`：`questions: list[ExtractedQuestion]`（允许空列表）
  - `normalize_question_text(s: str) -> str`：NFKC → lower → 去所有空白

- [ ] **Step 1: 写失败测试**

`backend/tests/test_extraction_schema.py`：

```python
import pytest
from pydantic import ValidationError

from app.schemas.extraction import ExtractedQuestion, QuestionExtractionResult


def make_valid(**overrides):
    data = dict(
        content="讲讲 TCP 三次握手的过程",
        question_type="eight_legged",
        source_image_indexes=[0],
        confidence=0.9,
    )
    data.update(overrides)
    return data


def test_valid_question():
    q = ExtractedQuestion(**make_valid())
    assert q.content == "讲讲 TCP 三次握手的过程"


def test_content_too_short_raises():
    with pytest.raises(ValidationError):
        ExtractedQuestion(**make_valid(content="你好"))


def test_invalid_question_type_raises():
    with pytest.raises(ValidationError):
        ExtractedQuestion(**make_valid(question_type="essay"))


def test_confidence_out_of_range_raises():
    with pytest.raises(ValidationError):
        ExtractedQuestion(**make_valid(confidence=1.5))


def test_result_allows_empty_list():
    result = QuestionExtractionResult(questions=[])
    assert result.questions == []
```

`backend/tests/test_text_utils.py`：

```python
from app.utils.text import normalize_question_text


def test_normalize_strips_space_and_case():
    assert normalize_question_text("讲讲 TCP 三次握手") == normalize_question_text("讲讲tcp三次握手")


def test_normalize_fullwidth_to_halfwidth():
    assert normalize_question_text("Ｒｅｄｉｓ 持久化？") == normalize_question_text("redis持久化?")


def test_normalize_removes_all_whitespace():
    assert normalize_question_text(" a b\tc ") == "abc"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_extraction_schema.py tests/test_text_utils.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.schemas'` / `'app.utils'`

- [ ] **Step 3: 最小实现**

`backend/app/schemas/extraction.py`：

```python
from typing import Literal

from pydantic import BaseModel, Field, field_validator

QuestionType = Literal["eight_legged", "handwritten_code", "scenario", "project"]


class ExtractedQuestion(BaseModel):
    content: str
    question_type: QuestionType
    answer_full: str | None = None
    follow_ups: list[str] = Field(default_factory=list)
    company: str | None = None
    direction: str | None = None
    interview_round: str | None = None
    source_image_indexes: list[int] = Field(default_factory=list)
    source_text_spans: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)

    @field_validator("content")
    @classmethod
    def content_not_trivial(cls, v: str) -> str:
        if len("".join(v.split())) < 4:
            raise ValueError("题目内容过短（去空白后需 ≥ 4 字符）")
        return v


class QuestionExtractionResult(BaseModel):
    questions: list[ExtractedQuestion] = Field(default_factory=list)
```

`backend/app/utils/text.py`：

```python
import unicodedata


def normalize_question_text(s: str) -> str:
    """NFKC 归一化 + 转小写 + 去全部空白，用于帖内题干去重。"""
    return "".join(unicodedata.normalize("NFKC", s).lower().split())
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_extraction_schema.py tests/test_text_utils.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas backend/app/utils backend/tests
git commit -m "feat(backend): extraction schema + question text normalization"
```

---

### Task 4: DeepSeek LLM 客户端（JSON 自检重试）+ Prompt 模块

**Files:**
- Create: `backend/app/services/llm/__init__.py`（空）、`backend/app/services/llm/prompts.py`、`backend/app/services/llm/deepseek.py`
- Test: `backend/tests/test_llm_deepseek.py`

**Interfaces:**
- Consumes: Task 3 的 `ExtractedQuestion / QuestionExtractionResult`
- Produces:
  - `class LLMError(Exception)`
  - `DeepSeekClient(api_key: str, base_url: str = "https://api.deepseek.com", model: str = "deepseek-chat", max_retries: int = 3, transport: httpx.AsyncTransport | None = None)`
  - `async DeepSeekClient.extract_questions(post_text: str, ocr_text: str) -> list[ExtractedQuestion]`（JSON 解析/Schema 校验失败自动重试，含错误反馈；耗尽抛 `LLMError`）
  - `async DeepSeekClient.generate_answer(content: str, question_type: str) -> str`（纯文本返回，非 JSON）
  - `prompts.EXTRACT_SYSTEM / EXTRACT_USER_TEMPLATE / ANSWER_SYSTEM / ANSWER_USER_TEMPLATE` 与 `prompts.QUESTION_TYPE_LABELS: dict`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_llm_deepseek.py`：

```python
import httpx
import pytest

from app.services.llm.deepseek import DeepSeekClient, LLMError

VALID_JSON = (
    '{"questions":[{"content":"讲讲TCP三次握手的过程","question_type":"eight_legged",'
    '"source_image_indexes":[0],"source_text_spans":["三次握手"],"confidence":0.9}]}'
)


def _client(handler) -> DeepSeekClient:
    return DeepSeekClient(api_key="k", transport=httpx.MockTransport(handler))


async def test_extract_success():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": VALID_JSON}}]})

    qs = await _client(handler).extract_questions("帖子", "OCR文本")
    assert qs[0].content == "讲讲TCP三次握手的过程"
    assert qs[0].question_type == "eight_legged"


async def test_extract_retries_on_bad_json_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        content = "不是JSON" if calls["n"] == 1 else VALID_JSON
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    qs = await _client(handler).extract_questions("帖子", "OCR文本")
    assert calls["n"] == 2
    assert len(qs) == 1


async def test_extract_exhausts_retries_and_raises():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "不是JSON"}}]})

    with pytest.raises(LLMError):
        await _client(handler).extract_questions("帖子", "OCR文本")


async def test_generate_answer_returns_plain_text():
    def handler(request):
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "- 要点1\n---\n详解"}}]}
        )

    answer = await _client(handler).generate_answer("讲讲三次握手", "eight_legged")
    assert "---" in answer
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_llm_deepseek.py -v`
Expected: FAIL，`No module named 'app.services'`

- [ ] **Step 3: 实现 prompts + DeepSeekClient**

`backend/app/services/llm/prompts.py`：

```python
QUESTION_TYPE_LABELS = {
    "eight_legged": "八股",
    "handwritten_code": "手撕代码",
    "scenario": "场景设计",
    "project": "项目深挖",
}

EXTRACT_SYSTEM = """你是面经整理专家。从给定的面经文本中提取所有面试题目，只输出 JSON 对象。
规则：
1. 只提取原文中明确出现的题目，禁止编造不存在的题。
2. 每道独立的题一条记录；面试官追问放进该题的 follow_ups。
3. question_type 取值：eight_legged(八股)、handwritten_code(手撕代码)、scenario(场景设计)、project(项目深挖)。
4. answer_full 为原帖中紧跟该题的答案原文；没有答案则填 null。
5. source_text_spans 必须引用 OCR 原文中真实存在的片段（用于溯源）。
6. confidence 为你对"这是一道完整独立题目"的把握，0 到 1。
输出格式：
{"questions":[{"content":"...","question_type":"...","answer_full":null,"follow_ups":[],"company":null,"direction":null,"interview_round":null,"source_image_indexes":[0],"source_text_spans":["..."],"confidence":0.9}]}"""

EXTRACT_USER_TEMPLATE = "# 帖子信息\n{post_text}\n\n# OCR 文本\n{ocr_text}\n\n请提取题目。"

ANSWER_SYSTEM = """你是资深面试教练。针对给定的面试题目，用中文写一份面试参考答案，输出 Markdown。
格式要求：
1. 先写「面试口述版」：3-5 个分点，每点一两句话，可直接背诵。
2. 然后单独一行，内容只有 --- 的分隔线。
3. 最后写「长文解释」：展开原理、对比、举例。
不要客套话，不要复述题目。"""

ANSWER_USER_TEMPLATE = "题目：{content}\n题型：{qtype}"
```

`backend/app/services/llm/deepseek.py`：

```python
import json

import httpx
from pydantic import ValidationError

from app.schemas.extraction import ExtractedQuestion, QuestionExtractionResult
from app.services.llm.prompts import (
    ANSWER_SYSTEM,
    ANSWER_USER_TEMPLATE,
    EXTRACT_SYSTEM,
    EXTRACT_USER_TEMPLATE,
    QUESTION_TYPE_LABELS,
)


class LLMError(Exception):
    pass


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        max_retries: int = 3,
        transport: httpx.AsyncTransport | None = None,
    ):
        self.model = model
        self.max_retries = max_retries
        kwargs = {
            "base_url": base_url,
            "headers": {"Authorization": f"Bearer {api_key}"},
            "timeout": httpx.Timeout(120.0),
        }
        if transport is not None:
            kwargs["transport"] = transport
        self._http = httpx.AsyncClient(**kwargs)

    async def _chat(self, system: str, user: str, json_mode: bool) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        resp = await self._http.post("/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def extract_questions(self, post_text: str, ocr_text: str) -> list[ExtractedQuestion]:
        user = EXTRACT_USER_TEMPLATE.format(post_text=post_text, ocr_text=ocr_text)
        feedback = ""
        for attempt in range(1, self.max_retries + 1):
            content = await self._chat(
                EXTRACT_SYSTEM, user + (f"\n\n上次输出错误：{feedback}，请修正后重新只输出 JSON。" if feedback else ""), json_mode=True
            )
            try:
                result = QuestionExtractionResult.model_validate(json.loads(content))
                return result.questions
            except (json.JSONDecodeError, ValidationError) as e:
                feedback = str(e)[:500]
        raise LLMError(f"抽题 JSON 解析/校验连续失败 {self.max_retries} 次：{feedback}")

    async def generate_answer(self, content: str, question_type: str) -> str:
        label = QUESTION_TYPE_LABELS.get(question_type, question_type)
        return await self._chat(
            ANSWER_SYSTEM, ANSWER_USER_TEMPLATE.format(content=content, qtype=label), json_mode=False
        )
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_llm_deepseek.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services backend/tests/test_llm_deepseek.py
git commit -m "feat(backend): deepseek client with schema-validated extraction retry"
```

---

### Task 5: OCR 服务封装（可注入 fake）

**Files:**
- Create: `backend/app/services/ocr.py`
- Test: `backend/tests/test_ocr.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `@dataclass OcrLine`：`text: str`、`confidence: float`、`box: list[list[int]]`
  - `@dataclass OcrResult`：`text: str`、`avg_confidence: float`、`lines: list[OcrLine]`
  - `parse_ocr_result(raw_pages: list) -> OcrResult`（纯函数：解析 PaddleOCR 原始输出、过滤噪声行、算平均置信度）
  - `class PaddleOcrService`：`async recognize(image_path: str) -> OcrResult`（懒加载引擎 + `asyncio.to_thread`；本地未装 paddle 时首次调用抛错，仅 Docker 内跑真实识别）
  - `class DummyOcrService`：构造时传入固定 `OcrResult`，测试用
  - 噪声关键词：`("水印", "点赞", "收藏", "关注", "小红书", "牛客网")`（命中即丢弃该行）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_ocr.py`：

```python
import pytest

from app.services.ocr import DummyOcrService, OcrResult, parse_ocr_result


def _raw_line(text_, conf):
    return [[[0, 0], [10, 0], [10, 10], [0, 10]], (text_, conf)]


def test_parse_filters_noise_and_computes_avg():
    raw = [
        [
            _raw_line("1. 讲讲 TCP 三次握手", 0.97),
            _raw_line("小红书", 0.99),          # 噪声，应被过滤
            _raw_line("2. 介绍一下 Redis 持久化", 0.93),
        ]
    ]
    result = parse_ocr_result(raw)
    assert "小红书" not in result.text
    assert result.lines[0].text == "1. 讲讲 TCP 三次握手"
    assert result.avg_confidence == pytest.approx(0.95)


def test_parse_empty_page():
    result = parse_ocr_result([[]])
    assert result.text == ""
    assert result.avg_confidence == 0.0


async def test_dummy_ocr_returns_preset():
    preset = OcrResult(text="预设文本", avg_confidence=0.95, lines=[])
    assert (await DummyOcrService(preset).recognize("/x.png")).text == "预设文本"


@pytest.mark.slow
async def test_real_paddleocr_smoke(tmp_path):
    pytest.importorskip("paddleocr")
    import base64

    from app.services.ocr import PaddleOcrService

    png = tmp_path / "t.png"
    png.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
    )
    result = await PaddleOcrService().recognize(str(png))
    assert isinstance(result, OcrResult)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_ocr.py -v -m "not slow"`
Expected: FAIL，`No module named 'app.services.ocr'`

- [ ] **Step 3: 实现**

`backend/app/services/ocr.py`：

```python
import asyncio
from dataclasses import dataclass, field

NOISE_KEYWORDS = ("水印", "点赞", "收藏", "关注", "小红书", "牛客网")


@dataclass
class OcrLine:
    text: str
    confidence: float
    box: list[list[int]] = field(default_factory=list)


@dataclass
class OcrResult:
    text: str
    avg_confidence: float
    lines: list[OcrLine] = field(default_factory=list)


def parse_ocr_result(raw_pages: list) -> OcrResult:
    """PaddleOCR 2.7 返回 [[ [box,(text,conf)], ... ]]；解析并过滤噪声行。"""
    lines: list[OcrLine] = []
    confs: list[float] = []
    page = raw_pages[0] if raw_pages and raw_pages[0] else []
    for box, (text_, conf) in page:
        if any(keyword in text_ for keyword in NOISE_KEYWORDS):
            continue
        lines.append(
            OcrLine(
                text=text_,
                confidence=float(conf),
                box=[[int(x), int(y)] for x, y in box],
            )
        )
        confs.append(float(conf))
    return OcrResult(
        text="\n".join(line.text for line in lines),
        avg_confidence=sum(confs) / len(confs) if confs else 0.0,
        lines=lines,
    )


class PaddleOcrService:
    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from paddleocr import PaddleOCR  # 本地未装则在此报错；Docker 内必装

            self._engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        return self._engine

    def _recognize_sync(self, image_path: str) -> OcrResult:
        raw = self._get_engine().ocr(image_path, cls=True)
        return parse_ocr_result(raw)

    async def recognize(self, image_path: str) -> OcrResult:
        return await asyncio.to_thread(self._recognize_sync, image_path)


class DummyOcrService:
    def __init__(self, preset: OcrResult):
        self.preset = preset

    async def recognize(self, image_path: str) -> OcrResult:
        return self.preset
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_ocr.py -v -m "not slow"`
Expected: 3 passed（slow 测试默认跳过）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ocr.py backend/tests/test_ocr.py
git commit -m "feat(backend): ocr service with noise filtering and injectable dummy"
```

---

### Task 6: 任务队列 + Worker 管线

**Files:**
- Create: `backend/app/services/queue.py`、`backend/app/services/worker.py`
- Modify: `backend/app/main.py`（替换 `start_worker_loop` 占位为真实实现）
- Test: `backend/tests/test_queue_worker.py`

**Interfaces:**
- Consumes: Task 2 模型、Task 3 `normalize_question_text`、Task 4 `LLMClient.extract_questions/generate_answer`、Task 5 `OcrService.recognize`
- Produces:
  - `async claim_next_task(session) -> IngestTask | None`（`SELECT ... FOR UPDATE SKIP LOCKED`，领取后置 `processing` 并提交）
  - `async run_task(task_id: int, *, session_factory, ocr, llm) -> None`：OCR 全部图 → 拼文本 → `llm.extract_questions` → 帖内去重 → 缺答案的调 `generate_answer` → 写 Question → 状态机（`done_with_warnings` 当任一题 `confidence < settings.low_confidence_threshold`）；异常 → `failed` + `error_message` + `retry_count += 1` + `finished_at`
  - `async start_worker_loop(app) -> None`：每 2 秒 claim 一次，用 `PaddleOcrService` + `DeepSeekClient(settings)` 执行

- [ ] **Step 1: 写失败测试**

`backend/tests/test_queue_worker.py`：

```python
from app.models import IngestTask, Question, SourceImage, SourcePost
from app.services.ocr import DummyOcrService, OcrResult
from app.services.queue import claim_next_task
from app.services.worker import run_task


def make_ocr(text_="1. 讲讲 TCP 三次握手\n2. 介绍一下 Redis 持久化机制"):
    return DummyOcrService(OcrResult(text=text_, avg_confidence=0.95, lines=[]))


class FakeLlm:
    def __init__(self, questions=None, fail=False):
        self.questions = questions or []
        self.fail = fail
        self.answered = []

    async def extract_questions(self, post_text, ocr_text):
        if self.fail:
            raise RuntimeError("LLM 挂了")
        return self.questions

    async def generate_answer(self, content, question_type):
        self.answered.append(content)
        return "- 口述要点\n---\n详细解释"


def q(content, conf=0.9, answer_full=None):
    from app.schemas.extraction import ExtractedQuestion

    return ExtractedQuestion(
        content=content,
        question_type="eight_legged",
        source_image_indexes=[0],
        source_text_spans=["x"],
        confidence=conf,
        answer_full=answer_full,
    )


async def seed(app, n_images=1):
    async with app.state.session_factory() as session:
        post = SourcePost(platform="manual", title="测试面经")
        session.add(post)
        await session.flush()
        for i in range(n_images):
            session.add(SourceImage(post_id=post.id, index=i, file_path=f"/tmp/{i}.png"))
        task = IngestTask(post_id=post.id, task_type="manual_images")
        session.add(task)
        await session.commit()
        return task.id, post.id


async def test_claim_marks_processing(app):
    task_id, _ = await seed(app)
    async with app.state.session_factory() as session:
        task = await claim_next_task(session)
        assert task.id == task_id
        assert task.status == "processing"


async def test_run_task_saves_deduped_questions(app):
    task_id, post_id = await seed(app)
    llm = FakeLlm(
        questions=[
            q("讲讲 TCP 三次握手的过程", answer_full="RDB 快照"),
            q("讲讲tcp三次握手的过程"),  # 归一化后重复，应被丢弃
            q("介绍一下 Redis 持久化机制"),
        ]
    )
    await run_task(task_id, session_factory=app.state.session_factory, ocr=make_ocr(), llm=llm)

    async with app.state.session_factory() as session:
        from sqlalchemy import select

        rows = (
            (await session.execute(select(Question).order_by(Question.id))).scalars().all()
        )
        assert len(rows) == 2  # 3 抽 2，重复题被合并
        tcp = next(r for r in rows if "三次握手" in r.content)
        redis = next(r for r in rows if "Redis" in r.content)
        assert tcp.answer_source == "original"       # 原帖答案
        assert redis.answer_source == "ai"           # LLM 生成
        assert llm.answered == ["介绍一下 Redis 持久化机制"]
        task = await session.get(IngestTask, task_id)
        assert task.status == "done"
        assert task.stage_stats == {"ocr_images": 1, "extracted": 3, "saved": 2}


async def test_run_task_low_confidence_marks_warning(app):
    task_id, _ = await seed(app)
    llm = FakeLlm(questions=[q("讲讲 操作系统 进程与线程的区别", conf=0.4)])
    await run_task(task_id, session_factory=app.state.session_factory, ocr=make_ocr(), llm=llm)
    async with app.state.session_factory() as session:
        task = await session.get(IngestTask, task_id)
        assert task.status == "done_with_warnings"


async def test_run_task_failure_marks_failed(app):
    task_id, _ = await seed(app)
    llm = FakeLlm(fail=True)
    await run_task(task_id, session_factory=app.state.session_factory, ocr=make_ocr(), llm=llm)
    async with app.state.session_factory() as session:
        task = await session.get(IngestTask, task_id)
        assert task.status == "failed"
        assert "LLM 挂了" in task.error_message
        assert task.retry_count == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_queue_worker.py -v`
Expected: FAIL，`No module named 'app.services.queue'`

- [ ] **Step 3: 实现 queue + worker + 真实 worker loop**

`backend/app/services/queue.py`：

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IngestTask


async def claim_next_task(session: AsyncSession) -> IngestTask | None:
    result = await session.execute(
        select(IngestTask)
        .where(IngestTask.status == "pending")
        .order_by(IngestTask.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    task = result.scalar_one_or_none()
    if task is not None:
        task.status = "processing"
        await session.commit()
    return task
```

`backend/app/services/worker.py`：

```python
import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.models import IngestTask, Question, SourceImage, SourcePost
from app.utils.text import normalize_question_text

logger = logging.getLogger(__name__)


async def run_task(task_id: int, *, session_factory, ocr, llm, low_confidence_threshold: float = 0.6) -> None:
    async with session_factory() as session:
        task = await session.get(IngestTask, task_id)
        if task is None or task.status != "processing":
            return
        post = await session.get(SourcePost, task.post_id)
        images = (
            await session.execute(
                select(SourceImage).where(SourceImage.post_id == post.id).order_by(SourceImage.index)
            )
        ).scalars().all()
        try:
            ocr_texts: list[str] = []
            for image in images:
                result = await ocr.recognize(image.file_path)
                image.ocr_text = result.text
                image.ocr_confidence = result.avg_confidence
                ocr_texts.append(result.text)

            post_text = "\n".join(filter(None, [post.title, post.raw_text]))
            questions = await llm.extract_questions(post_text, "\n\n".join(ocr_texts))

            seen: set[str] = set()
            min_confidence = 1.0
            for item in questions:
                key = normalize_question_text(item.content)
                if key in seen:
                    continue
                seen.add(key)
                if item.answer_full:
                    answer, source = item.answer_full, "original"
                else:
                    answer, source = await llm.generate_answer(item.content, item.question_type), "ai"
                main_image = (
                    images[item.source_image_indexes[0]]
                    if item.source_image_indexes and item.source_image_indexes[0] < len(images)
                    else None
                )
                session.add(
                    Question(
                        post_id=post.id,
                        image_id=main_image.id if main_image else None,
                        content=item.content.strip(),
                        question_type=item.question_type,
                        answer_markdown=answer,
                        answer_source=source,
                        company=item.company,
                        direction=item.direction,
                        interview_round=item.interview_round,
                        source_url=post.url,
                        confidence=item.confidence,
                    )
                )
                min_confidence = min(min_confidence, item.confidence)

            task.status = (
                "done_with_warnings" if min_confidence < low_confidence_threshold else "done"
            )
            task.stage_stats = {"ocr_images": len(images), "extracted": len(questions), "saved": len(seen)}
        except Exception as e:  # noqa: BLE001 —— 单任务失败不能拖垮 worker
            task.status = "failed"
            task.error_message = f"{type(e).__name__}: {e}"
            task.retry_count += 1
            logger.exception("任务 %s 处理失败", task_id)
        finally:
            task.finished_at = datetime.now(UTC)
            await session.commit()


async def start_worker_loop(app) -> None:
    """FastAPI lifespan 启动的常驻循环：每 2 秒领取一个任务。"""
    from app.config import get_settings
    from app.services.llm.deepseek import DeepSeekClient
    from app.services.ocr import PaddleOcrService

    settings = app.state.settings or get_settings()
    ocr = PaddleOcrService()
    llm = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        max_retries=settings.llm_max_retries,
    )
    while True:
        async with app.state.session_factory() as session:
            task = await claim_next_task(session)
        if task is None:
            await asyncio.sleep(2)
            continue
        await run_task(
            task.id,
            session_factory=app.state.session_factory,
            ocr=ocr,
            llm=llm,
            low_confidence_threshold=settings.low_confidence_threshold,
        )
```

> `main.py` 修改：删除占位 `start_worker_loop`，改为 `from app.services.worker import start_worker_loop`（import 移到 lifespan 内或顶部均可，注意避免循环导入——`worker` 内部延迟导入 `DeepSeekClient/PaddleOcrService` 已规避）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_queue_worker.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/queue.py backend/app/services/worker.py backend/app/main.py backend/tests/test_queue_worker.py
git commit -m "feat(backend): pg-skip-locked task queue and extraction worker pipeline"
```

---

### Task 7: 上传 API（POST /api/ingest/images）

**Files:**
- Create: `backend/app/api/__init__.py`（空）、`backend/app/api/ingest.py`
- Modify: `backend/app/main.py`（include_router，替换 Task 2 里的占位 include 为真实路由——Task 2 的 main 已 include，本任务只需保证导入不报错；若 Task 2 用了 try/except 占位，此处删除）
- Test: `backend/tests/test_api_ingest.py`

**Interfaces:**
- Consumes: Task 2 模型与 `app.state.settings.upload_dir`
- Produces: `POST /api/ingest/images`，multipart 字段名 `files`（可多个），成功 `201 {"post_id": int, "task_id": int}`；校验失败 `400`（无文件/非图片/超 20MB）；创建 `platform="manual"` 的 `SourcePost`（`title="手动上传 YYYY-MM-DD HH:MM"`）、每图一条 `SourceImage`、一条 `IngestTask(task_type="manual_images", status="pending")`；文件落盘 `{upload_dir}/{post_id}/{index}{ext}`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_api_ingest.py`：

```python
from conftest import PNG_1PX

from app.models import IngestTask, SourceImage, SourcePost


async def test_upload_creates_post_images_task_and_files(app, client, tmp_path):
    resp = await client.post(
        "/api/ingest/images",
        files=[
            ("files", ("a.png", PNG_1PX, "image/png")),
            ("files", ("b.png", PNG_1PX, "image/png")),
        ],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["post_id"] > 0 and body["task_id"] > 0

    async with app.state.session_factory() as session:
        post = await session.get(SourcePost, body["post_id"])
        assert post.platform == "manual"
        images = (
            await session.execute(
                SourceImage.__table__.select().where(SourceImage.post_id == post.id)
            )
        ).fetchall()
        assert len(images) == 2
        task = await session.get(IngestTask, body["task_id"])
        assert task.status == "pending"
    assert (tmp_path / "images" / str(post.id) / "0.png").exists()


async def test_upload_rejects_non_image(app, client):
    resp = await client.post(
        "/api/ingest/images",
        files=[("files", ("evil.txt", b"hello", "text/plain"))],
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_api_ingest.py -v`
Expected: FAIL（404 Not Found，路由不存在）

- [ ] **Step 3: 实现**

`backend/app/api/ingest.py`：

```python
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import IngestTask, SourceImage, SourcePost

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_SIZE = 20 * 1024 * 1024


@router.post("/images", status_code=201)
async def upload_images(
    request: Request,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise HTTPException(400, "没有收到任何文件")

    validated: list[tuple[str, bytes]] = []
    for f in files:
        if f.content_type not in ALLOWED_TYPES:
            raise HTTPException(400, f"{f.filename} 不是支持的图片类型 (png/jpeg/webp)")
        data = await f.read()
        if len(data) > MAX_SIZE:
            raise HTTPException(400, f"{f.filename} 超过 20MB 限制")
        validated.append((f.filename or "unnamed.png", data))

    post = SourcePost(platform="manual", title=f"手动上传 {datetime.now():%Y-%m-%d %H:%M}")
    db.add(post)
    await db.flush()

    upload_dir: Path = request.app.state.settings.upload_dir / str(post.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    for i, (filename, data) in enumerate(validated):
        suffix = Path(filename).suffix.lower() or ".png"
        path = upload_dir / f"{i}{suffix}"
        path.write_bytes(data)
        db.add(SourceImage(post_id=post.id, index=i, file_path=str(path)))

    task = IngestTask(post_id=post.id, task_type="manual_images")
    db.add(task)
    await db.commit()
    return {"post_id": post.id, "task_id": task.id}
```

> `main.py` 确认：Task 2 中 `from app.api import export, ingest, questions, search, tasks` 一行在本任务后才能全部导入成功——若 Task 2 曾用 try/except 占位缺失模块，现在逐个删除占位（本任务至少保证 `ingest` 真实存在；`tasks/questions/search/export` 的 include 改为后续任务逐个放开，或统一在 Task 2 用注释占位、各任务创建后放开）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_api_ingest.py tests/test_models.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/api backend/app/main.py backend/tests/test_api_ingest.py
git commit -m "feat(backend): batch screenshot upload endpoint"
```

---

### Task 8: 任务 API（列表 / 详情 / 重试）

**Files:**
- Create: `backend/app/api/tasks.py`
- Modify: `backend/app/schemas/question.py`（新建，含 `TaskOut`）
- Test: `backend/tests/test_api_tasks.py`

**Interfaces:**
- Consumes: Task 2 `IngestTask`
- Produces:
  - `TaskOut(BaseModel)`：`id: int`、`post_id: int`、`task_type: str`、`status: str`、`retry_count: int`、`error_message: str | None`、`stage_stats: dict | None`、`created_at: datetime`、`finished_at: datetime | None`
  - `GET /api/tasks?status=&page=1&page_size=20` → `{"items": [TaskOut], "total": int}`（status 可选过滤，按 id 倒序）
  - `GET /api/tasks/{id}` → `TaskOut`（404 不存在）
  - `POST /api/tasks/{id}/retry` → `TaskOut`；仅 `failed` 可重试：置 `pending`、清 `error_message`、删除该源帖全部 `Question`（幂等重跑）；非 failed → `409`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_api_tasks.py`：

```python
from app.models import IngestTask, Question, SourcePost


async def seed_task(app, status="failed", with_question=False):
    async with app.state.session_factory() as session:
        post = SourcePost(platform="manual", title="t")
        session.add(post)
        await session.flush()
        task = IngestTask(
            post_id=post.id,
            task_type="manual_images",
            status=status,
            retry_count=1 if status == "failed" else 0,
            error_message="boom" if status == "failed" else None,
        )
        session.add(task)
        if with_question:
            session.add(
                Question(
                    post_id=post.id,
                    content="旧题目数据",
                    question_type="eight_legged",
                    answer_source="ai",
                    confidence=0.5,
                )
            )
        await session.commit()
        return task.id


async def test_list_and_filter(app, client):
    await seed_task(app, status="failed")
    await seed_task(app, status="done")
    resp = await client.get("/api/tasks", params={"status": "failed"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "failed"


async def test_retry_failed_task_resets_and_clears_questions(app, client):
    task_id = await seed_task(app, status="failed", with_question=True)
    resp = await client.post(f"/api/tasks/{task_id}/retry")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    assert resp.json()["error_message"] is None

    async with app.state.session_factory() as session:
        from sqlalchemy import select

        remaining = (await session.execute(select(Question))).scalars().all()
        assert remaining == []


async def test_retry_non_failed_returns_409(app, client):
    task_id = await seed_task(app, status="done")
    resp = await client.post(f"/api/tasks/{task_id}/retry")
    assert resp.status_code == 409
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_api_tasks.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现**

`backend/app/schemas/question.py`：

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    task_type: str
    status: str
    retry_count: int
    error_message: str | None
    stage_stats: dict | None
    created_at: datetime
    finished_at: datetime | None
```

`backend/app/api/tasks.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import IngestTask, Question
from app.schemas.question import TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    status: str | None = None, page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)
):
    conditions = []
    if status:
        conditions.append(IngestTask.status == status)
    base = select(IngestTask).where(*conditions)
    total = await db.scalar(select(func.count()).select_from(IngestTask).where(*conditions))
    rows = (
        await db.execute(
            base.order_by(IngestTask.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return {"items": [TaskOut.model_validate(r) for r in rows], "total": total}


@router.get("/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(IngestTask, task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    return TaskOut.model_validate(task)


@router.post("/{task_id}/retry")
async def retry_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(IngestTask, task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    if task.status != "failed":
        raise HTTPException(409, "只有失败的任务可以重试")
    await db.execute(delete(Question).where(Question.post_id == task.post_id))
    task.status = "pending"
    task.error_message = None
    await db.commit()
    return TaskOut.model_validate(task)
```

> `main.py`：确保 `app.include_router(tasks.router)` 生效（Task 2 已统一 include，则无需改动；若被注释占位则放开）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_api_tasks.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/tasks.py backend/app/schemas/question.py backend/tests/test_api_tasks.py
git commit -m "feat(backend): task list/detail/retry endpoints"
```

---

### Task 9: 题目 API（列表过滤 / 详情 / 编辑 / 软删除）

**Files:**
- Modify: `backend/app/schemas/question.py`（追加 `QuestionOut`、`QuestionUpdate`）
- Create: `backend/app/api/questions.py`
- Test: `backend/tests/test_api_questions.py`

**Interfaces:**
- Consumes: Task 2 `Question` 模型
- Produces:
  - `QuestionOut(BaseModel, from_attributes)`：`id, post_id, image_id, content, question_type, answer_markdown, answer_source, company, direction, interview_round, source_url, crop_image_path, confidence, created_at, updated_at`
  - `QuestionUpdate(BaseModel)`：全字段可选——`content, question_type, answer_markdown, company, direction, interview_round`
  - `GET /api/questions?company=&direction=&question_type=&answer_source=&q=&min_confidence=&page=1&page_size=20` → `{"items":[QuestionOut],"total":int}`；`q` 对 `content` 做 `ilike %q%`；排除 `deleted_at` 非空；按 `id` 倒序
  - `GET /api/questions/{id}` → `QuestionOut`（含已删除 → 404）
  - `PATCH /api/questions/{id}`（body 为 `QuestionUpdate`）→ `QuestionOut`，只更新显式传入字段（事后修订界面依赖）
  - `DELETE /api/questions/{id}` → `204`，软删除（置 `deleted_at`）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_api_questions.py`：

```python
from app.models import Question, SourcePost


async def seed_question(app, **overrides):
    defaults = dict(
        content="讲讲 MySQL 的 MVCC 实现原理",
        question_type="eight_legged",
        answer_markdown="undo log + ReadView",
        answer_source="original",
        company="字节跳动",
        direction="后端",
        interview_round="一面",
        confidence=0.92,
    )
    defaults.update(overrides)
    async with app.state.session_factory() as session:
        post = SourcePost(platform="manual", title="t")
        session.add(post)
        await session.flush()
        session.add(Question(post_id=post.id, **defaults))
        await session.commit()


async def test_list_with_filters(app, client):
    await seed_question(app)
    await seed_question(app, content="手写 LRU 缓存", question_type="handwritten_code", company="阿里巴巴")

    resp = await client.get("/api/questions", params={"question_type": "handwritten_code"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["content"] == "手写 LRU 缓存"

    resp = await client.get("/api/questions", params={"q": "MVCC"})
    assert resp.json()["total"] == 1


async def test_patch_updates_fields(app, client):
    await seed_question(app)
    qid = (await client.get("/api/questions")).json()["items"][0]["id"]
    resp = await client.patch(
        f"/api/questions/{qid}",
        json={"answer_markdown": "修正后的答案", "confidence": None},
    )
    # confidence 不在 QuestionUpdate 里，传了也会被忽略（pydantic extra=ignore 默认行为）
    assert resp.status_code == 200
    assert resp.json()["answer_markdown"] == "修正后的答案"
    assert resp.json()["confidence"] == 0.92


async def test_delete_is_soft(app, client):
    await seed_question(app)
    qid = (await client.get("/api/questions")).json()["items"][0]["id"]
    assert (await client.delete(f"/api/questions/{qid}")).status_code == 204
    assert (await client.get(f"/api/questions/{qid}")).status_code == 404
    assert (await client.get("/api/questions")).json()["total"] == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_api_questions.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现**

`backend/app/schemas/question.py` 追加：

```python
from typing import Literal


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    image_id: int | None
    content: str
    question_type: str
    answer_markdown: str | None
    answer_source: str
    company: str | None
    direction: str | None
    interview_round: str | None
    source_url: str | None
    crop_image_path: str | None
    confidence: float
    created_at: datetime
    updated_at: datetime


class QuestionUpdate(BaseModel):
    content: str | None = None
    question_type: Literal["eight_legged", "handwritten_code", "scenario", "project"] | None = None
    answer_markdown: str | None = None
    company: str | None = None
    direction: str | None = None
    interview_round: str | None = None
```

`backend/app/api/questions.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Question
from app.schemas.question import QuestionOut, QuestionUpdate

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _alive(stmt):
    return stmt.where(Question.deleted_at.is_(None))


@router.get("")
async def list_questions(
    company: str | None = None,
    direction: str | None = None,
    question_type: str | None = None,
    answer_source: str | None = None,
    q: str | None = None,
    min_confidence: float | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    conditions = [Question.deleted_at.is_(None)]
    if company:
        conditions.append(Question.company == company)
    if direction:
        conditions.append(Question.direction == direction)
    if question_type:
        conditions.append(Question.question_type == question_type)
    if answer_source:
        conditions.append(Question.answer_source == answer_source)
    if q:
        conditions.append(Question.content.ilike(f"%{q}%"))
    if min_confidence is not None:
        conditions.append(Question.confidence >= min_confidence)

    total = await db.scalar(select(func.count()).select_from(Question).where(*conditions))
    rows = (
        await db.execute(
            select(Question)
            .where(*conditions)
            .order_by(Question.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {"items": [QuestionOut.model_validate(r) for r in rows], "total": total}


@router.get("/{question_id}")
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)):
    question = await db.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise HTTPException(404, "题目不存在")
    return QuestionOut.model_validate(question)


@router.patch("/{question_id}")
async def update_question(
    question_id: int, payload: QuestionUpdate, db: AsyncSession = Depends(get_db)
):
    question = await db.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise HTTPException(404, "题目不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    await db.commit()
    await db.refresh(question)
    return QuestionOut.model_validate(question)


@router.delete("/{question_id}", status_code=204)
async def delete_question(question_id: int, db: AsyncSession = Depends(get_db)):
    question = await db.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise HTTPException(404, "题目不存在")
    from datetime import UTC, datetime

    question.deleted_at = datetime.now(UTC)
    await db.commit()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_api_questions.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/questions.py backend/app/schemas/question.py backend/tests/test_api_questions.py
git commit -m "feat(backend): question list/detail/edit/soft-delete endpoints"
```

---

### Task 10: 全文搜索 API（zhparser）

**Files:**
- Create: `backend/app/api/search.py`
- Test: `backend/tests/test_api_search.py`

**Interfaces:**
- Consumes: Task 2 的 `search_vector` 生成列 + GIN 索引
- Produces: `GET /api/search?q=&company=&direction=&question_type=` → `{"items":[QuestionOut 字段 + "rank": float + "headline": str（含 <em> 高亮）]}`，按 `ts_rank` 倒序，上限 50；`q` 为空返回 400

- [ ] **Step 1: 写失败测试**

`backend/tests/test_api_search.py`：

```python
from tests.test_api_questions import seed_question


async def test_search_finds_and_highlights(app, client):
    await seed_question(app)  # 讲讲 MySQL 的 MVCC 实现原理
    await seed_question(app, content="介绍一下 HTTPS 握手过程", company="腾讯")

    resp = await client.get("/api/search", params={"q": "MVCC"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["content"].startswith("讲讲 MySQL")
    assert "<em>" in items[0]["headline"]
    assert items[0]["rank"] > 0


async def test_search_no_result(app, client):
    await seed_question(app)
    resp = await client.get("/api/search", params={"q": "Kubernetes调度器"})
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_search_empty_query_rejected(app, client):
    assert (await client.get("/api/search", params={"q": ""})).status_code == 400
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_api_search.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现**

`backend/app/api/search.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.question import QuestionOut

router = APIRouter(prefix="/api/search", tags=["search"])

SEARCH_SQL = text(
    """
    SELECT q.id, q.rank, ts_headline(
               'zhparser', q.content, query,
               'StartSel=<em>, StopSel=</em>, MaxWords=36, MinWords=10'
           ) AS headline
    FROM questions q, websearch_to_tsquery('zhparser', :q) query
    WHERE q.search_vector @@ query AND q.deleted_at IS NULL
    ORDER BY q.rank DESC
    LIMIT 50
    """
)


@router.get("")
async def search(
    q: str,
    company: str | None = None,
    direction: str | None = None,
    question_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(400, "搜索词不能为空")
    rows = (await db.execute(SEARCH_SQL, {"q": q})).mappings().all()
    items = []
    for row in rows:
        question = await db.get(QuestionOut.model_config and __import__("app.models", fromlist=["Question"]).Question, row["id"])  # 占位——实现时替换
        items.append({**_question_out_dict(db, row["id"]), "rank": float(row["rank"]), "headline": row["headline"]})
    return {"items": items}
```

> **实现注意（不要照抄上面占位行）**：正确写法是先按 id 批量取 Question 再组装。最终实现：

```python
@router.get("")
async def search(
    q: str,
    db: AsyncSession = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(400, "搜索词不能为空")
    hits = (await db.execute(SEARCH_SQL, {"q": q})).mappings().all()
    items = []
    for hit in hits:
        question = await db.get(Question, hit["id"])
        if question is None:
            continue
        item = QuestionOut.model_validate(question).model_dump(mode="json")
        item["rank"] = float(hit["rank"])
        item["headline"] = hit["headline"]
        items.append(item)
    return {"items": items}
```

（`SEARCH_SQL` 中 `q.rank` 的别名问题：PostgreSQL 里 `ts_rank(search_vector, query) AS rank` 在 `ORDER BY q.rank` 处需写 `ORDER BY rank DESC`（输出列名），实现时以通过测试为准，SQL 为：

```sql
SELECT q.id,
       ts_rank(q.search_vector, query) AS rank,
       ts_headline('zhparser', q.content, query,
                   'StartSel=<em>, StopSel=</em>, MaxWords=36, MinWords=10') AS headline
FROM questions q, websearch_to_tsquery('zhparser', :q) query
WHERE q.search_vector @@ query AND q.deleted_at IS NULL
ORDER BY rank DESC
LIMIT 50
```

并在文件顶部导入 `from app.models import Question`。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_api_search.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/search.py backend/tests/test_api_search.py
git commit -m "feat(backend): zhparser full-text search endpoint with headline highlight"
```

---

### Task 11: Markdown 导出

**Files:**
- Create: `backend/app/services/exporters/__init__.py`（空）、`backend/app/services/exporters/md.py`
- Create: `backend/app/api/export.py`
- Test: `backend/tests/test_export.py`

**Interfaces:**
- Consumes: Task 9 `QuestionOut`、Task 3 无关；`prompts.QUESTION_TYPE_LABELS`
- Produces:
  - `build_markdown(questions: list[QuestionOut-like]) -> str`：格式严格按 spec §6.3；`answer_source=ai` 且答案含 `\n---\n` 时拆为「### 答案（口述版）」+「### 长文解释」，否则「### 答案」；缺答案写「（待补充）」；无来源链接写「无链接」
  - `GET /api/export?format=md` → `text/markdown` 附件下载（文件名 `mianjing-export.md`），导出**全部未删除题目**（按 id 正序）；`format` 非 `md` → 400

- [ ] **Step 1: 写失败测试**

`backend/tests/test_export.py`：

```python
from types import SimpleNamespace

from app.services.exporters.md import build_markdown


def ns(**kw):
    base = dict(
        content="讲讲 MySQL 的 MVCC 实现原理",
        question_type="eight_legged",
        answer_markdown="undo log + ReadView",
        answer_source="original",
        company="字节跳动",
        direction="后端",
        interview_round="一面",
        source_url="https://example.com/p/1",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_original_answer_format():
    md = build_markdown([ns()])
    expected = (
        "# 面经题库导出\n\n"
        "## [八股] 讲讲 MySQL 的 MVCC 实现原理\n\n"
        "- 公司：字节跳动 ｜ 方向：后端 ｜ 轮次：一面\n"
        "- 来源：[原帖](https://example.com/p/1) ｜ 答案来源：来自原帖\n\n"
        "### 答案\nundo log + ReadView\n"
    )
    assert md == expected


def test_ai_answer_split_oral_and_detail():
    q = ns(
        answer_source="ai",
        answer_markdown="- 要点1\n- 要点2\n---\nMVCC 详解正文",
        source_url=None,
    )
    md = build_markdown([q])
    assert "### 答案（口述版）\n- 要点1\n- 要点2\n" in md
    assert "### 长文解释\nMVCC 详解正文" in md
    assert "无链接" in md


async def test_export_endpoint(app, client):
    from tests.test_api_questions import seed_question

    await seed_question(app)
    resp = await client.get("/api/export", params={"format": "md"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "MVCC" in resp.text
    assert (await client.get("/api/export", params={"format": "pdf"})).status_code == 400
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_export.py -v`
Expected: FAIL，`No module named 'app.services.exporters'`

- [ ] **Step 3: 实现**

`backend/app/services/exporters/md.py`：

```python
from app.services.llm.prompts import QUESTION_TYPE_LABELS


def _label(qtype: str) -> str:
    return QUESTION_TYPE_LABELS.get(qtype, qtype)


def question_section(q) -> str:
    source = f"[原帖]({q.source_url})" if q.source_url else "无链接"
    source_label = "来自原帖" if q.answer_source == "original" else "AI 生成"
    lines = [
        f"## [{_label(q.question_type)}] {q.content}",
        "",
        f"- 公司：{q.company or '未知'} ｜ 方向：{q.direction or '未知'} ｜ 轮次：{q.interview_round or '未知'}",
        f"- 来源：{source} ｜ 答案来源：{source_label}",
        "",
    ]
    answer = (q.answer_markdown or "").strip()
    if q.answer_source == "ai" and "\n---\n" in answer:
        oral, detail = answer.split("\n---\n", 1)
        lines += ["### 答案（口述版）", oral.strip(), "", "### 长文解释", detail.strip(), ""]
    else:
        lines += ["### 答案", answer or "（待补充）", ""]
    return "\n".join(lines)


def build_markdown(questions) -> str:
    return "# 面经题库导出\n\n" + "\n".join(question_section(q) for q in questions)
```

`backend/app/api/export.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Question
from app.schemas.question import QuestionOut
from app.services.exporters.md import build_markdown

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("")
async def export(format: str = "md", db: AsyncSession = Depends(get_db)):
    if format != "md":
        raise HTTPException(400, "目前仅支持 format=md")
    rows = (
        await db.execute(
            select(Question).where(Question.deleted_at.is_(None)).order_by(Question.id)
        )
    ).scalars().all()
    markdown = build_markdown([QuestionOut.model_validate(r) for r in rows])
    return StreamingResponse(
        iter([markdown]),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="mianjing-export.md"'},
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_export.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/exporters backend/app/api/export.py backend/tests/test_export.py
git commit -m "feat(backend): markdown export endpoint matching spec format"
```

---

### Task 12: 后端 Docker 化 + compose 集成 + 端到端验收

**Files:**
- Create: `backend/Dockerfile`
- Modify: `docker-compose.yml`（追加 backend 服务）
- Modify: `README.md`（quickstart）
- Test: 无新增单测；本任务交付物是"compose 一键起、真实截图端到端跑通"

**Interfaces:**
- Consumes: Task 1–11 全部
- Produces: `docker compose up -d --build` 后 `http://localhost:8000/health` 返回 ok；上传真实面经截图 → 题目自动入库 → 可搜索 → 可导出

- [ ] **Step 1: 写 backend/Dockerfile**

```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-ocr.txt ./
RUN pip install -r requirements.txt -r requirements-ocr.txt
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: compose 追加 backend 服务**

`docker-compose.yml` services 下追加（保留原 postgres 服务）：

```yaml
  backend:
    build: ./backend
    env_file: backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/mianjing
      UPLOAD_DIR: /app/data/images
    volumes:
      - ./data:/app/data
    ports:
      - "8000:8000"
    depends_on:
      - postgres
```

- [ ] **Step 3: 构建启动并冒烟**

```bash
cp backend/.env.example backend/.env   # 填入真实 DEEPSEEK_API_KEY
docker compose up -d --build
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`（首次构建较慢：paddle 约 1-2GB、zhparser 编译几分钟）

- [ ] **Step 4: 真实截图端到端验收（spec P1 验收标准）**

准备 10 张真实面经截图（放在 `data/samples/`，不入库 git）：

```bash
curl -X POST http://localhost:8000/api/ingest/images \
  -F "files=@data/samples/1.png" -F "files=@data/samples/2.png" \
  -F "files=@data/samples/3.png" -F "files=@data/samples/4.png" \
  -F "files=@data/samples/5.png" -F "files=@data/samples/6.png" \
  -F "files=@data/samples/7.png" -F "files=@data/samples/8.png" \
  -F "files=@data/samples/9.png" -F "files=@data/samples/10.png"
# 等待 1-3 分钟（OCR+LLM），然后：
curl "http://localhost:8000/api/tasks"            # 期望 status: done / done_with_warnings
curl "http://localhost:8000/api/questions"        # 期望 items 非空，题目为中文规范题
curl "http://localhost:8000/api/search?q=三次握手" # 期望命中
curl -o export.md "http://localhost:8000/api/export?format=md"  # 期望合法 Markdown
```

Expected: 任务 done（或 done_with_warnings 且题目已入库）；搜索命中；导出文件可用 Typora/Obsidian 打开且格式符合 spec §6.3。

- [ ] **Step 5: 全量回归 + README**

```bash
cd backend && python -m pytest -v -m "not slow"
```

Expected: 全部 passed。README 追加：

```markdown
## Quickstart（后端 P1）

```bash
cp backend/.env.example backend/.env   # 填 DEEPSEEK_API_KEY
docker compose up -d --build
# 上传：POST http://localhost:8000/api/ingest/images (multipart, 字段名 files)
# 题库：GET http://localhost:8000/api/questions
# 搜索：GET http://localhost:8000/api/search?q=...
# 导出：GET http://localhost:8000/api/export?format=md
```
```

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile docker-compose.yml README.md
git commit -m "feat(backend): dockerize api and wire compose deployment"
```

---

## Self-Review 记录

**1. Spec 覆盖对照（DESIGN.md → 计划任务）**

| spec 条目 | 覆盖任务 |
|---|---|
| §3.3 批量截图上传（拖拽/粘贴属前端，后端收 multipart） | Task 7 |
| §4.1 任务状态机 + 重试 | Task 6（状态机）、Task 8（retry API） |
| §4.2 步骤 1/2/3/5a/6/7/8/9/10 | Task 7（落盘）、Task 5（OCR+降噪）、Task 4/6（抽题+自检重试）、Task 6（去重/答案/入库） |
| §4.3 抽题 Schema（含 source_text_spans 幻觉约束进 Prompt） | Task 3、Task 4（Prompt 规则 1/5） |
| §4.4 答案规范（口述版+长文） | Task 4（ANSWER_SYSTEM）、Task 11（导出拆分） |
| §5 数据模型 5 张表 + search_vector | Task 2 |
| §6.1/6.2 API（P1 子集：ingest/tasks/questions/search/export） | Task 7/8/9/10/11 |
| §6.3 导出格式 | Task 11（逐字符断言） |
| §1.2 搜索范围 = 题干+答案+公司/方向 | Task 2 生成列 SQL（content/company/direction/answer_markdown 四列拼接） |
| P1 验收标准 | Task 12 Step 4 |

**2. Placeholder 扫描**：Task 2 Step 4 中故意保留的"占位修正"写法（先错后改）与 Task 10 的"实现注意（不要照抄占位行）"是**教学性对照**，均给出了最终正确代码；除此之外无 TBD/TODO/"类似 Task N"。

**3. 类型一致性检查**：`ExtractedQuestion` 字段在 Task 3/4/6 三处引用一致；`run_task(task_id, *, session_factory, ocr, llm, low_confidence_threshold)` 与 Task 8 retry 流程（status=pending → claim → run_task）衔接一致；`QUESTION_TYPE_LABELS` 在 Task 4 定义、Task 11 消费；`normalize_question_text` 在 Task 3 定义、Task 6 消费。已通过。

**4. 已知风险提示**：① PaddleOCR 2.7.3 与 numpy 2.x 存在兼容性问题，如遇报错在 requirements-ocr.txt 固定 `numpy<2`；② zhparser 首次构建依赖 xunsearch.com 下载 scws，若网络不通可改用 git 镜像源；③ `main.py` 中 5 个 router 的 include 顺序与各任务创建节奏需保持编译通过（建议 Task 2 先全部注释、随后逐个放开）。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-14-p1-backend-pipeline.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个任务派发独立子代理，任务间双阶段评审，迭代快。
2. **Inline Execution** — 使用 superpowers:executing-plans 在本会话内分批执行，带检查点。
