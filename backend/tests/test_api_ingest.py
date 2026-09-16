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
