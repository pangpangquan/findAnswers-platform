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
