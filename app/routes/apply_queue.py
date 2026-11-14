"""API очереди откликов «бот готовит — владелец жмёт» (app/apply_queue.py). Им пользуется @ninjiu_bot."""
from fastapi import APIRouter, Request

from app import apply_queue
from app.storage import add_applied

router = APIRouter()


@router.get("/api/apply_queue")
async def queue_list(status: str = ""):
    if status and status not in apply_queue.STATUSES:
        return {"ok": False, "error": f"status: {'|'.join(apply_queue.STATUSES)}"}
    items = apply_queue.items(status)
    return {"ok": True, "items": items, "count": len(items)}


async def _close(request: Request, status: str) -> dict:
    body = await request.json()
    iid = str(body.get("id", ""))
    was_open = apply_queue.get(iid).get("status") == "open"
    item = apply_queue.close(iid, status)
    if not item:
        return {"ok": False, "error": "нет такой записи"}
    if status == "done" and was_open:
        add_applied(item["account"], item["vacancy_id"], {
            "title": item["title"], "company": item["company"], "campaign_id": item.get("campaign_id"),
            **{k: v for k, v in (item.get("meta") or {}).items() if v}})
    return {"ok": True, "item": item}


@router.post("/api/apply_queue/done")
async def queue_done(request: Request):
    """Владелец откликнулся на hh сам: вакансия уходит в отклики."""
    return await _close(request, "done")


@router.post("/api/apply_queue/skip")
async def queue_skip(request: Request):
    return await _close(request, "skipped")
