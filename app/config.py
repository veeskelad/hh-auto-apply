"""
Configuration: Config class, accounts_data, save/load functions, URL helpers.
"""

import json
import threading
from pathlib import Path

from app.logging_utils import log_debug

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"


# ============================================================
# АККАУНТЫ
# ============================================================

# Загружается из data/accounts.json при старте (через load_accounts())
accounts_data: list = []


# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

# Дефолтные паттерны «сообщение HR не требует ответа» (вежливые отписки/уведомления).
# Используются, если CONFIG.llm_skip_patterns не задан. Regex, case-insensitive.
DEFAULT_LLM_SKIP_PATTERNS = [
    r"рассмотр\w*\s+ваше\s+резюме",
    r"если\b.{0,40}(подойд|заинтересу|совпад).{0,40}свяж",
    r"мы\s+свяж\w*\s+с\s+вами",
    r"свяж\w*\s+с\s+вами\s+(если|в\s+случае)",
    r"спасибо\s+за\s+(ваш\s+)?отклик",
    r"ваш\s+отклик\s+(получен|принят|зарегистр)",
    r"ваше\s+резюме\s+(получен|принят|передан)",
    r"вакансия\s+(закрыт|на\s+паузе|приостановл)",
    r"к\s+сожалению.{0,60}(не\s+готовы|отказ|не\s+подход)",
]

# Маркеры вопроса/действия — если есть в сообщении, оно ТРЕБУЕТ ответа (отменяет skip).
LLM_QUESTION_MARKERS = [
    "?", "сколько", "когда", "готов", "расскажи", "уточни", "пришли",
    "подтверди", "укажи", "напиши", "ответь", "можете ли", "удобно",
    "созвон", "звонок", "интервью", "собеседован", "тестов", "задани",
]


