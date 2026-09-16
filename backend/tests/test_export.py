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
