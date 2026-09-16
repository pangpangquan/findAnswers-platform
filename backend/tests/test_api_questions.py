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