class Config:
    """Глобальные настройки (можно менять в runtime)"""
    pages_per_url = 40
    max_concurrent = 20
    response_delay = 1
    pause_between_cycles = 60
    limit_check_interval = 30
    resume_touch_interval = 4
    batch_responses = 3
    min_salary = 0  # Минимальная зарплата в руб (0 = без фильтра)
    auto_pause_errors = 5  # Авто-пауза после N ошибок подряд (0 = выключено)
    auto_apply_tests: bool = False  # Автоматически проходить опросники при откликах
    use_oauth_apply: bool = False  # Использовать OAuth API для откликов (вместо web cookies)
    daily_apply_limit: int = 0  # Жёсткий лимит откликов в день (0 = без ограничения)
    stop_on_hh_limit: bool = True  # Полная остановка при HH лимите (не перепроверять)
    # Фильтр по формату работы (пустой = без фильтра, все форматы)
    # Возможные значения: "fullDay", "remote", "flexible", "shift", "flyInFlyOut"
    allowed_schedules: list = []
    # Стоп-слова в заголовке вакансии: если слово встречается в названии — НЕ откликаться
    title_blacklist: list = []
    # Если непустой — откликаться ТОЛЬКО на вакансии, где в названии есть хотя бы одно слово
    title_whitelist: list = []

    # LLM auto-reply settings
    llm_enabled: bool = False
    llm_auto_send: bool = False       # False = черновик в очередь подтверждения (по умолчанию); True = слать сразу
    llm_use_cover_letter: bool = True  # Передавать сопроводительное письмо в контекст
    llm_use_resume: bool = True        # Включать текст резюме в системный промпт
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_profiles: list = None         # [{name, api_key, base_url, model, enabled}]
    llm_profile_mode: str = "fallback"  # "fallback" | "roundrobin"
    skip_inconsistent: bool = False  # Пропускать вакансии с несовпадением опыта
    filter_agencies: bool = False  # Исключить кадровые агентства из поиска
    filter_low_competition: bool = False  # Только вакансии с <10 откликами
    search_period_days: int = 0  # 0 = все, 1-30 = последние N дней
    llm_fill_questionnaire: bool = False  # Использовать LLM для заполнения опросников
    # Сообщения HR, не требующие ответа (вежливые отписки/уведомления без вопроса).
    # Если последнее сообщение работодателя матчит паттерн и не содержит вопроса —
    # бот не отвечает и не создаёт черновик. Паттерны — regex, case-insensitive.
    llm_skip_patterns: list = None
    llm_check_interval: int = 5  # Интервал проверки чатов LLM (в минутах, мин 2)
    # Anti-AI-detector prompt: разная длина предложений, живые интонации, без штампов
    llm_system_prompt: str = (
        "Ты помощник соискателя работы. Отвечай на сообщения от HR и работодателей. "
        "Пиши от первого лица (пол — по профилю соискателя).\n\n"
        "ПРАВИЛА (важно соблюдать):\n"
        "1. Разная длина предложений: короткие (3-5 слов) чередуй с длинными (10-15 слов). "
        "Не делай все предложения одной длины.\n"
        "2. Без штампов: НЕ используй «с большим интересом», «буду рад», «внести вклад», "
        "«рассмотрите мою кандидатуру», «с удовольствием», «искренний интерес», "
        "«возможность присоединиться», «ценю ваше время». Вообще никаких штампов.\n"
        "3. Естественная пунктуация: иногда без восклицательных знаков, без длинных тире, "
        "без лишних запятых. Как человек в мессенджере.\n"
        "4. Конкретика и релевантность: когда спрашивают про опыт или навык — бери из "
        "резюме именно то, что относится к вопросу, и говори конкретно что делал. Если "
        "прямого опыта под вопрос нет — честно скажи про близкий/смежный, который поможет, "
        "без выдумок. Если про время — назови конкретное время.\n"
        "5. Дружелюбно, но не официозно. Как с коллегой, которого уважаешь.\n"
        "6. Соглашайся на предложенное время собеседования или предложи конкретную альтернативу.\n"
        "7. НЕ используй эмодзи в каждом сообщении. Только если реально к месту.\n"
        "8. Не начинай каждое сообщение с «Здравствуйте!» или «Добрый день!». "
        "Если это продолжение переписки — начни сразу по делу.\n"
        "9. Не пиши больше 3-4 предложений, если не требуется развёрнутый ответ.\n"
        "10. Не используй конструкцию «Я бы...» — говори уверенно: «Я могу», «Я готов», «Да».\n"
        "11. НЕ называй компании-работодателей: ни куда устраиваешься сейчас, ни свои "
        "прошлые места работы (никаких «ООО ...», брендов, названий фирм). Описывай ТОЛЬКО "
        "что именно делал и какой стек использовал — «внедрил AI-систему на n8n», «настроил "
        "пайплайны на TypeScript/Python», а не «в компании X». Названия технологий (n8n, "
        "Qdrant, Python) — можно и нужно."
    )

    # Промпт генерации сопроводительных писем под вакансию (по гайдам hh.ru)
    llm_cover_letter_prompt: str = (
        "Ты пишешь сопроводительное письмо к отклику на вакансию hh.ru от лица соискателя "
        "(пол — по профилю/резюме). Опирайся ТОЛЬКО на факты из резюме, ничего не выдумывай.\n\n"
        "ВАЖНО: письмо читает не только рекрутер, но и AI-скрининг/ATS работодателя. Поэтому "
        "естественно вплетай ключевые навыки и термины из описания вакансии — те, под которые "
        "у тебя реально есть опыт, — чтобы автоматический отбор их распознал. НО без "
        "keyword-stuffing: не сухой список через запятую, а связно, в контексте того, что делал. "
        "Письмо должно дополнять резюме мотивацией и контекстом, а не быть его копией.\n\n"
        "ЧЕГО НЕ ДЕЛАТЬ (важно):\n"
        "— НЕ называй компанию-работодателя по имени и не пиши «в вашу компанию X». Говори про "
        "саму роль/задачи, а не про конкретного работодателя.\n"
        "— НЕ называй свои прошлые места работы и работодателей (никаких «в компании X я делал»). "
        "Говори про опыт и СТЕК обезличенно: что умеешь, с какими технологиями работал и как это "
        "закрывает требования вакансии.\n\n"
        "О ЧЁМ ПИСАТЬ:\n"
        "1. Покажи, что прочитал вакансию: зацепись за её ЗАДАЧИ и технологии (без названия "
        "компании) и скажи, чем направление работы тебе интересно — искренне, без лести.\n"
        "2. Дай 2-3 сильных доказательства релевантности под ключевые требования: что умеешь, "
        "с каким стеком работал и какой получался результат — обезличенно, без названий компаний. "
        "Свяжи свой стек с требованиями вакансии.\n"
        "3. Если прямого опыта под требование нет — честно назови близкий/смежный, без выдумок.\n\n"
        "СТРУКТУРА — 3-4 абзаца, каждый про одну мысль, разделяй ПУСТОЙ строкой:\n"
        "• Абзац 1: на какую позицию откликаюсь + чем интересны задачи вакансии (1-2 предложения).\n"
        "• Абзац 2-3: релевантный опыт под требования (что умею → стек → результат), без названий "
        "компаний. Свяжи стек с задачами вакансии.\n"
        "• Последний абзац: какую пользу принесу / готов обсудить детали.\n\n"
        "ОБЪЁМ: 250-350 слов. Достаточно, чтобы раскрыть релевантный опыт для AI-скрининга, "
        "но без воды — каждое предложение по делу.\n\n"
        "ФОРМАТИРОВАНИЕ: это hh.ru, ТОЛЬКО обычный текст. НЕ используй markdown — никакого "
        "**жирного**, курсива, заголовков #, списков с «•», «-», «*». Только абзацы через "
        "пустую строку (\\n\\n).\n\n"
        "СТИЛЬ — живо и по-человечески (это важно):\n"
        "4. Пиши как живой человек, а не как бот или отдел кадров. Искренне, тепло, на «вы». "
        "Можно лёгкую индивидуальность — но без фамильярности и без эмодзи.\n"
        "5. Разная длина предложений: короткие (3-5 слов) чередуй с длинными. Не моноритм.\n"
        "6. БЕЗ штампов и канцелярита: НЕ используй «с большим интересом», «буду рад», «внести "
        "вклад», «рассмотрите мою кандидатуру», «с удовольствием», «возможность присоединиться», "
        "«командный игрок», «стрессоустойчивость», «динамично развивающаяся», «готов развиваться». "
        "НЕ нанизывай buzzword'ы («production-grade», «multi-agent», «отказоустойчивость») — "
        "объясняй простыми словами, что конкретно делал.\n"
        "7. Естественная пунктуация, без длинных тире. Уверенно: «Я делал», «Я умею», не «Я бы мог».\n"
        "8. Выводи ТОЛЬКО текст письма — БЕЗ приветствия в первой строке (добавится отдельно) "
        "и БЕЗ блока контактов/подписи (добавится отдельно)."
    )

    # Шаблонные ответы на опросы (list of {keywords: [...], answer: "..."})
    questionnaire_templates: list = []
    # Ответ по умолчанию (когда ни один шаблон не подошёл)
    questionnaire_default_answer: str = "Готова рассказать подробнее на собеседовании."

    # Глобальный пул поисковых URL (выбираются на карточке каждого аккаунта)
    url_pool: list = []  # [{url, pages}, ...] или plain строки (legacy)

    # Шаблоны сопроводительных писем (list of {name: str, text: str})
    letter_templates: list = [
        {
            "name": "Стандартное",
            "text": (
                "Здравствуйте!\n\n"
                "Я выражаю искренний интерес к возможности присоединиться к вашей компании.\n\n"
                "Я ознакомился с деятельностью вашей организации и уверен, что мой опыт и навыки "
                "смогут внести вклад в вашу команду.\n\n"
                "Хочу отметить, что я всегда готов обучаться новому и развиваться в профессиональном плане.\n\n"
                "Считаю, что ваша компания предоставляет отличные возможности для роста и "
                "самосовершенствования, и мне бы хотелось стать частью вашей команды.\n\n"
                "С уважением,\n[ИМЯ]\n[t.me: @username]\n[📞 телефон]"
            ),
        }
    ]


