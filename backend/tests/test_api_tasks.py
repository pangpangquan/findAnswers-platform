from sqlalchemy import select

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
        remaining = (await session.execute(select(Question))).scalars().all()
        assert remaining == []


async def test_retry_non_failed_returns_409(app, client):
    task_id = await seed_task(app, status="done")
    resp = await client.post(f"/api/tasks/{task_id}/retry")
    assert resp.status_code == 409
