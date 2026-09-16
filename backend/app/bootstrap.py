from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import Base

SEARCH_VECTOR_SQL = """
ALTER TABLE questions ADD COLUMN IF NOT EXISTS search_vector tsvector
GENERATED ALWAYS AS (
  to_tsvector('zhparser',
    coalesce(content, '') || ' ' || coalesce(company, '') || ' ' ||
    coalesce(direction, '') || ' ' || coalesce(answer_markdown, ''))
) STORED
"""

GIN_SQL = "CREATE INDEX IF NOT EXISTS ix_questions_search_vector ON questions USING GIN (search_vector)"

# zhparser 扩展只注册 parser，configuration 需手动创建（幂等：先查 pg_ts_config）
ZHCONFIG_SQL = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'zhparser') THEN
    CREATE TEXT SEARCH CONFIGURATION zhparser (PARSER = zhparser);
    ALTER TEXT SEARCH CONFIGURATION zhparser ADD MAPPING FOR n,v,a,i,e,l WITH simple;
  END IF;
END $$;
"""


async def init_db(engine: AsyncEngine) -> None:
    """幂等：建扩展与搜索配置、建表、加 search_vector 生成列与 GIN 索引。"""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS zhparser"))
        await conn.execute(text(ZHCONFIG_SQL))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(SEARCH_VECTOR_SQL))
        await conn.execute(text(GIN_SQL))
