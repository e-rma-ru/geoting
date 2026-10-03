# Geoting — Project

Внутренний исследовательский сервис мониторинга AI Search Visibility (GEO).

## Стек

- Backend: Python 3.9+, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16 (Docker), httpx.
- AI gateway: RouterAI (OpenAI-совместимый), один ключ на все модели.
- Frontend: React 18 + Vite, Tailwind CSS, Recharts, React Router.
- Демо-проект: Priority Center (Владивосток, языковой центр).

## Ключевые документы

- `README.md` — установка и запуск.
- `ARCHITECTURE.md` — архитектура (сущности БД, пайплайны, метрики, AI/RouterAI, точки расширения).

## Актуальное состояние архитектуры

- **AI-шлюз**: Geoting общается с AI-моделями только через RouterAI
  (`ROUTERAI_BASE_URL` = `https://routerai.ru/api/v1`, ключ `ROUTERAI_API_KEY`).
  Модель — параметр в формате `provider/model` (`deepseek/deepseek-v4-flash`,
  `openai/gpt-5.4`, …). Прямые интеграции OpenAI/Gemini/Perplexity удалены.
  Исторические runs сохраняют исходные `provider`/`model` (показ «legacy»).
- **Research = эксперимент**: Research не привязан к одной модели. У него есть
  набор выбранных моделей (`research_models`) и независимые runs
  (`prompts × models × runs_per_prompt`). Каждый `ResearchRun` хранит свою
  `model`/`provider` — фундамент будущего cross-model сравнения.
- **Анализ**: brand_mentioned — программно (алиасы + fuzzy), семантика —
  LLM через RouterAI; при недоступности — heuristic без фейковых значений.
- **AI-профили компаний**: строятся явно (кнопка) из уже собранных ответов;
  чтение dashboard никогда не вызывает AI API.
- **Concurrency**: глобальный semaphore `MAX_CONCURRENT_REQUESTS`.
- **DEMO**: только предсозданные данные; открытие/seed не вызывает AI API.
- **Миграции БД**: аддитивные идемпотентные `ALTER TABLE ... IF NOT EXISTS` на старте.
- **Ключи**: единственный `ROUTERAI_API_KEY` в `backend/.env`, runtime-оверрайд
  через Settings UI; полный ключ не возвращается frontend, не логируется.

## Быстрые команды

```bash
docker compose up -d db
cd backend && .venv/bin/uvicorn app.main:app --port 8000
cd frontend && npm run dev
```

Тесты: `cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests -q`
Сборка: `cd frontend && npm run build`
