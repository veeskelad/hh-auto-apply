"""Сухой прогон: письмо и ответы на анкету под реальные вакансии, без отправки отклика.

    python scripts/dry_run.py --tests 5            первые 5 вакансий из data/test_required_vacancies.json
    python scripts/dry_run.py --vacancy 123,456    конкретные вакансии

Запускать из корня проекта (нужны data/ и .env). К hh.ru идут только GET: страница вакансии
и форма анкеты. Итог — data/dry_run_<время>.md: вопросы, ответы нейросети, письмо.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONUTF8", "1")


def _load_env() -> None:
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", type=int, default=0, help="взять N вакансий из test_required_vacancies.json")
    ap.add_argument("--vacancy", default="", help="id вакансий через запятую")
    ap.add_argument("--session", type=int, default=0, help="номер браузерной сессии в browser_sessions.json")
    ap.add_argument("--no-letter", action="store_true", help="не генерировать письмо")
    a = ap.parse_args()

    _load_env()
    from app.hh_transport import install
    install()
    import requests
    from app.config import CONFIG, load_config
    load_config()
    from app.hh_apply import fetch_vacancy_description
    from app.hh_resume import fetch_all_resume_texts
    from app.llm import generate_cover_letter, generate_llm_questionnaire_answers, profile_facts
    from app.questionnaire import _parse_questionnaire_rich, answer_text

    sessions = json.loads(Path("data/browser_sessions.json").read_text(encoding="utf-8"))
    acc = sessions[a.session]
    vids = [v.strip() for v in a.vacancy.split(",") if v.strip()]
    if a.tests:
        tests = json.loads(Path("data/test_required_vacancies.json").read_text(encoding="utf-8"))
        vids += list(tests.keys())[: a.tests]
    if not vids:
        print("✗ нет вакансий: укажи --tests N или --vacancy id")
        return 2

    print(f"факты о кандидате: {len(profile_facts())} симв.; LLM-профили: "
          f"{[p.get('name') for p in CONFIG.llm_profiles or [] if p.get('enabled')]}")
    resume = fetch_all_resume_texts(acc)
    print(f"резюме с hh: {len(resume)} симв.")

    out = [f"# Сухой прогон {datetime.now():%d.%m.%Y %H:%M}", ""]
    for vid in vids:
        url = f"https://hh.ru/applicant/vacancy_response?vacancyId={vid}&withoutTest=no"
        r = requests.get(url, cookies=acc.get("cookies", {}), timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Referer": f"https://hh.ru/vacancy/{vid}"})
        vd = fetch_vacancy_description(vid, acc.get("cookies", {}))
        title, company = vd.get("title", ""), vd.get("company", "")
        out += [f"## {title or vid} — {company}", f"https://hh.ru/vacancy/{vid}", ""]
        rich = _parse_questionnaire_rich(r.text) if r.status_code == 200 else []
        print(f"{vid}: форма HTTP {r.status_code}, вопросов {len(rich)}, «{title[:50]}»")
        if r.status_code != 200:
            out += [f"Форма анкеты: HTTP {r.status_code}", ""]
        elif not rich:
            out += ["Анкеты нет (или вакансия закрыта / уже откликались).", ""]
        else:
            ans = generate_llm_questionnaire_answers(rich, title, company, resume_text=resume)
            for q in rich:
                val = ans.get(q["field"], "")
                labels = {o["value"]: o["label"] for o in q.get("options") or []}
                shown = answer_text(q, ans) or "— нет ответа —"
                if q.get("options") and val and val not in labels:
                    shown += "  ⚠️ значения нет среди вариантов"
                out += [f"**В:** {q['text']}", f"**О:** {shown}", ""]
        if not a.no_letter:
            letter = generate_cover_letter(title, vd.get("description", ""), company, resume)
            out += ["**Письмо:**", "", letter or "— не сгенерировано —", ""]
    dst = Path("data") / f"dry_run_{datetime.now():%Y%m%d_%H%M}.md"
    dst.write_text("\n".join(out), encoding="utf-8")
    print(f"✓ {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
