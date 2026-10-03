# Geoting — Architecture

## Обзор

Стек:

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL (asyncpg/psycopg), httpx, asyncio.
- **Frontend**: React 18 + Vite, Tailwind CSS, Recharts, React Router.
- **Инфраструктура**: Docker Compose (PostgreSQL 16).

Логический поток:

```
Project + Prompts
   └─ POST /api/research  → ResearchService
        ├─ создаёт Research (queued) + ResearchRun для каждого prompt × provider × run
        └─ фоновая задача (asyncio):
             semaphore (MAX_CONCURRENT_REQUESTS)
             └─ для каждого ResearchRun:
                  AIProvider.run_prompt(prompt)          # независимый API-запрос
                  → сохраняется полный raw_response
                  → AnalysisService:
                       brand_mentioned (программно, алиасы)
                       LLM-анализ (рекомендация, тональность, точность, конкуренты)
                       sources → Citations (домен, source_type, supports_brand)
                  → статус completed/failed
        └─ Research → completed/failed
   └─ Dashboard/Compare вычисляются на лету из сохранённых данных
```

## Сущности БД

Все модели в `backend/app/models/`.

| Таблица | Назначение | Ключевые поля |
| --- | --- | --- |
| `projects` | Компания | name, website, city, country, category, description, target_audience, services, `brand_aliases` (JSON), `competitors` (JSON) |
| `prompts` | Исследовательский запрос | project_id, text, cluster, intent, active |
| `research` | Один эксперимент | project_id, name, status (queued/running/completed/failed), prompts_count, providers_count, runs_per_prompt, started_at, completed_at |
| `research_models` | Участники эксперимента (выбранные AI-модели) | research_id (FK), model, provider, created_at; unique (research_id, model) |
| `research_runs` | Наблюдение: конкретный prompt × model × run | research_id, prompt_id, provider, model, run_number, status, `response_text`, `raw_response` (JSON), response_time_ms, error_message |
| `mention_analyses` | Результат анализа одного ответа | research_run_id (unique), brand_mentioned, brand_position, recommendation_score, sentiment, accuracy_score, confidence, reasoning, `is_heuristic`, `raw_analysis` (JSON) |
| `citations` | Источник из ответа | research_run_id, url, domain, title, cited_text, supports_brand, source_type |
| `competitor_mentions` | Упоминание конкурента в ответе | research_run_id, competitor_name, position, recommendation_score |

Связи: `Project 1—N Prompt`, `Project 1—N Research`, `Research 1—N ResearchRun`, `ResearchRun 1—1 MentionAnalysis`, `ResearchRun 1—N Citation`, `ResearchRun 1—N CompetitorMention`.

`raw_response` хранится всегда — это обязательное требование (полный оригинальный ответ AI).

## AI / RouterAI Architecture

Geoting обращается ко всем AI-моделям через **единый API-шлюз RouterAI** (OpenAI-совместимый `chat/completions`). Приложение не знает деталей API конкретных AI-провайдеров: конкретная модель передаётся как параметр в формате `provider/model`.

```
Geoting ──▶ AIProvider abstraction ──▶ RouterAI (ROUTERAI_BASE_URL /chat/completions)
                                          ├── openai/gpt-5.4
                                          ├── anthropic/...
                                          ├── google/...
                                          ├── deepseek/deepseek-v4-flash
                                          └── ...
```

- **Ключ**: единственный `ROUTERAI_API_KEY` (Bearer). Хранится в `backend/.env`, runtime-оверрайд через Settings UI (`secret_store`). Полный ключ никогда не возвращается frontend, только `key_hint`.
- **Base URL**: `ROUTERAI_BASE_URL`, default `https://routerai.ru/api/v1`, централизованно в `config.py`.
- **Модели**: `backend/app/services/model_catalog.py` — живой каталог `GET {base}/models` (кэш 30 мин, фильтр токено-тарифных текстовых моделей) + встроенный запасной список `DEFAULT_MODEL_CATALOG`. Единый источник ID моделей для UI (`GET /api/settings/models`).
- **Модель по умолчанию**: `ROUTERAI_DEFAULT_MODEL`; меняется в Settings (`runtime_config_store`). При создании Research модель фиксируется и сохраняется.
- **Анализатор и AI-профили**: идут через тот же RouterAI (`chat_json` в `analyzer.py`), `ANALYZER_MODEL` задаёт модель.
- **Ошибки** (`AIProvider._request_with_retry`): 401/403 → `ProviderAuthError` (без ретраев); 400/404/422 → `ProviderError`; 429/5xx и timeout/network → ретраи с экспоненциальной паузой.
- **Concurrency**: глобальный `asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)` (модульный, общий для всех Research).
- **Безопасность**: ключ не логируется, не попадает в raw response/ошибки/URL/git.
- **DEMO**: demo research и seed используют только предсозданные данные; чтение dashboard/runs/profiles никогда не создаёт AI-запросы; пайплайн исполняет только runs со статусом `queued`.

