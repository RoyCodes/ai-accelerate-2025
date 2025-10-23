# ui/home.py
import mesop as me
import mesop.labs as mel
from dataclasses import field
import json, httpx, time

root_url = "http://localhost:8000"

MACHINE_ORDER = [
    ("mx-01", "Mixer 3000", "Mixer"),
    ("kn-02", "Kneader Pro", "Kneader"),
    ("ct-03", "CookieCutter X", "Cutter"),
    ("ov-04", "Tunnel Oven", "Oven"),
    ("cl-05", "Spiral Cooler", "Cooler"),
    ("pk-06", "Flow Packer", "Packer"),
]
WORKER_SLOTS = 5

def _init_machines():
    return [
        {"machine_id": mid, "name": name, "type": mtype,
         "ts": None, "power_w": None, "co2_kg_per_min": None, "scrap_rate_pct": None}
        for (mid, name, mtype) in MACHINE_ORDER
    ]

@me.stateclass
class State:
    status: str = ""
    onload_done: bool = False
    rev: int = 0  # << force rerender hint
    machines_json: str = json.dumps(_init_machines())
    # use {} instead of None to avoid first-click weirdness
    workers_json: str = json.dumps([{} for _ in range(WORKER_SLOTS)])
    w_loading_json: str = json.dumps([False] * WORKER_SLOTS)

def _get_lists():
    s = me.state(State)
    return (
        json.loads(s.machines_json),
        json.loads(s.workers_json),
        json.loads(s.w_loading_json),
    )

def _set_lists(machines, workers, w_loading):
    s = me.state(State)
    # compact JSON (slight perf gain)
    s.machines_json = json.dumps(machines, separators=(",", ":"))
    s.workers_json = json.dumps(workers, separators=(",", ":"))
    s.w_loading_json = json.dumps(w_loading, separators=(",", ":"))
    s.rev += 1  # << ensure re-render even if strings happen to be identical

# ---------- Actions ----------
async def refresh_telemetry(evt: me.ClickEvent | None):
    s = me.state(State)
    s.status = "Loading latest telemetry…"
    async with httpx.AsyncClient(base_url=root_url, timeout=10) as client:
        r = await client.get("/api/machines/latest?minutes=10")
        payload = r.json()
        items = payload.get("items", [])
        if not items:
            s.status = "No telemetry data found."
            return

        by_id = {d["machine_id"]: d for d in items}
        machines, workers, w_loading = _get_lists()

        for slot in machines:
            mid = slot["machine_id"]
            if mid in by_id:
                d = by_id[mid]
                slot["ts"] = d.get("ts")
                slot["power_w"] = d.get("power_w")
                slot["co2_kg_per_min"] = d.get("co2_kg_per_min")
                slot["scrap_rate_pct"] = d.get("scrap_rate_pct")

        _set_lists(machines, workers, w_loading)
        s.status = f"Updated {len(items)} machine(s)"

async def gen_worker(evt, idx: int):
    machines, workers, w_loading = _get_lists()
    if w_loading[idx]:
        return
    w_loading[idx] = True
    _set_lists(machines, workers, w_loading)
    try:
        async with httpx.AsyncClient(base_url=root_url, timeout=8) as client:
            r = await client.post("/api/workers/generate")
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, list):
                payload = payload[0] if payload else {}
            if not isinstance(payload, dict):
                payload = {}
            workers[idx] = payload
    finally:
        w_loading[idx] = False
        _set_lists(machines, workers, w_loading)

# ---------- Chat ----------
def on_load(e: me.LoadEvent):
    me.set_theme_mode("system")

def transform(user_input: str, history: list[mel.ChatMessage]):
    s = me.state(State)
    machines, workers, _ = _get_lists()
    live = [m for m in machines if m.get("ts")]
    if not live:
        yield "I don’t see recent telemetry yet. Tap **Refresh telemetry** first.\n"
        return

    max_pow = max((m.get("power_w") or 0) for m in live)
    hottest = max(live, key=lambda m: (m.get("scrap_rate_pct") or 0))
    yield "Okay, looking at the latest line data… "
    time.sleep(0.1)
    yield f"Peak power is about **{max_pow:.1f} W**. "
    time.sleep(0.1)
    yield f"Highest scrap right now: **{hottest['name']}** at **{(hottest.get('scrap_rate_pct') or 0):.2f}%**. "
    time.sleep(0.1)
    available = [w for w in workers if w]
    yield f"I see **{len(available)}** generated workers. Ask me to propose a maintenance slot and I’ll include a suggested assignee.\n"

