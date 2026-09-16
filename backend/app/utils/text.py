import unicodedata


def normalize_question_text(s: str) -> str:
    """NFKC 归一化 + 转小写 + 去全部空白，用于帖内题干去重。"""
    return "".join(unicodedata.normalize("NFKC", s).lower().split())
