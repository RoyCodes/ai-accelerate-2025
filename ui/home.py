import mesop as me
from dataclasses import field
import httpx
from typing import List

SLOTS = 5
root_url = "http://localhost:8000"  # swap to your deployed base later

@me.stateclass
class State:
    button_label: str = "Generate"
    in_progress: bool = False
    # store plain dicts; no Unions/Any/object
    machines: List[dict] = field(default_factory=lambda: [{} for _ in range(SLOTS)])
    workers:  List[dict] = field(default_factory=lambda: [{} for _ in range(SLOTS)])
    m_loading: List[bool] = field(default_factory=lambda: [False] * SLOTS)
    w_loading: List[bool] = field(default_factory=lambda: [False] * SLOTS)
    status: str = ""

# ---- Actions ----

async def on_generate_button_click(event: me.ClickEvent):
    s = me.state(State)
    if s.in_progress:
        return
    s.in_progress = True
    s.button_label = "Generating…"
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{root_url}/api/generate/start")
        s.button_label = r.text
    s.in_progress = False

async def gen_machine(evt: me.ClickEvent, idx: int):
    s = me.state(State)
    if s.m_loading[idx]:
        return
    s.m_loading[idx] = True
    async with httpx.AsyncClient(base_url=root_url, timeout=8) as client:
        r = await client.post("/api/machines/generate")
        s.machines[idx] = r.json()
    s.m_loading[idx] = False

async def gen_worker(evt: me.ClickEvent, idx: int):
    s = me.state(State)
    if s.w_loading[idx]:
        return
    s.w_loading[idx] = True
    async with httpx.AsyncClient(base_url=root_url, timeout=8) as client:
        r = await client.post("/api/workers/generate")
        s.workers[idx] = r.json()
    s.w_loading[idx] = False

# ---- UI ----

ROOT_BOX_STYLE = me.Style(
    background="#e7f2ff",
    height="100%",
    font_family="Inter",
    display="flex",
    flex_direction="column",
)

def header():
    with me.box(style=me.Style(padding=me.Padding.all(16))):
        me.text("Hello, World!")

def button():
    s = me.state(State)
    me.button(label=s.button_label, color="primary", type="flat", on_click=on_generate_button_click)

def make_machine_click(idx: int):
    async def _handler(evt: me.ClickEvent):
        await gen_machine(evt, idx)
    return _handler

def make_worker_click(idx: int):
    async def _handler(evt: me.ClickEvent):
        await gen_worker(evt, idx)
    return _handler

def _sensor_preview(sensors: dict):
    return [f"{k}: {v}" for k, v in list(sensors.items())[:5]]

def machine_card(data, idx: int):
    s = me.state(State)
    with me.card(appearance="raised", style=me.Style(min_width=220, background="#f3f4f6")):
        if not data:
            label = "Generating…" if s.m_loading[idx] else "Generate"
            me.button(label, color="primary", type="flat", on_click=make_machine_click(idx))
        else:
            me.card_header(title=data["name"], subtitle=data["mtype"])
            with me.card_content():
                me.icon(icon="factory")
                for line in _sensor_preview(data.get("sensors", {})):
                    me.text(line)

def worker_card(data, idx: int):
    s = me.state(State)
    with me.card(appearance="raised", style=me.Style(min_width=220, background="#f3f4f6")):
        if not data:
            label = "Generating…" if s.w_loading[idx] else "Generate"
            me.button(label, color="primary", type="flat", on_click=make_worker_click(idx))
        else:
            role = data.get("role", "Worker")
            lvl = data.get("level", 1)
            me.card_header(title=data["name"], subtitle=f"{role} • L{lvl}")
            with me.card_content():
                me.icon(icon="person")
                sched = data.get("schedule", {})
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                me.text(", ".join(f"{d[:3]}:{sched.get(d, 'Off')[0]}" for d in days))

@me.page(
    path="/",
    stylesheets=["https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap"],
)
def page():
    s = me.state(State)
    with me.box(style=ROOT_BOX_STYLE):

        # Header Section
        with me.box(style=me.Style(
            background="#fff",
            padding=me.Padding.all(16),
            border_radius=12,
            margin=me.Margin.symmetric(horizontal="auto", vertical=12),
            width="min(900px, 100%)",
        )):header()

        # Machines Section
        with me.box(style=me.Style(
            background="#fff",
            padding=me.Padding.all(16),
            border_radius=12,
            margin=me.Margin.symmetric(horizontal="auto", vertical=12),
            width="min(900px, 100%)",
        )):
            me.text("Machines", style=me.Style(font_weight=700, font_size=18))
            with me.box(style=me.Style(display="flex", flex_direction="row", flex_wrap="wrap", gap=12)):
                for i in range(SLOTS):
                    machine_card(s.machines[i], i)

        # Workers Section
        with me.box(style=me.Style(
            background="#fff",
            padding=me.Padding.all(16),
            border_radius=12,
            margin=me.Margin.symmetric(horizontal="auto", vertical=12),
            width="min(900px, 100%)",
        )):
            me.text("Workers", style=me.Style(font_weight=700, font_size=18))
            with me.box(style=me.Style(display="flex", flex_direction="row", flex_wrap="wrap", gap=12)):
                for i in range(SLOTS):
                    worker_card(s.workers[i], i)
        
        # Telemetry Section
        with me.box(style=me.Style(
            background="#fff",
            padding=me.Padding.all(16),
            border_radius=12,
            margin=me.Margin.symmetric(horizontal="auto", vertical=12),
            width="min(900px, 100%)",
        )):button()