CONFIG = Config()
CONFIG.llm_profiles = []


def _url_entry(item) -> dict:
    """Нормализует элемент url_pool в {url, pages}."""
    if isinstance(item, str):
        return {"url": item.strip(), "pages": CONFIG.pages_per_url}
    return {"url": item.get("url", "").strip(), "pages": int(item.get("pages", CONFIG.pages_per_url))}


def _url_pages_map() -> dict:
    """Возвращает {url_str: pages} из CONFIG.url_pool."""
    return {e["url"]: e["pages"] for u in CONFIG.url_pool for e in [_url_entry(u)]}


_CONFIG_KEYS = [
    "pages_per_url", "max_concurrent", "response_delay", "pause_between_cycles",
    "limit_check_interval", "resume_touch_interval", "batch_responses", "min_salary",
    "auto_pause_errors", "questionnaire_default_answer", "llm_fill_questionnaire",
    "skip_inconsistent", "use_oauth_apply", "daily_apply_limit", "stop_on_hh_limit", "llm_check_interval",
    "filter_agencies", "filter_low_competition", "search_period_days",
]


def save_config():
    """Сохранить текущий CONFIG на диск."""
    data = {k: getattr(CONFIG, k) for k in _CONFIG_KEYS}
    data["questionnaire_templates"] = CONFIG.questionnaire_templates
    data["letter_templates"] = CONFIG.letter_templates
    data["allowed_schedules"] = CONFIG.allowed_schedules
    data["title_blacklist"] = CONFIG.title_blacklist
    data["title_whitelist"] = CONFIG.title_whitelist
    data["auto_apply_tests"] = CONFIG.auto_apply_tests
    data["use_oauth_apply"] = CONFIG.use_oauth_apply
    data["url_pool"] = CONFIG.url_pool
    data["llm_api_key"] = CONFIG.llm_api_key
    data["llm_base_url"] = CONFIG.llm_base_url
    data["llm_model"] = CONFIG.llm_model
    data["llm_enabled"] = CONFIG.llm_enabled
    data["llm_auto_send"] = CONFIG.llm_auto_send
    data["llm_use_cover_letter"] = CONFIG.llm_use_cover_letter
    data["llm_use_resume"] = CONFIG.llm_use_resume
    data["llm_system_prompt"] = CONFIG.llm_system_prompt
    data["llm_cover_letter_prompt"] = CONFIG.llm_cover_letter_prompt
    data["llm_profiles"] = CONFIG.llm_profiles
    data["llm_profile_mode"] = CONFIG.llm_profile_mode
    def _write():
        tmp = CONFIG_FILE.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(CONFIG_FILE)
        except Exception as e:
            log_debug(f"save_config error: {e}")
            tmp.unlink(missing_ok=True)
    threading.Thread(target=_write, daemon=True).start()


