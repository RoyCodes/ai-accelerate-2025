# ui/home.py (JSON-in-state variant)
import mesop as me
from dataclasses import field
import json, httpx

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
    machines_json: str = json.dumps(_init_machines())
    workers_json: str = json.dumps([None for _ in range(WORKER_SLOTS)])
    w_loading_json: str = json.dumps([False] * WORKER_SLOTS)

def _get_lists():
    s = me.state(State)
    return json.loads(s.machines_json), json.loads(s.workers_json), json.loads(s.w_loading_json)

def _set_lists(machines, workers, w_loading):
    s = me.state(State)
    s.machines_json = json.dumps(machines)
    s.workers_json = json.dumps(workers)
    s.w_loading_json = json.dumps(w_loading)

async def refresh_telemetry(evt: me.ClickEvent | None):
    s = me.state(State)
    s.status = "Loading latest telemetry…"

    async with httpx.AsyncClient(base_url=root_url, timeout=10) as client:
        # Fetch telemetry from the API
        r = await client.get("/api/machines/latest?minutes=10")
        payload = r.json()

        # If there are no items, update status and return early
        if not payload.get("items"):
            s.status = "No telemetry data found."
            return

        data = payload.get("items", [])
        by_id = {d["machine_id"]: d for d in data}

        # Update machines state with the new data
        machines = json.loads(s.machines_json)  # Get current state
        for slot in machines:
            mid = slot["machine_id"]
            if mid in by_id:
                d = by_id[mid]
                # Hydrate the machine slot with fresh telemetry
                slot["ts"] = d.get("ts")
                slot["power_w"] = d.get("power_w")
                slot["co2_kg_per_min"] = d.get("co2_kg_per_min")
                slot["scrap_rate_pct"] = d.get("scrap_rate_pct")

        # Persist updated machines state back into Mesop state
        s.machines_json = json.dumps(machines)

    s.status = f"Updated {len(data)} machine(s)"

async def gen_worker(evt, idx):
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

ROOT_BOX_STYLE = me.Style(background="#e7f2ff", height="100%", font_family="Inter", display="flex", flex_direction="column")

def header():
    with me.box(style=me.Style(padding=me.Padding.all(16))):
        me.text("Cookie Factory Copilot", style=me.Style(font_size=20, font_weight=700))
        me.button("Refresh telemetry", color="primary", on_click=refresh_telemetry)

def machine_card(data):
    with me.card(appearance="raised", style=me.Style(min_width=240, background="#f7f7f7")):
        me.card_header(title=f"{data['name']} ({data['machine_id']})", subtitle=data["type"])
        with me.card_content():
            me.icon(icon="factory")
            me.text(f"ts: {data.get('ts') or '—'}")
            me.text(f"power_w: {data.get('power_w') if data.get('power_w') is not None else '—'}")
            me.text(f"co2_kg_per_min: {data.get('co2_kg_per_min') if data.get('co2_kg_per_min') is not None else '—'}")
            me.text(f"scrap_rate_pct: {data.get('scrap_rate_pct') if data.get('scrap_rate_pct') is not None else '—'}")

def make_worker_click(idx):
    async def _handler(evt):
        await gen_worker(evt, idx)
    return _handler

def worker_card(data, idx):
    with me.card(appearance="raised", style=me.Style(min_width=220, background="#f7f7f7")):
        if not data:
            me.button("Generate", color="primary", type="flat", on_click=make_worker_click(idx))
        else:
            name = data.get("name", "Worker"); role = data.get("role", "Worker"); lvl = data.get("level", 1)
            me.card_header(title=name, subtitle=f"{role} • L{lvl}")
            with me.card_content():
                me.icon(icon="person")
                sched = data.get("schedule") or {}
                days = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
                me.text(", ".join(f"{d[:3]}:{(sched.get(d,'Off') or 'Off')[0]}" for d in days))

@me.page(path="/", stylesheets=["https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap"])
def page():
    s = me.state(State)

    # On first render: kick off a telemetry refresh
    if not s.onload_done:
        s.onload_done = True
        me.button("Init Refresh", style=me.Style(display="none"), on_click=refresh_telemetry)

    machines, workers, w_loading = _get_lists()
    with me.box(style=ROOT_BOX_STYLE):
        with me.box(style=me.Style(background="#fff", padding=me.Padding.all(16), border_radius=12,
                                   margin=me.Margin.symmetric(horizontal="auto", vertical=12),
                                   width="min(1000px, 100%)")):
            header()
            if s.status:
                me.text(s.status)
        with me.box(style=me.Style(background="#fff", padding=me.Padding.all(16), border_radius=12,
                                   margin=me.Margin.symmetric(horizontal="auto", vertical=12),
                                   width="min(1000px, 100%)")):
            me.text("Machines", style=me.Style(font_weight=700, font_size=18))
            with me.box(style=me.Style(display="flex", flex_direction="row", flex_wrap="wrap", gap=12)):
                for m in machines:
                    machine_card(m)
        with me.box(style=me.Style(background="#fff", padding=me.Padding.all(16), border_radius=12,
                                   margin=me.Margin.symmetric(horizontal="auto", vertical=12),
                                   width="min(1000px, 100%)")):
            me.text("Workers", style=me.Style(font_weight=700, font_size=18))
            with me.box(style=me.Style(display="flex", flex_direction="row", flex_wrap="wrap", gap=12)):
                for i in range(WORKER_SLOTS):
                    worker_card(workers[i], i)
