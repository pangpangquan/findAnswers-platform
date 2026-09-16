import asyncio
from dataclasses import dataclass, field

NOISE_KEYWORDS = ("水印", "点赞", "收藏", "关注", "小红书", "牛客网")


@dataclass
class OcrLine:
    text: str
    confidence: float
    box: list[list[int]] = field(default_factory=list)


@dataclass
class OcrResult:
    text: str
    avg_confidence: float
    lines: list[OcrLine] = field(default_factory=list)


def parse_ocr_result(raw_pages: list) -> OcrResult:
    """PaddleOCR 2.7 返回 [[ [box,(text,conf)], ... ]]；解析并过滤噪声行。"""
    lines: list[OcrLine] = []
    confs: list[float] = []
    page = raw_pages[0] if raw_pages and raw_pages[0] else []
    for box, (text_, conf) in page:
        if any(keyword in text_ for keyword in NOISE_KEYWORDS):
            continue
        lines.append(
            OcrLine(
                text=text_,
                confidence=float(conf),
                box=[[int(x), int(y)] for x, y in box],
            )
        )
        confs.append(float(conf))
    return OcrResult(
        text="\n".join(line.text for line in lines),
        avg_confidence=sum(confs) / len(confs) if confs else 0.0,
        lines=lines,
    )


class PaddleOcrService:
    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from paddleocr import PaddleOCR  # 本地未装则在此报错；Docker 内必装

            self._engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        return self._engine

    def _recognize_sync(self, image_path: str) -> OcrResult:
        raw = self._get_engine().ocr(image_path, cls=True)
        return parse_ocr_result(raw)

    async def recognize(self, image_path: str) -> OcrResult:
        return await asyncio.to_thread(self._recognize_sync, image_path)


class DummyOcrService:
    def __init__(self, preset: OcrResult):
        self.preset = preset

    async def recognize(self, image_path: str) -> OcrResult:
        return self.preset
