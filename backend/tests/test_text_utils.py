from app.utils.text import normalize_question_text


def test_normalize_strips_space_and_case():
    assert normalize_question_text("讲讲 TCP 三次握手") == normalize_question_text("讲讲tcp三次握手")


def test_normalize_fullwidth_to_halfwidth():
    assert normalize_question_text("Ｒｅｄｉｓ 持久化？") == normalize_question_text("redis持久化?")


def test_normalize_removes_all_whitespace():
    assert normalize_question_text(" a b\tc ") == "abc"
