from app.models import IngestTask, Question, SourceImage, SourcePost


async def test_create_post_image_task_question(app):
    async with app.state.session_factory() as session:
        post = SourcePost(platform="manual", title="测试帖")
        session.add(post)
        await session.flush()
        image = SourceImage(post_id=post.id, index=0, file_path="/tmp/a.png")
        session.add(image)
        await session.flush()
        task = IngestTask(post_id=post.id, task_type="manual_images")
        session.add(task)
        session.add(
            Question(
                post_id=post.id,
                image_id=image.id,
                content="讲讲 TCP 三次握手",
                question_type="eight_legged",
                answer_source="ai",
                confidence=0.9,
            )
        )
        await session.commit()

        assert post.id is not None
        assert task.status == "pending"
        assert task.retry_count == 0


async def test_search_vector_column_exists(app):
    from sqlalchemy import text

    async with app.state.engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'questions' AND column_name = 'search_vector'"
            )
        )
        assert rows.scalar() == "search_vector"
