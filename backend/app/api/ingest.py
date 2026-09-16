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
