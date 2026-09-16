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
