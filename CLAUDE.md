# HH Auto Apply — проект

Форк [hh.ru-clicker](https://github.com/Vlad9572324/hh.ru-clicker) с доработками.

## Архитектура

FastAPI веб-дашборд + reverse-engineered API hh.ru (476 эндпоинтов).
Без Playwright — прямые HTTP запросы к HH.

```
web_app.py → FastAPI app
app/
├── config.py          # Настройки (runtime через дашборд)
├── manager.py         # BotManager — оркестратор (1824 строки)
├── hh_api.py          # Парсинг HH.ru страниц (BS4)
├── hh_apply.py        # Отправка откликов, опросники
├── hh_chat.py         # Чат через chatik.hh.ru API
├── hh_negotiations.py # Статистика переговоров
├── hh_resume.py       # Парсинг резюме
├── llm.py             # DeepSeek/OpenAI интеграция
├── questionnaire.py   # Заполнение опросников
├── oauth.py           # OAuth2 токены
├── state.py           # AccountState
├── storage.py         # Файловое хранилище (JSON)
├── websocket.py       # WebSocket实时 обновления
├── logging_utils.py   # Логи
└── routes/            # API роуты
```

## Доработки относительно оригинала

1. Anti-AI-detector промпты (разная длина, отсутствие штампов)
2. Telegram нотификации через Hermes (файловый мост)
3. .env поддержка для DeepSeek API ключа
4. Default конфиг с поисковыми запросами

## Запуск

```bash
# Docker
docker-compose up -d

# Локально
pip install -r requirements.txt
python web_app.py
```

Дашборд: http://localhost:8000