# ---------- UI ----------
ROOT_BOX_STYLE = me.Style(
    background="#e7f2ff",
    height="100%",
    font_family="Inter",
    display="flex",
    flex_direction="column",
)

def header():
    with me.box(style=me.Style(padding=me.Padding.all(16))):
        me.text("Cookie Factory Copilot", style=me.Style(font_size=20, font_weight=700))
        me.button("Refresh telemetry", color="primary", on_click=refresh_telemetry)

def machine_card(data: dict):
    with me.card(appearance="raised", style=me.Style(min_width=240, background="#f7f7f7")):
        me.card_header(title=f"{data.get('name','Unknown')} ({data.get('machine_id','?')})", subtitle=data.get("type",""))
        with me.card_content():
            me.icon(icon="factory")
            me.text(f"ts: {data.get('ts') or '—'}")
            pw = data.get("power_w")
            co2 = data.get("co2_kg_per_min")
            scrap = data.get("scrap_rate_pct")
            me.text(f"power_w: {pw if pw is not None else '—'}")
            me.text(f"co2_kg_per_min: {co2 if co2 is not None else '—'}")
            me.text(f"scrap_rate_pct: {scrap if scrap is not None else '—'}")

def make_worker_click(idx: int):
    async def _handler(evt):
        await gen_worker(evt, idx)
    return _handler

def worker_card(data, idx: int):
    with me.card(appearance="raised", style=me.Style(min_width=220, background="#f7f7f7")):
        if not data:
            me.button("Generate", color="primary", type="flat", on_click=make_worker_click(idx))
        else:
            name = data.get("name", "Worker")
            role = data.get("role", "Worker")
            lvl = data.get("level", 1)
            me.card_header(title=name, subtitle=f"{role} • L{lvl}")
            with me.card_content():
                me.icon(icon="person")
                sched = data.get("schedule") or {}
                days = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
                me.text(", ".join(f"{d[:3]}:{(sched.get(d,'Off') or 'Off')[0]}" for d in days))

@me.page(
    path="/",
    title="Cookie Factory Copilot",
    on_load=on_load,
    stylesheets=["https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap"],
)
def page():
    s = me.state(State)
    if not s.onload_done:
        s.onload_done = True
        # user still clicks "Refresh telemetry", but on-load state is now sound
    machines, workers, _ = _get_lists()

    with me.box(style=ROOT_BOX_STYLE):
        # Header
        with me.box(style=me.Style(
            background="#fff", padding=me.Padding.all(16), border_radius=12,
            margin=me.Margin.symmetric(horizontal="auto", vertical=12),
            width="min(1100px, 100%)",
        )):
            header()
            if s.status:
                me.text(s.status)

        # Top: Machines | Workers
        with me.box(style=me.Style(
            display="flex", flex_direction="row", flex_wrap="wrap", gap=12,
            margin=me.Margin.symmetric(horizontal="auto"),
            width="min(1100px, 100%)",
        )):
            with me.box(style=me.Style(background="#fff", padding=me.Padding.all(16), border_radius=12,
                                       flex="1 1 520px", min_width="520px")):
                me.text("Machines", style=me.Style(font_weight=700, font_size=18))
                with me.box(style=me.Style(display="flex", flex_direction="row", flex_wrap="wrap", gap=12)):
                    for m in machines:
                        machine_card(m)
            with me.box(style=me.Style(background="#fff", padding=me.Padding.all(16), border_radius=12,
                                       flex="1 1 520px", min_width="520px")):
                me.text("Workers", style=me.Style(font_weight=700, font_size=18))
                with me.box(style=me.Style(display="flex", flex_direction="row", flex_wrap="wrap", gap=12)):
                    for i in range(WORKER_SLOTS):
                        worker_card(workers[i], i)

        # Bottom: chat
        with me.box(style=me.Style(
            background="#fff", padding=me.Padding.all(16), border_radius=12,
            margin=me.Margin.symmetric(horizontal="auto", vertical=12),
            width="min(1100px, 100%)",
        )):
            mel.chat(transform, title="Factory Copilot", bot_user="Copilot")