def load_config():
    """Загрузить CONFIG с диска (если файл есть)."""
    if not CONFIG_FILE.exists():
        return
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in _CONFIG_KEYS:
            if k in data:
                old_val = getattr(CONFIG, k)
                try:
                    setattr(CONFIG, k, type(old_val)(data[k]))
                except (ValueError, TypeError):
                    log_debug(f"⚠️ Невалидное значение конфига {k}={data[k]!r}, пропуск")
        if "questionnaire_templates" in data and isinstance(data["questionnaire_templates"], list):
            CONFIG.questionnaire_templates = data["questionnaire_templates"]
        if "letter_templates" in data and isinstance(data["letter_templates"], list):
            CONFIG.letter_templates = data["letter_templates"]
        if "url_pool" in data and isinstance(data["url_pool"], list):
            CONFIG.url_pool = data["url_pool"]
        for k in ("llm_api_key", "llm_base_url", "llm_model", "llm_system_prompt", "llm_cover_letter_prompt"):
            if k in data and isinstance(data[k], str):
                setattr(CONFIG, k, data[k])
        for k in ("llm_enabled", "llm_auto_send", "llm_use_cover_letter", "llm_use_resume", "llm_fill_questionnaire"):
            if k in data:
                setattr(CONFIG, k, bool(data[k]))
        if "allowed_schedules" in data and isinstance(data["allowed_schedules"], list):
            CONFIG.allowed_schedules = data["allowed_schedules"]
        if "title_blacklist" in data and isinstance(data["title_blacklist"], list):
            CONFIG.title_blacklist = data["title_blacklist"]
        if "title_whitelist" in data and isinstance(data["title_whitelist"], list):
            CONFIG.title_whitelist = data["title_whitelist"]
        if "auto_apply_tests" in data:
            CONFIG.auto_apply_tests = bool(data["auto_apply_tests"])
        if "use_oauth_apply" in data:
            CONFIG.use_oauth_apply = bool(data["use_oauth_apply"])
        if "llm_profiles" in data and isinstance(data["llm_profiles"], list):
            CONFIG.llm_profiles = data["llm_profiles"]
        if "llm_profile_mode" in data and isinstance(data["llm_profile_mode"], str):
            CONFIG.llm_profile_mode = data["llm_profile_mode"]
        # Migration: if no profiles defined but old-style api_key exists, create one profile
        if not CONFIG.llm_profiles and CONFIG.llm_api_key:
            CONFIG.llm_profiles = [{"name": "Основной", "api_key": CONFIG.llm_api_key,
                "base_url": CONFIG.llm_base_url, "model": CONFIG.llm_model, "enabled": True}]
    except Exception as e:
        log_debug(f"load_config error: {e}")


def save_accounts():
    """Сохранить accounts_data на диск (в фоновом потоке)."""
    snapshot = [
        {k: v for k, v in acc.items() if not k.startswith("_")}
        for acc in accounts_data
    ]
    def _write():
        tmp = ACCOUNTS_FILE.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            tmp.replace(ACCOUNTS_FILE)
        except Exception as e:
            log_debug(f"save_accounts error: {e}")
            tmp.unlink(missing_ok=True)
    threading.Thread(target=_write, daemon=True).start()


def load_accounts():
    """Загрузить accounts_data с диска (если файл есть)."""
    if not ACCOUNTS_FILE.exists():
        save_accounts()  # первый запуск — сохраняем текущие дефолты
        return
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            accounts_data.clear()
            accounts_data.extend(data)
    except Exception as e:
        log_debug(f"load_accounts error: {e}")