## Provider abstraction

`backend/app/providers/base.py`:

```python
class AIProvider(ABC):
    async def run_prompt(self, prompt: str, config: Optional[dict] = None) -> AIResponse:
        ...
```

`AIResponse` — унифицированный результат:

```python
class AIResponse(BaseModel):
    provider: str
    model: str
    text: str
    sources: list[Source]      # url, title, cited_text — только реальные источники от API
    raw_response: Any          # полный ответ API
    response_time_ms: int
```

Реализации (единственная активная):

| Provider | API | Web search / grounding | Источники |
| --- | --- | --- | --- |
| `RouterAIProvider` | `POST {base}/chat/completions` (OpenAI-совместимый) | зависит от выбранной модели | парсит `citations[]`, если gateway их вернёт; иначе пусто (честно) |

Исполнители моделей OpenAI/Gemini/Perplexity раньше были отдельными классами `OpenAIProvider`/`GeminiProvider`/`PerplexityProvider` с собственными ключами и endpoints — после миграции они удалены. Исторические Research/runs, выполненные до миграции, сохраняют исходные `provider`/`model` в БД и отображаются с пометкой «(legacy)»; новые runs всегда имеют `provider=routerai`.

Источники не придумываются — используются только возвращённые API. У многих моделей RouterAI веб-поиск/цитаты не возвращаются → у run источники пустые.

Retry с экспоненциальной паузой (429, 5xx, timeout, network): в `AIProvider._request_with_retry`, параметры из `.env` (`MAX_RETRIES`, `REQUEST_TIMEOUT_SECONDS`).

Реестр: `backend/app/providers/__init__.py` (`PROVIDER_REGISTRY` содержит только `routerai`, `get_provider`, `provider_status`).

## Research pipeline

### Концепция: один Research = один эксперимент

```
Research (эксперимент)
 ├── prompts
 ├── selected models (ResearchModel)
 │     ├── deepseek/deepseek-v4-flash
 │     ├── openai/gpt-5.4
 │     └── ...
 └── runs (независимые наблюдения)
       ├── prompt A × model A (× repetitions)
       ├── prompt A × model B
       ├── prompt B × model A
       └── ...
```

Research больше не привязан к одной модели: количество runs = `prompts × models × runs_per_prompt`.
Каждый `ResearchRun` хранит свою `model` (и `provider=routerai`), поэтому можно однозначно сказать,
какой моделью выполнен конкретный ответ, и в будущем агрегировать метрики по моделям.
Исторические (legacy) Research, созданные до этой схемы, мигрированы в `research_models`
и продолжают открываться.

`backend/app/services/research_service.py`.

1. `create_research`:
   - валидирует проект, RouterAI-ключ и выбранные модели (по каталогу; `models[]` ≥ 1; legacy `model`/default как фолбэк);
   - берёт все `active` prompts проекта;
   - создаёт `Research` (status=`queued`), строки `ResearchModel` для каждой модели и `ResearchRun` для каждого `prompt × model × run_number` (status=`queued`, `provider=routerai`, `model` — модель конкретного run);
   - запускает фоновую задачу `_run_research` через `asyncio.create_task`.
2. `_run_research`:
   - `Research` → `running`;
   - обработка запусков с `asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)` и `asyncio.gather`;
   - каждый запуск работает в **отдельной сессии БД** (без общих объектов), что исключает гонки;
   - каждый запуск — отдельный `provider.run_prompt` (независимый контекст);
   - при завершении `Research` → `completed` (или `failed`, если упали все запуски).
3. `_process_run`:
   - `run` → `running`;
   - вызов `RouterAIProvider.run_prompt(model из run)`, сохранение `response_text`, `raw_response`, `model`, `response_time_ms`;
   - `run` → `completed` + запуск `AnalysisService`;
   - при ошибке: `run` → `failed` + `error_message` (не более 2000 символов).

Восстановление после рестарта: `main.recover_interrupted_research` помечает `running/queued` research и runs как `failed`.

## Analysis pipeline

`backend/app/services/analysis_service.py` + `branding.py` + `analyzer.py`.

Принцип: **не доверяем LLM там, где можно посчитать программно**.

### Программно (детерминированно)

