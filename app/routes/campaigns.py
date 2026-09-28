"""
Кампании автооткликов — библиотека сохранённых конфигов (несколько на аккаунт).
Активна одна на аккаунт (запуск = загрузить параметры в сессию + armed).
"""

import asyncio

from fastapi import APIRouter, Request

from app.instances import bot
from app.storage import (
    list_campaigns, get_campaign, upsert_campaign, delete_campaign,
    get_applied_list, set_campaign_stats, count_applied_by_campaign,
    CAMPAIGN_PARAM_KEYS,
)
from app.hh_negotiations import fetch_negotiation_status_map

router = APIRouter()


def _live_state_for_campaign(camp: dict):
    """Найти живое AccountState, на котором сейчас активна эта кампания (или None)."""
    cid = camp.get("id")
    states = list(bot.account_states) + list(bot.temp_states.values())
    for st in states:
        if getattr(st, "active_campaign_id", None) == cid:
            return st
    return None


def _merge_live(camp: dict, sent_by_cid: dict) -> dict:
    """Собрать актуальные счётчики кампании.
    sent — из persistent applied (по campaign_id): переживает рестарт и растёт live,
    т.к. воркер при отправке пишет add_applied с campaign_id.
    skipped/errors — эфемерные (per-run): берём из live-состояния, если кампания идёт."""
    camp = dict(camp)
    stats = dict(camp.get("stats") or {})
    stats["sent"] = sent_by_cid.get(camp.get("id"), 0)
    st = _live_state_for_campaign(camp)
    if st and st.armed:
        camp["status"] = "running"
        stats["skipped"] = st.campaign_skipped
        stats["errors"] = st.campaign_errors
        stats["skip_reasons"] = dict(st.campaign_skip_reasons)
    camp["stats"] = stats
    return camp


@router.get("/api/campaigns")
async def api_campaigns_list():
    if getattr(bot, "_migrate_campaigns_pending", False):
        bot._migrate_campaigns_pending = False
        bot.migrate_campaigns_from_sessions()
        bot.reconcile_campaign_statuses()  # сбросить зависшие 'running' после рестарта
        bot.backfill_applied_campaign_ids()  # привязать историю откликов к кампаниям
    sent_by_cid = count_applied_by_campaign()
    camps = [_merge_live(c, sent_by_cid) for c in list_campaigns()]
    total_apps = sum((c.get("stats") or {}).get("sent", 0) for c in camps)
    active = sum(1 for c in camps if c.get("status") == "running")
    return {"campaigns": camps, "total": len(camps), "active": active, "total_responses": total_apps}


@router.post("/api/campaigns")
async def api_campaigns_create(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "bad json"}
    camp = {"name": (body.get("name") or body.get("search_query") or "Без названия").strip()}
    for k in CAMPAIGN_PARAM_KEYS:
        if k in body:
            camp[k] = body[k]
    # привязать к аккаунту по session_key
    acc_idx = body.get("account_idx")
    if acc_idx is not None:
        camp["session_key"] = bot.session_key_for_idx(int(acc_idx))
    elif body.get("session_key"):
        camp["session_key"] = body["session_key"]
    saved = upsert_campaign(camp)
    return {"ok": True, "campaign": saved}


@router.post("/api/campaigns/{cid}")
async def api_campaigns_update(cid: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "bad json"}
    camp = get_campaign(cid)
    if not camp:
        return {"ok": False, "error": "Кампания не найдена"}
    upd = {"id": cid}
    if "name" in body:
        upd["name"] = str(body["name"]).strip() or camp.get("name", "")
    for k in CAMPAIGN_PARAM_KEYS:
        if k in body:
            upd[k] = body[k]
    saved = upsert_campaign(upd)
    return {"ok": True, "campaign": saved}


@router.delete("/api/campaigns/{cid}")
async def api_campaigns_delete(cid: str):
    camp = get_campaign(cid)
    if camp:
        idx = bot.idx_for_session_key(camp.get("session_key"))
        if idx is not None:
            st = bot._resolve_state(idx)
            if st and getattr(st, "active_campaign_id", None) == cid and st.armed:
                bot.disarm_campaign(idx)
    delete_campaign(cid)
    return {"ok": True}


@router.post("/api/campaigns/{cid}/start")
async def api_campaigns_start(cid: str, request: Request):
    camp = get_campaign(cid)
    if not camp:
        return {"ok": False, "error": "Кампания не найдена"}
    idx = bot.idx_for_session_key(camp.get("session_key"))
    if idx is None:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if body.get("account_idx") is not None:
            idx = int(body["account_idx"])
    if idx is None:
        return {"ok": False, "error": "Не найдена сессия аккаунта для кампании"}
    return bot.start_campaign(idx, cid)


@router.post("/api/campaigns/{cid}/stop")
async def api_campaigns_stop(cid: str):
    camp = get_campaign(cid)
    if not camp:
        return {"ok": False, "error": "Кампания не найдена"}
    idx = bot.idx_for_session_key(camp.get("session_key"))
    res = {"ok": True, "armed": False}
    if idx is not None:
        res = bot.disarm_campaign(idx)
    # Статус пишем НАПРЯМУЮ по cid: после рестарта runtime active_campaign_id
    # теряется, и disarm_campaign не смог бы обновить библиотеку. Здесь cid известен.
    set_campaign_stats(cid, status="stopped")
    res["ok"] = True
    return res


@router.get("/api/campaigns/{cid}/applications")
async def api_campaigns_applications(cid: str):
    """Отклики кампании (по campaign_id; fallback по имени аккаунта) + статус HH."""
    camp = get_campaign(cid)
    if not camp:
        return {"applications": [], "error": "Кампания не найдена"}
    idx = bot.idx_for_session_key(camp.get("session_key"))
    acc = bot._get_apply_acc(idx) if idx is not None else None
    name = acc.get("name", "") if acc else ""
    all_apps = get_applied_list(5000)
    apps = [a for a in all_apps if a.get("campaign_id") == cid]
    if not apps and name:
        # историческая совместимость: старые отклики без campaign_id — по аккаунту
        apps = [a for a in all_apps if a.get("account") == name and not a.get("campaign_id")]
    smap = {}
    if acc:
        try:
            smap = await asyncio.get_event_loop().run_in_executor(
                None, fetch_negotiation_status_map, acc)
        except Exception:
            smap = {}
    for a in apps:
        a["hh_status"] = smap.get(str(a.get("vacancy_id")), "Отправлен")
    return {"applications": apps, "total": len(apps)}
