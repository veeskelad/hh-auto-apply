"""
LLM integration: generate replies, questionnaire answers, text randomization.
"""

import os
import re
import json
import random
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from app.logging_utils import log_debug
from app.config import CONFIG, DATA_DIR

# Файлы владельца в data/ (в .gitignore): факты о кандидате и правила ответов в чатах
PROFILE_FACTS_FILE = DATA_DIR / "profile_facts.md"
CHAT_PLAYBOOK_FILE = DATA_DIR / "chat_playbook.md"
_file_cache: dict = {}


def _read_cached(path: Path) -> str:
    """Текст файла без HTML-комментариев; перечитывается, когда меняется mtime."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return ""
    hit = _file_cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    text = re.sub(r"<!--[\s\S]*?-->", "", path.read_text(encoding="utf-8")).strip()
    _file_cache[path] = (mtime, text)
    return text


def profile_facts() -> str:
    return _read_cached(PROFILE_FACTS_FILE)


def chat_playbook() -> str:
    return _read_cached(CHAT_PLAYBOOK_FILE)


def _facts_block() -> str:
    facts = profile_facts()
    if not facts:
        return ""
    return ("\n\n---\nФакты о кандидате (главный источник; важнее резюме при расхождении; "
            "чего здесь и в резюме нет, того не придумывай):\n" + facts + "\n---")

try:
    import openai as _openai_mod
    _openai_available = True
except ImportError:
    _openai_available = False

_llm_rr_index = 0  # round-robin counter for multi-profile LLM
_llm_rr_lock = threading.Lock()


def _resolve_key(raw: str) -> str:
    """Разрешить ключ: 'env:VAR' -> os.environ[VAR], иначе значение как есть.
    Позволяет хранить в config.json ссылку, а сам секрет — в .env."""
    if isinstance(raw, str) and raw.startswith("env:"):
        return os.environ.get(raw[4:], "")
    return raw or ""


class _SubscriptionCLI:
    """OpenAI-подобный клиент поверх CLI с подпиской вместо API-ключа:
    `claude -p` (Claude Code) или `codex exec` (Codex, вход через ChatGPT).
    Инструменты, MCP и пользовательские настройки выключены: в промпт попадают
    сообщения работодателей, и модель не должна иметь возможности что-то выполнить."""

    def __init__(self, kind: str, model: str):
        from types import SimpleNamespace
        self._ns = SimpleNamespace
        self.kind = kind
        self.model = model or ("sonnet" if kind == "claude" else "")
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    @staticmethod
    def _split(messages):
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [m for m in messages if m["role"] != "system"]
        prompt = rest[0]["content"] if len(rest) == 1 else "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in rest)
        return system, prompt

    def _claude(self, system, prompt, model, cwd):
        exe = shutil.which("claude") or "/opt/homebrew/bin/claude"
        cmd = [exe, "-p", "--tools", "", "--strict-mcp-config", "--setting-sources", "",
               "--no-session-persistence", "--output-format", "text", "--model", model]
        # .cmd-обёртка Windows режет командную строку на 8191 символе и портит переводы строк:
        # тогда системный промпт уходит в stdin
        if system and (exe.lower().endswith((".cmd", ".bat")) or len(system) > 20000):
            prompt = f"<instructions>\n{system}\n</instructions>\n\n{prompt}"
            system = "Выполни задачу по инструкциям из блока <instructions> в начале сообщения."
        if system:
            cmd += ["--system-prompt", system]
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                           timeout=180, cwd=cwd)
        if r.returncode != 0 or not r.stdout.strip():
            raise RuntimeError(f"claude -p exit {r.returncode}: {r.stderr.strip()[:300]}")
        return r.stdout.strip()

    def _codex(self, system, prompt, model, cwd):
        exe = shutil.which("codex") or "/opt/homebrew/bin/codex"
        out = Path(cwd) / "out.txt"
        cmd = [exe, "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules",
               "-s", "read-only", "--color", "never", "-c", "web_search=disabled", "-o", str(out)]
        for feature in ("shell_tool", "unified_exec", "apps", "plugins", "browser_use", "computer_use",
                        "in_app_browser", "multi_agent", "image_generation", "hooks"):
            cmd += ["--disable", feature]
        if system:
            ins = Path(cwd) / "instructions.md"
            ins.write_text(system, encoding="utf-8")
            cmd += ["-c", f"model_instructions_file='{ins.as_posix()}'"]
        if model:
            cmd += ["-m", model]
        cmd.append("-")
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                           timeout=240, cwd=cwd)
        text = out.read_text(encoding="utf-8").strip() if out.exists() else ""
        if r.returncode != 0 or not text:
            raise RuntimeError(f"codex exec exit {r.returncode}: {r.stderr.strip()[-300:]}")
        return text

    def _create(self, model=None, messages=(), **_):
        system, prompt = self._split(messages)
        run = self._claude if self.kind == "claude" else self._codex
        with tempfile.TemporaryDirectory() as cwd:
            text = run(system, prompt, model or self.model, cwd)
        msg = self._ns(content=text)
        return self._ns(choices=[self._ns(message=msg)])


_CLI_KINDS = {"claude-cli": "claude", "codex-cli": "codex"}


def _no_dash(text: str) -> str:
    """Длинное и среднее тире выдают машинный текст: в письмах и ответах их быть не должно."""
    return (text or "").replace("—", "-").replace("–", "-").strip()


def _client_for(profile: dict):
    if profile.get("base_url") in _CLI_KINDS:
        return _SubscriptionCLI(_CLI_KINDS[profile["base_url"]], profile.get("model"))
    return _openai_mod.OpenAI(api_key=_resolve_key(profile["api_key"]), base_url=profile.get("base_url") or None)


def _randomize_text(template: str) -> str:
    """Replace {opt1|opt2|opt3} with random choice from alternatives."""
    def pick(m):
        options = [o.strip() for o in m.group(1).split('|')]
        return random.choice(options)
    return re.sub(r'\{([^}]+\|[^}]+)\}', pick, template)


def generate_llm_reply(conversation: list, employer_name: str = "", cover_letter: str = "", resume_text: str = "") -> str:
    """Generate a reply to employer using configured LLM (OpenAI-compatible API)."""
    global _llm_rr_index
    if not _openai_available:
        log_debug("generate_llm_reply: openai package not installed")
        return ""

    # Build profiles list: use multi-profile config if available, else fall back to legacy fields
    profiles = [p for p in (CONFIG.llm_profiles or []) if p.get("enabled", True) and p.get("api_key")]
    if not profiles:
        # Legacy fallback: use old single-key config
        if not CONFIG.llm_api_key:
            return ""
        profiles = [{"api_key": CONFIG.llm_api_key, "base_url": CONFIG.llm_base_url,
                     "model": CONFIG.llm_model}]

    # Build messages list (shared across profile attempts)
    system = CONFIG.llm_system_prompt
    system += (
        "\n\nВАЖНО: если последнее сообщение работодателя — формальная вежливость "
        "или уведомление без вопроса и без просьбы к соискателю (например «рассмотрим "
        "ваше резюме, если подойдёт — свяжемся», «спасибо за отклик», «ваш отклик "
        "получен»), отвечать НЕ нужно. В этом случае верни РОВНО строку [NO_REPLY] "
        "без каких-либо других слов."
    )
    if resume_text and resume_text.strip():
        system += (
            f"\n\n---\nРезюме соискателя (используй для персонализации ответов):\n"
            f"{resume_text.strip()}\n---"
        )
    if cover_letter and cover_letter.strip():
        system += (
            f"\n\nКонтекст: к отклику на вакансию работодателя «{employer_name}» "
            f"было приложено сопроводительное письмо:\n\"\"\"\n{cover_letter.strip()}\n\"\"\"\n"
            "Учитывай содержание письма при ответе и не противоречь ему."
        )
    messages = [{"role": "system", "content": system}]
    for msg in conversation[-8:]:
        role = "user" if msg["sender"] == "employer" else "assistant"
        messages.append({"role": role, "content": msg["text"]})

    mode = CONFIG.llm_profile_mode

    if mode == "roundrobin":
        # Pick one profile by round-robin, try only that one
        with _llm_rr_lock:
            idx = _llm_rr_index % len(profiles)
            _llm_rr_index += 1
        profile = profiles[idx]
        pname = profile.get("name") or profile.get("model") or f"профиль {idx}"
        model = profile.get("model") or "gpt-4o-mini"
        log_debug(f"generate_llm_reply: roundrobin → {pname} ({model}), {len(messages)-1} сообщений")
        try:
            client = _client_for(profile)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )
            result = _no_dash(resp.choices[0].message.content)
            log_debug(f"generate_llm_reply: {pname} → {len(result)} симв.")
            return result
        except Exception as e:
            log_debug(f"generate_llm_reply roundrobin {pname} error: {e}")
            return ""
    else:
        # Fallback mode: try each profile in order, return first successful result
        for i, profile in enumerate(profiles):
            pname = profile.get("name") or profile.get("model") or f"профиль {i}"
            model = profile.get("model") or "gpt-4o-mini"
            log_debug(f"generate_llm_reply: fallback {i+1}/{len(profiles)} → {pname} ({model}), {len(messages)-1} сообщений")
            try:
                client = _client_for(profile)
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=300,
                    temperature=0.7,
                )
                result = _no_dash(resp.choices[0].message.content)
                log_debug(f"generate_llm_reply: {pname} → {len(result)} симв.")
                return result
            except Exception as e:
                log_debug(f"generate_llm_reply fallback {pname} error: {e}")
                continue
        log_debug("generate_llm_reply: все профили вернули ошибку")
        return ""


# Категории плейбука: в каких бот отвечает сам, а в каких только готовит черновик владельцу
CHAT_AUTO_CATEGORIES = {"thanks", "salary_format", "contacts", "test_task", "interview_invite"}  # experience — черновиком: 11.11 бот сам ответил «Да, Kafka»
CHAT_CATEGORIES = CHAT_AUTO_CATEGORIES | {"experience", "offer", "negotiation", "rejection", "unknown", "no_reply"}
CHAT_AUTO_MIN_CONFIDENCE = 0.7


def generate_llm_reply_plan(conversation: list, employer_name: str = "", cover_letter: str = "",
                            resume_text: str = "") -> dict:
    """Ответ работодателю по плейбуку data/chat_playbook.md.

    Возвращает {category, confidence, reply, variants, reason, auto}; auto=True — категория
    из CHAT_AUTO_CATEGORIES и модель уверена, ответ можно отправить без владельца.
    Пустой dict — сбой всех профилей.
    """
    playbook = chat_playbook()
    system = CONFIG.llm_system_prompt
    if playbook:
        system += "\n\n---\nПлейбук ответов работодателям (следуй ему):\n" + playbook + "\n---"
    if resume_text and resume_text.strip():
        system += "\n\n---\nРезюме кандидата:\n" + resume_text.strip()[:6000] + "\n---"
    system += _facts_block()
    if cover_letter and cover_letter.strip():
        system += (f"\n\nК отклику на вакансию работодателя «{employer_name}» было приложено письмо:\n"
                   f"\"\"\"\n{cover_letter.strip()}\n\"\"\"\nНе противоречь ему.")
    system += (
        "\n\nВерни ТОЛЬКО JSON без markdown:\n"
        '{"category": "<одна из: ' + ", ".join(sorted(CHAT_CATEGORIES)) + '>", '
        '"confidence": <0..1, насколько ты уверен в категории и в том, что ответ верен по фактам>, '
        '"reply": "<лучший ответ от первого лица; пусто, если category=no_reply>", '
        '"variants": ["<другой вариант ответа>", "<ещё вариант>"], '
        '"reason": "<коротко: почему такая категория>"}'
    )
    convo = []
    for msg in conversation[-8:]:
        who = "Работодатель" if msg.get("sender") == "employer" else "Кандидат"
        convo.append(f"{who}: {msg.get('text', '')}")
    user = "Переписка (последнее сообщение внизу):\n" + "\n".join(convo)
    raw = _llm_chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                    max_tokens=900, temperature=0.6, label="generate_llm_reply_plan")
    if not raw:
        return {}
    m = re.search(r"\{[\s\S]*\}", raw)
    plan = {}
    if m:
        try:
            plan = json.loads(m.group())
        except Exception:
            plan = {}
    if not plan:
        # Модель вернула просто текст: черновик владельцу, без автоотправки
        no_reply = "[NO_REPLY]" in raw.upper()
        return {"category": "no_reply" if no_reply else "unknown", "confidence": 0.0,
                "reply": "" if no_reply else raw, "variants": [], "reason": "ответ не в JSON", "auto": False}
    cat = str(plan.get("category", "unknown")).strip().lower()
    if cat not in CHAT_CATEGORIES:
        cat = "unknown"
    try:
        conf = float(plan.get("confidence", 0))
    except (TypeError, ValueError):
        conf = 0.0
    reply = _no_dash(str(plan.get("reply") or ""))
    variants = [_no_dash(str(v)) for v in (plan.get("variants") or []) if str(v).strip()][:3]
    return {"category": cat, "confidence": conf, "reply": reply, "variants": variants,
            "reason": str(plan.get("reason") or "")[:300],
            "auto": cat in CHAT_AUTO_CATEGORIES and conf >= CHAT_AUTO_MIN_CONFIDENCE and bool(reply)}


def _llm_chat(messages: list, max_tokens: int = 300, temperature: float = 0.7, label: str = "llm") -> str:
    """Прогнать messages через сконфигурированные LLM-профили (fallback по порядку). Возвращает текст или ''."""
    if not _openai_available:
        return ""
    profiles = [p for p in (CONFIG.llm_profiles or []) if p.get("enabled", True) and p.get("api_key")]
    if not profiles:
        if not CONFIG.llm_api_key:
            return ""
        profiles = [{"api_key": CONFIG.llm_api_key, "base_url": CONFIG.llm_base_url, "model": CONFIG.llm_model}]
    for i, profile in enumerate(profiles):
        pname = profile.get("name") or profile.get("model") or f"профиль {i}"
        model = profile.get("model") or "gpt-4o-mini"
        try:
            client = _client_for(profile)
            resp = client.chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, temperature=temperature,
            )
            result = _no_dash(resp.choices[0].message.content)
            log_debug(f"{label}: {pname} → {len(result)} симв.")
            return result
        except Exception as e:
            log_debug(f"{label} {pname} error: {e}")
            continue
    log_debug(f"{label}: все профили вернули ошибку")
    return ""


def generate_cover_letter(vacancy_title: str, vacancy_description: str, company: str,
                          resume_texts: str = "", system_prompt: str = "") -> str:
    """
    Сгенерировать сопроводительное письмо под конкретную вакансию, опираясь на резюме
    (одно или оба). Возвращает текст письма или '' при сбое (вызывающий код делает fallback на шаблон).
    """
    base = system_prompt or CONFIG.llm_cover_letter_prompt or CONFIG.llm_system_prompt
    system = base
    if resume_texts and resume_texts.strip():
        system += (
            f"\n\n---\nРезюме соискателя (опирайся на факты отсюда, не выдумывай):\n"
            f"{resume_texts.strip()}\n---"
        )
    system += _facts_block()
    user = f"Должность: {vacancy_title or '—'}\nКомпания: {company or '—'}\n"
    if vacancy_description and vacancy_description.strip():
        user += f"\nОписание вакансии:\n{vacancy_description.strip()[:3000]}\n"
    user += "\nНапиши сопроводительное письмо по правилам выше. Выведи только текст письма."
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return _llm_chat(messages, max_tokens=700, temperature=0.9, label="generate_cover_letter")


def generate_llm_questionnaire_answers(rich_questions: list, vacancy_title: str = "", company: str = "",
                                       resume_text: str = "") -> dict:
    """Заполняет ответы на опросник работодателя через LLM.
    rich_questions — список из _parse_questionnaire_rich().
    resume_text — опционально текст резюме для контекста.
    Возвращает {field: value} или {} при ошибке.
    """
    if not _openai_available or not rich_questions:
        return {}
    profiles = [p for p in (CONFIG.llm_profiles or []) if p.get("enabled", True) and p.get("api_key")]
    if not profiles:
        if not CONFIG.llm_api_key:
            return {}
        profiles = [{"api_key": CONFIG.llm_api_key, "base_url": CONFIG.llm_base_url, "model": CONFIG.llm_model}]

    lines = ["Заполни анкету работодателя для отклика на вакансию."]
    if vacancy_title:
        lines.append(f"Вакансия: {vacancy_title}")
    if company:
        lines.append(f"Компания: {company}")
    lines += ["", "Вопросы:"]
    for i, q in enumerate(rich_questions, 1):
        qtext = q.get("text", "")
        qtype = q.get("type", "textarea")
        if qtype == "textarea":
            lines.append(f'{i}. [текст] {qtext}')
        elif qtype == "radio":
            opts = " / ".join(f'"{o["label"]}" (value={o["value"]})' for o in q.get("options", []))
            own = (f' Свой вариант: value=open, а текст в поле "{q["text_field"]}".'
                   if q.get("text_field") else "")
            lines.append(f'{i}. [выбор одного: {opts}]{own} {qtext}')
        elif qtype == "checkbox":
            opts = " / ".join(f'"{o["label"]}" (value={o["value"]})' for o in q.get("options", []))
            lines.append(f'{i}. [чекбокс: {opts}] {qtext}')
        elif qtype == "select":
            opts = " / ".join(f'"{o["label"]}" (value={o["value"]})' for o in q.get("options", []))
            lines.append(f'{i}. [выпадающий список: {opts}] {qtext}')
    lines += [
        "",
        "Заполни анкету от первого лица по правилам из системного сообщения.",
        "Для текста — 1–5 предложений, на вопрос на знания можно подробнее.",
        "Для radio/checkbox/select — верни точное value из скобок (цифру или код).",
        "Где есть «Свой вариант»: если ни один готовый вариант не точен для кандидата "
        "(например, опыт смешанный), выбери open и напиши ответ в поле *_text; "
        "иначе поле *_text оставь пустой строкой.",
        "",
        "Верни ТОЛЬКО JSON без пояснений:",
        "{"
    ]
    for q in rich_questions:
        lines.append(f'  "{q["field"]}": "...",')
        if q.get("text_field"):
            lines.append(f'  "{q["text_field"]}": "",')
    lines.append("}")

    system = (
        "Ты заполняешь анкету работодателя от лица кандидата, от первого лица. Правила:\n"
        "1. Вопрос об опыте, навыках, проектах — отвечай по фактам о кандидате и резюме, "
        "с конкретикой (технологии, масштаб, результат). Ничего не выдумывай: ни лет опыта, "
        "ни компаний, ни цифр.\n"
        "2. Прямого опыта нет — честно скажи, что не работал с этим, и назови ближайший "
        "смежный опыт из фактов.\n"
        "3. Вопрос на знания (что делает команда, чем отличается A от B, как бы ты решил "
        "задачу) — отвечай как опытный инженер: по существу, правильно, 2–5 предложений.\n"
        "4. Зарплата, формат, город, релокация, выход на работу, английский — строго по фактам.\n"
        "4а. Формальные вопросы (оформление по ТК РФ, ИП или самозанятость, гражданство, допуск, "
        "судимость, военный билет, аккредитация) — только если ответ прямо есть в фактах. Нет факта: "
        "в тексте напиши, что уточнишь на звонке; в вариантах выбери «Свой вариант» с таким текстом, "
        "а если его нет — верни для этого поля пустую строку. Не угадывай.\n"
        "5. Варианты ответа — выбирай тот, что правдив для кандидата; не завышай уровень.\n"
        "6. Без канцелярита, штампов и длинных тире.\n"
        "Возвращай ТОЛЬКО валидный JSON, без markdown и пояснений."
    )
    if resume_text:
        system += f"\n\nРезюме кандидата с hh:\n{resume_text[:6000]}"
    system += _facts_block()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(lines)}]

    for i, profile in enumerate(profiles):
        pname = profile.get("name") or f"профиль {i}"
        model = profile.get("model") or "gpt-4o-mini"
        log_debug(f"generate_llm_questionnaire_answers: {pname} ({model}), {len(rich_questions)} вопросов")
        try:
            client = _client_for(profile)
            resp = client.chat.completions.create(
                model=model, messages=messages, max_tokens=2000, temperature=0.3,
            )
            raw = _no_dash(resp.choices[0].message.content)
            log_debug(f"generate_llm_questionnaire_answers raw: {raw[:300]}")
            # Извлекаем JSON — ищем {} блок
            json_m = re.search(r'\{[\s\S]*\}', raw)
            if json_m:
                answers = json.loads(json_m.group())
                return {k: str(v) for k, v in answers.items() if v is not None}
        except Exception as e:
            log_debug(f"generate_llm_questionnaire_answers {pname} error: {e}")
            if i < len(profiles) - 1:
                continue
    return {}