- **brand_mentioned** — поиск по `brand_aliases` с нормализацией текста, fuzzy-matching (difflib) и оконной проверкой контекста для однострочных алиасов (слово «Priority» без контекста не считается упоминанием).
- **domains** — извлекаются из URL (`urllib.parse`).
- **source_type** — эвристика по домену (official_site/map/directory/review/media/social/forum/blog/other/unknown).
- **supports_brand** — эвристика: домен совпадает с сайтом проекта, либо алиас встречается в URL/title/cited_text.

### LLM (семантическое)

- **recommendation_score** (0–5 по рубрике), **sentiment**, **accuracy_score**, **confidence**, **reasoning**, **brand_position**, **competitors**.
- Вызов `analyze_with_llm` (RouterAI `chat/completions` с `response_format: json_object`) с JSON-schema в system-промпте.
- Если RouterAI не настроен или вызов упал — `is_heuristic=True`, семантические поля `null`/`unknown`, `brand_position` не определяется. **Никаких фейковых значений.**

Итоговая `brand_mentioned` всегда программная; LLM-значение сохраняется в `raw_analysis` для референса.

## Metrics

`backend/app/services/metrics.py`. Метрики считаются на лету из сохранённых данных (`compute_research_metrics`). Знаменатель — все `ResearchRun` исследования (включая failed; failed-запуски без анализа не считаются упоминанием).

| Метрика | Формула | Источник |
| --- | --- | --- |
| Mention Rate | mentions / total_runs × 100 | программная brand_mentioned |
| Top 3 Rate | runs с brand_position ≤ 3 / total_runs × 100 | LLM brand_position |
| Average Position | среднее brand_position среди упоминаний | LLM brand_position |
| Recommendation Rate | runs с recommendation_score ≥ 3 / total_runs × 100 | LLM |
| Average Recommendation Score | средний recommendation_score по всем анализам (0 = отсутствует) | LLM |
| Citation Rate | runs с citation, поддерживающим бренд / total_runs × 100 | supports_brand (эвристика) |
| Entity Accuracy | средний accuracy_score | LLM |
| Share of Voice | brand mentions / (brand + competitor mentions) × 100 | бренд + LLM-конкуренты |

Share of Voice — **эвристическая доля упоминаний, а не доля рынка** (документировано в UI и в `METHODOLOGY_NOTES`).

Интерфейс явно помечает: `AI analysis / heuristic — не ground truth`.

## API (основные endpoint-ы)

- `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/{id}`
- `GET/POST /api/projects/{id}/prompts`, `PUT/DELETE /api/prompts/{id}`, `POST …/prompts/import`, `GET …/prompts/export`
- `POST /api/research` (запуск), `GET /api/projects/{id}/research`, `GET /api/research`, `GET /api/research/{id}`, `GET /api/research/{id}/runs`, `GET /api/runs/{id}`
- `GET /api/research/{id}/dashboard`, `GET /api/research/{id}/metrics`, `GET /api/projects/{id}/dashboard` (time series), `GET /api/compare?research_ids=1,2`
- `GET /api/settings` (статус интеграций, ключи не показываются)
- `GET /api/health`

## Frontend

- `src/pages/Projects.jsx` — карточки проектов, создание.
- `src/pages/ProjectDetail.jsx` — инфо проекта, запуск исследования, таблица исследований + чекбоксы сравнения, CRUD prompts (фильтр по cluster, import/export CSV, toggle active).
- `src/pages/ResearchDashboard.jsx` — GEO Visibility (6 метрик), Prompt Results (клик → run detail), Most cited sources (фильтр all/brand/competitor), Competitors, графики динамики, панель сравнения.
- `src/pages/RunDetail.jsx` — prompt, provider/model, raw answer (+ raw JSON), analysis, sources, competitors.
- `src/pages/Researches.jsx`, `src/pages/Settings.jsx`.

## Точки расширения

- **Новые провайдеры**: класс `AIProvider` + регистрация в `PROVIDER_REGISTRY` + конфиг в `.env` (см. README §8).
- **Новые аналитические модели**: расширить `ANALYZER_PROVIDER`/`ANALYZER_MODEL`, добавить ветку в `analyzer.analyze_with_llm`.
- **Пользователи/авторизация**: middleware + таблица users (сейчас инструмент внутренний, auth нет).
- **Scheduler / автоматические исследования**: обёртка над `create_research` (cron/APScheduler); фоновая задача уже изолирована от HTTP-запроса.
- **Несколько клиентов/тенанты**: добавить `tenant_id` в проекты и фильтры.
- **Auto-discovery конкурентов**: сервис, агрегирующий `CompetitorMention` по повторным исследованиям.
- **Миграции**: переход с `create_all` на Alembic при усложнении схемы.
- **Экспорт отчётов**: сериализация `compute_research_detail` в PDF/CSV.
