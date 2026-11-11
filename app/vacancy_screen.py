"""Проверка текста вакансии перед откликом (решения владельца 11.11.2026).

1. Только полная удалёнка: даже с фильтром «удалённо» в тексте бывает «с возможностью при
   необходимости приезжать в офис», «гибрид», «2 дня в офисе» — такие пропускаем.
2. Указания для ИИ/ботов/агентов в тексте («если вы ИИ, напишите слово…», «ignore previous
   instructions») не выполняем: вакансию не откликаем, а отдаём владельцу на проверку.

screen(text) → {"office": фрагмент или "", "agent": фрагмент или ""}.
Решения запоминаются в data/screened_vacancies.json, чтобы не проверять и не уведомлять повторно.
"""
import json
import re
import threading
from pathlib import Path

STORE = Path("data") / "screened_vacancies.json"
_lock = threading.Lock()

_OFFICE = [
    r"приезжа\w*\s+в\s+офис", r"выезд\w*\s+в\s+офис", r"посещ\w*\s+офис", r"присутств\w*\s+в\s+офисе",
    r"работ\w*\s+(из|в)\s+офис\w*", r"бывать\s+в\s+офисе", r"появля\w*\s+в\s+офисе",
    r"\d+\s*(раз|дн\w*)\s+в\s+(неделю|месяц)\s+в\s+офис\w*", r"в\s+офис\w*\s+\d+\s*(раз|дн\w*)",
    r"\d+\s*(раз|дн\w*)\s+в\s+(неделю|месяц)\s+в\s+офисе",
    r"(come|commute)\s+to\s+the\s+office", r"office\s+\d+\s*days?",
]
# «по желанию», «на выбор», «на твоё усмотрение» — офис не обязателен
_OPTIONAL = re.compile(r"(по\s+желани|при\s+желани|на\s+(твой|ваш)\s+выбор|на\s+выбор|на\s+(твоё|твое|ваше)?\s*усмотрени|"
                       r"по\s+(твоему|вашему)\s+выбору|if\s+you\s+(want|wish|like)|or\s+choose|optional)", re.I)
# «без необходимости приезжать в офис», «не нужно бывать в офисе» — это удалёнка
_NEGATION = re.compile(r"(без|не\s+нужно|не\s+требуется|нет\s+необходимости|не\s+обязательно|никаких)\W+(\w+\W+){0,3}$")

_AI = r"(ии|ai|нейросет\w*|нейронк\w*|бот\w*|gpt|chatgpt|llm|ии[\s-]?агент\w*|ai[\s-]?агент\w*|языков\w*\s+модел\w*|language\s+model\w*|ассистент\w*)"
_AGENT = [
    rf"если\s+(вы|ты)\s+(\w+\s+){{0,2}}{_AI}\b",
    rf"(вниманию|attention|note\s+to|message\s+to|instructions?\s+for|дорог\w+|уважаем\w+)\W+(\w+\W+){{0,2}}{_AI}\b",
    rf"if\s+you\s+are\s+(an?\s+)?(\w+\s+)?{_AI}\b",
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", r"игнорир\w*\s+(все\s+)?(предыдущ|прошл)\w*\s+инструкц",
    r"(кодов|секретн|контрольн|проверочн)\w*\s+слов\w*",
    r"(напиш\w*|укаж\w*|добав\w*|вставь\w*)\s+(в\s+)?(начал\w*|перв\w*\s+строк\w*|конц\w*|тем\w*)\s+(письма|сообщени\w*|отклика)",
    r"(напиш\w*|укаж\w*|добав\w*)\s+(в\s+)?(сопроводительн\w*\s+)?(письм\w*|отклик\w*)\s+(слово|фраз\w*)",
]
_OFFICE_RE = [re.compile(p, re.I) for p in _OFFICE]
_AGENT_RE = [re.compile(p, re.I) for p in _AGENT]


def _snippet(text: str, m: re.Match) -> str:
    a, b = max(0, m.start() - 60), min(len(text), m.end() + 60)
    return re.sub(r"\s+", " ", text[a:b]).strip()


def screen(text: str) -> dict:
    text = text or ""
    res = {"office": "", "agent": ""}
    for rx in _AGENT_RE:
        m = rx.search(text)
        if m:
            res["agent"] = _snippet(text, m)
            break
    for rx in _OFFICE_RE:
        for m in rx.finditer(text):
            if _NEGATION.search(text[max(0, m.start() - 40):m.start()].lower()):
                continue
            if _OPTIONAL.search(text[max(0, m.start() - 80):m.end() + 80]):
                continue
            res["office"] = _snippet(text, m)
            break
        if res["office"]:
            break
    return res


def _load() -> dict:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def known(vid: str) -> dict:
    """Прошлое решение по вакансии: {"reason": "office"|"agent", ...} или {}."""
    with _lock:
        return _load().get(str(vid), {})


def remember(vid: str, reason: str, snippet: str, title: str = "", company: str = "") -> None:
    with _lock:
        d = _load()
        d[str(vid)] = {"reason": reason, "snippet": snippet[:300], "title": title, "company": company}
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
