import base64

import pytest

from app.services.ocr import DummyOcrService, OcrResult, parse_ocr_result


def _raw_line(text_, conf):
    return [[[0, 0], [10, 0], [10, 10], [0, 10]], (text_, conf)]


def test_parse_filters_noise_and_computes_avg():
    raw = [
        [
            _raw_line("1. 讲讲 TCP 三次握手", 0.97),
            _raw_line("小红书", 0.99),  # 噪声，应被过滤
            _raw_line("2. 介绍一下 Redis 持久化", 0.93),
        ]
    ]
    result = parse_ocr_result(raw)
    assert "小红书" not in result.text
    assert result.lines[0].text == "1. 讲讲 TCP 三次握手"
    assert result.avg_confidence == pytest.approx(0.95)


def test_parse_empty_page():
    result = parse_ocr_result([[]])
    assert result.text == ""
    assert result.avg_confidence == 0.0


async def test_dummy_ocr_returns_preset():
    preset = OcrResult(text="预设文本", avg_confidence=0.95, lines=[])
    assert (await DummyOcrService(preset).recognize("/x.png")).text == "预设文本"


@pytest.mark.slow
async def test_real_paddleocr_smoke(tmp_path):
    pytest.importorskip("paddleocr")
    from app.services.ocr import PaddleOcrService

    png = tmp_path / "t.png"
    png.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    ))
    result = await PaddleOcrService().recognize(str(png))
    assert isinstance(result, OcrResult)
