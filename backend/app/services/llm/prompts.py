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
