# 面经整理平台

个人自用：从小红书/牛客/截图收集面经，自动整理成一题一答案的规范题库。

- 设计文档：`docs/DESIGN.md`
- 实施计划：`docs/superpowers/plans/`

## Quickstart（后端 P1）

```bash
cp backend/.env.example backend/.env   # 填 DEEPSEEK_API_KEY
docker compose up -d --build
# 前端：http://localhost:8080（上传/任务/题库/搜索/导出）
# 上传：POST http://localhost:8000/api/ingest/images (multipart, 字段名 files)
# 题库：GET http://localhost:8000/api/questions
# 搜索：GET http://localhost:8000/api/search?q=...
# 导出：GET http://localhost:8000/api/export?format=md
```
