# Geoting

Внутренний исследовательский сервис мониторинга AI Search Visibility (GEO — Generative Engine Optimization).

Geoting отправляет коммерческие prompts в выбранные AI-системы (OpenAI, Gemini, Perplexity) с web search / grounding, сохраняет полные сырые ответы, извлекает упоминания бренда, источники и конкурентов, оценивает качество представления компании и агрегирует результаты в GEO Dashboard.

> Это исследовательский инструмент для личного использования и GEO-экспериментов, **не** production SaaS.

## 1. Что такое Geoting

- Вы создаёте **проект** (компанию) с бренд-алиасами и списком конкурентов.
- Добавляете набор **коммерческих prompts** (например, «Куда во Владивостоке отдать ребёнка на английский?»).
- Выбираете **AI-провайдеров** и количество независимых запусков на prompt.
- Каждый `prompt × provider × run` выполняется как **полностью независимый API-запрос** без истории диалога.
- Сохраняется **полный сырой ответ** каждого AI.
- Отдельный AI-анализатор оценивает рекомендацию, тональность, точность описания и конкурентов.
- Исследование можно повторять и **сравнивать динамику** метрик.

## 2. Как установить

Требования: Docker, Python 3.9+, Node.js 18+.

```bash
# 1. Клонировать/скопировать репозиторий
# 2. Поднять PostgreSQL
docker compose up -d db

# 3. Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Frontend
cd ../frontend
npm install
```

## 3. Как настроить PostgreSQL

PostgreSQL запускается через `docker compose up -d db` (образ `postgres:16-alpine`, контейнер `geoting_db`).

- Порт на хосте: **5433** (чтобы не конфликтовать с уже запущенными локальными Postgres на 5432).
- Пользователь/пароль/БД: `geo` / `geo` / `geo_lab` (имя БД `geo_lab` сохранено для совместимости с существующими данными).

Если порт 5433 занят — поменяйте `ports` в `docker-compose.yml` и строку `DATABASE_URL` в `backend/.env`.

## 4. Как создать `.env`

```bash
cd backend
cp .env.example .env
# затем отредактируйте .env и вставьте свои API-keys
```

Минимальная конфигурация:

```env
DATABASE_URL=postgresql+psycopg://geo:geo@localhost:5433/geo_lab

# RouterAI — единый AI-шлюз (один ключ → все модели: OpenAI, Anthropic,
# Google, DeepSeek, Qwen и др.). Получите ключ на https://routerai.ru
ROUTERAI_API_KEY=sk-...
ROUTERAI_BASE_URL=https://routerai.ru/api/v1
ROUTERAI_DEFAULT_MODEL=deepseek/deepseek-v4-flash

MAX_CONCURRENT_REQUESTS=5
MAX_RETRIES=3
REQUEST_TIMEOUT_SECONDS=120

ANALYZER_MODEL=deepseek/deepseek-v4-flash
```

> `.env` никогда не коммитится (в `.gitignore`). Ключ хранится только в backend и вводится в Настройках → RouterAI.

## 5. Как запустить backend

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

Таблицы создаются автоматически при старте. Зависшие исследования после рестарта помечаются `failed`.

**Seed** (демо-данные для Priority Center, 20 prompts):

```bash
cd backend
.venv/bin/python -m app.seed
```

**Демо-исследование** (позволяет посмотреть dashboard без API-ключей; данные помечены как DEMO):

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/seed_demo_research.py 1
PYTHONPATH=. .venv/bin/python scripts/seed_demo_research.py 2
```

## 6. Как запустить frontend

```bash
cd frontend
npm run dev
```

Открыть http://localhost:5173. Vite проксирует `/api` на `http://localhost:8000`.

## 7. Как выполнить первое исследование

1. Откройте http://localhost:5173 → Projects.
2. Создайте проект (или используйте засеянный Priority Center), укажите `brand_aliases` (по одному на строку) и при необходимости `competitors`.
3. Откройте проект → вкладка **Prompts** → добавьте или импортируйте prompts (минимум 1 active).
4. В Настройках → RouterAI введите API-ключ и нажмите «Проверить подключение».
5. На странице проекта нажмите **Run research**: отметьте одну или несколько **AI-моделей** (по умолчанию отмечена модель из настроек), задайте `runs per prompt` — до запуска показывается суммарное число AI-запросов (`запросы × модели × повторы`).
6. Дождитесь выполнения (страница обновляется автоматически).
7. Откройте исследование: метрики GEO Visibility, таблица Prompt Results, Most cited sources, Competitors, графики динамики.
8. Клик по строке Prompt Results открывает полный ResearchRun: prompt, provider/model, raw answer, analysis, sources, competitors.
9. Выберите два исследования чекбоксами и нажмите **Compare** — появится таблица сравнения.

## 8. AI-модели через RouterAI

Geoting обращается ко всем AI-моделям через единый шлюз **RouterAI** (OpenAI-совместимый API). Модель передаётся как параметр в формате `provider/model` (например `deepseek/deepseek-v4-flash`, `openai/gpt-5.4`, `~anthropic/claude-sonnet-latest`).

- **Ключ**: Настройки → RouterAI → «Ввести API-ключ» (или `ROUTERAI_API_KEY` в `.env`). Ключ никогда не показывается целиком.
- **Список моделей**: Settings API получает живой каталог RouterAI (`GET /api/settings/models`); при недоступности используется встроенный запасной список.
- **Модель по умолчанию** (`ROUTERAI_DEFAULT_MODEL`) выбирается для новых исследований; каждое исследование и каждый run сохраняют свою модель.
- **Проверить подключение** выполняет реальный запрос к RouterAI.

Исторические исследования, выполненные до миграции через прямые API, сохраняют свой исходный `provider`/`model` и отображаются как «(legacy)».

## 9. Как импортировать prompts

CSV (первая строка — опциональный заголовок `text,cluster,intent`):

```csv
text,cluster,intent
"Куда во Владивостоке отдать ребёнка на английский?","children","commercial"
```

- Импорт: страница проекта → вкладка **Prompts** → кнопка импорта файла.
- Экспорт: кнопка **Export CSV**.
- Дубликаты по тексту пропускаются.

## 10. Ограничения текущей версии

- Исследование выполняется в фоне процесса uvicorn; при рестарте сервера во время исследования запуски помечаются `failed` (не продолжается с места).
- Миграции БД — аддитивные, идемпотентные `ALTER TABLE ... IF NOT EXISTS` при старте (нет Alembic; схему нужно расширять осознанно).
- Нет пользователей/авторизации — это внутренний инструмент.
- Нет scheduler/автоматических исследований.
- `brand_position` в heuristic-режиме (без настроенного анализатора) не определяется — метрики Top 3 / Avg Position будут пустыми.
- `supports_brand` у источников — эвристика (совпадение домена/алиаса), не абсолютная истина.
- Share of Voice — **эвристическая доля упоминаний** среди обнаруженных brand/competitor mentions, это НЕ доля рынка.
- Источники/цитаты берутся только из того, что вернул API. У многих моделей RouterAI веб-поиск/цитаты не возвращаются — тогда у run источники пустые (это честный результат).
- Использование моделей расходует баланс RouterAI; перед запуском Research UI показывает предупреждение.

---

Документация по архитектуре: [ARCHITECTURE.md](ARCHITECTURE.md).
