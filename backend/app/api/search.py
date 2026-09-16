from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Question
from app.schemas.question import QuestionOut

router = APIRouter(prefix="/api/search", tags=["search"])

SEARCH_SQL = text(
    """
    SELECT q.id,
           ts_rank(q.search_vector, query) AS rank,
           ts_headline('zhparser', q.content, query,
                       'StartSel=<em>, StopSel=</em>, MaxWords=36, MinWords=10') AS headline
    FROM questions q, websearch_to_tsquery('zhparser', :q) query
    WHERE q.search_vector @@ query AND q.deleted_at IS NULL
    ORDER BY rank DESC
    LIMIT 50
    """
)


@router.get("")
async def search(q: str, db: AsyncSession = Depends(get_db)):
    if not q.strip():
        raise HTTPException(400, "搜索词不能为空")
    hits = (await db.execute(SEARCH_SQL, {"q": q})).mappings().all()
    items = []
    for hit in hits:
        question = await db.get(Question, hit["id"])
        if question is None:
            continue
        item = QuestionOut.model_validate(question).model_dump(mode="json")
        item["rank"] = float(hit["rank"])
        item["headline"] = hit["headline"]
        items.append(item)
    return {"items": items}
