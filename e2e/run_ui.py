"""UI e2e: поднимает два изолированных стенда и прогоняет e2e/ui.e2e.mjs в ego-browser.

    python e2e/run_ui.py            скриншоты в e2e/screenshots/
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand import PORT, Stand  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "screenshots"


def close_stale_spaces() -> None:
    """Закрыть пространства ego, оставшиеся от прерванного прогона."""
    js = ('const s = await listTaskSpaces();'
          'for (const x of s.filter((x) => x.name === "hh-auto-apply e2e" && x.ownership === "agent"))'
          ' await (await taskSpace(x.id)).finish({ keep: [] });')
    subprocess.run(["ego-browser", "nodejs", "-e", js], stdin=subprocess.DEVNULL, capture_output=True, timeout=60)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    with Stand() as full, Stand(empty=True, port=PORT + 1) as empty:
        params = {"E2E_BASE": full.base, "E2E_EMPTY_BASE": empty.base, "E2E_OUT": str(OUT)}
        script = f"globalThis.__E2E = {json.dumps(params)};\n" + (HERE / "ui.e2e.mjs").read_text(encoding="utf-8")
        close_stale_spaces()
        if sys.platform == "darwin":
            # Chromium не рисует перекрытое окно: клики и скриншоты в нём зависают
            subprocess.run(["open", "-a", "ego lite"], check=False)
        try:
            r = subprocess.run(["ego-browser", "nodejs"], input=script, capture_output=True, text=True,
                               encoding="utf-8", timeout=300)
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            steps = [l for l in (out + "\n" + err).splitlines() if "E2E_STEP " in l]
            print("✗ ego-browser завис на шаге:", steps[-1].split("E2E_STEP ", 1)[1] if steps else "до первого шага")
            close_stale_spaces()
            return 2
        line = next((l[l.index("E2E_RESULTS "):] for l in (r.stdout + "\n" + r.stderr).splitlines() if "E2E_RESULTS " in l), None)
        if not line:
            print(r.stdout[-2000:], r.stderr[-2000:], sep="\n")
            return 2
        results = json.loads(line[len("E2E_RESULTS "):])
        missed = [l.split(" ", 1)[1] for l in (r.stdout + "\n" + r.stderr).splitlines() if l.startswith("E2E_MISSED_SCREENSHOTS ")]
        outside = [b for b in full.blocked() + empty.blocked() if "hh.ru" not in b]
    for res in results:
        print(("✓ " if res["ok"] else "✗ ") + res["name"] + ("" if res["ok"] else f"\n    {res['error']}"))
    if outside:
        print("✗ стенд пытался выйти наружу:", outside[:5])
    failed = sum(not r["ok"] for r in results) + bool(outside)
    if missed:
        print("! не снялись скриншоты (на результат не влияет):", missed[0])
    print(f"\n{len(results) - failed} из {len(results)} прошли; скриншоты: {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
