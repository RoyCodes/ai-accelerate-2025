# ui/home.py
import mesop as me
import mesop.labs as mel
from dataclasses import field  # ok to keep; harmless if unused
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
        {
            "machine_id": mid,
            "name": name,
            "type": mtype,
            "ts": None,
            "power_w": None,
            "co2_kg_per_min": None,
            "scrap_rate_pct": None,
        }
        for (mid, name, mtype) in MACHINE_ORDER
    ]


@me.stateclass
class State:
    status: str = ""
    onload_done: bool = False
    rev: int = 0  # force rerender hint
    machines_json: str = json.dumps(_init_machines())
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
    s.machines_json = json.dumps(machines, separators=(",", ":"))
    s.workers_json = json.dumps(workers, separators=(",", ":"))
    s.w_loading_json = json.dumps(w_loading, separators=(",", ":"))
    s.rev += 1  # ensure re-render even if JSON happens to be identical


# ---------- Actions ----------
async def refresh_telemetry(evt: me.ClickEvent | None):
    s = me.state(State)
    s.status = "Loading latest telemetry…"
    async with httpx.AsyncClient(base_url=root_url, timeout=12) as client:
        r = await client.get("/api/machines/latest?minutes=120")
        try:
            payload = r.json()
        except Exception:
            s.status = f"Bad response from API ({r.status_code})"
            return

        items = payload.get("items", [])
        if not items:
            s.status = "No telemetry data found."
            return

        by_id = {d.get("machine_id"): d for d in items if d.get("machine_id")}
        machines, workers, w_loading = _get_lists()

        for slot in machines:
            mid = slot["machine_id"]
            d = by_id.get(mid)
            if not d:
                continue
            slot["ts"] = d.get("ts")
            slot["power_w"] = d.get("power_w")
            # handle either co2_kg_per_min or co_2_kg_per_min
            slot["co2_kg_per_min"] = d.get("co2_kg_per_min", d.get("co_2_kg_per_min"))
            slot["scrap_rate_pct"] = d.get("scrap_rate_pct")

        _set_lists(machines, workers, w_loading)
        s.status = f"Updated {len(items)} machine(s) at {time.strftime('%H:%M:%S')}"


async def gen_worker(evt: me.ClickEvent, idx: int):
    machines, workers, w_loading = _get_lists()
    if w_loading[idx]:
        return
    w_loading[idx] = True
    _set_lists(machines, workers, w_loading)
    try:
        async with httpx.AsyncClient(base_url=root_url, timeout=10) as client:
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
        me.state(State).status = f"Worker slot {idx+1} updated"


# ---- stable per-slot handlers to avoid “Unknown handler id” ----
def _make_worker_click(i: int):
    async def _handler(evt: me.ClickEvent):
        await gen_worker(evt, i)

    return _handler


WORKER_HANDLERS = [_make_worker_click(i) for i in range(WORKER_SLOTS)]

# ---------- Chat ----------
def on_load(e: me.LoadEvent):
    # Force light mode (no dark/system toggle)
    me.set_theme_mode("light")


def _chat_context_snapshot():
    machines, workers, _ = _get_lists()
    live = [m for m in machines if m.get("ts")]
    return {
        "machines": live[:6],  # keep small
        "workers": [w for w in workers if w][:8],
    }


def _history_to_messages(history: list[mel.ChatMessage] | None):
    """
    Convert Mesop chat history to a minimal [{role, content}] list
    without assuming specific attributes exist on ChatMessage.
    """
    msgs: list[dict] = []
    if not history:
        return msgs

    for m in history:
        # choose role
        role = (
            getattr(m, "role", None)
            or ("user" if getattr(m, "author", None) in ("You", "user") else "assistant")
            or "user"
        )
        # choose content
        content = (
            getattr(m, "content", None)
            or getattr(m, "text", None)
            or getattr(m, "message", None)
        )
        if content is None:
            if isinstance(m, str):
                content = m
            else:
                try:
                    content = json.dumps({k: str(v) for k, v in getattr(m, "__dict__", {}).items()})
                except Exception:
                    content = str(m)

        if content:
            msgs.append({"role": role, "content": content})

    return msgs


def transform(user_input: str, history: list[mel.ChatMessage]):
    """
    Calls FastAPI route POST /api/ai/chat with:
      { "prompt": <str>, "context": <snapshot>, "history": [ {role, content}, ... ] }

    Streaming support:
      - text/event-stream or text/plain: yield streaming lines
      - application/json: {"chunks":[...]} or {"reply": "..."}
      - fallback to raw text
    """
    payload = {
        "prompt": user_input,
        "context": _chat_context_snapshot(),
        "history": _history_to_messages(history),
    }

    try:
        with httpx.Client(base_url=root_url, timeout=60.0) as client:
            with client.stream("POST", "/api/ai/chat", json=payload) as resp:
                if resp.status_code != 200:
                    yield f"API error ({resp.status_code}): {resp.text[:300]}"
                    return

                ctype = (resp.headers.get("content-type") or "").lower()

                # Streamed text/SSE
                if "text/event-stream" in ctype or "text/plain" in ctype:
                    for raw in resp.iter_lines():
                        if not raw:
                            continue
                        # normalize to str
                        if isinstance(raw, (bytes, bytearray)):
                            line = raw.decode("utf-8", errors="ignore")
                        else:
                            line = str(raw)
                        if line.startswith("data:"):
                            line = line[5:].lstrip()
                        if line:
                            yield line
                    return

                # Non-streaming: try JSON, then raw text
                body_text = resp.text
                try:
                    data = resp.json()
                    if isinstance(data, dict):
                        chunks = data.get("chunks")
                        if isinstance(chunks, list) and all(isinstance(c, str) for c in chunks):
                            for ch in chunks:
                                yield ch
                            return
                        reply = data.get("reply")
                        if isinstance(reply, str):
                            yield reply
                            return
                    yield json.dumps(data)[:1200]
                    return
                except Exception:
                    if body_text:
                        yield body_text[:2000]
                        return
                    yield "(empty response)"
                    return

    except Exception as e:
        yield f"Request failed: {e}"


# ---------- UI (style) ----------
PRIMARY = "#1a73e8"
BG_PAGE = "#f6f8fb"
BG_CARD = "#ffffff"
TEXT_MUTED = "#6b7280"
CARD_RADIUS = 12
CARD_SHADOW = "0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.1)"
CARD_HOVER = "0 6px 20px rgba(16,24,40,.08)"
GRID_MAX_W = "1200px"
SECTION_GAP = 16

ROOT_BOX_STYLE = me.Style(
    background=BG_PAGE,
    height="100%",
    font_family="Inter",
    display="flex",
    flex_direction="column",
)

# ---- Icon mapping (Material Symbols) ----
ICON_COLORS = {
    "mixer": "#7c3aed",
    "kneader": "#2563eb",
    "cutter": "#0ea5e9",
    "oven": "#f97316",
    "cooler": "#06b6d4",
    "packer": "#16a34a",
    "worker": "#1f2937",
    "qa": "#ef4444",
    "electric": "#f59e0b",
    "maint": "#22c55e",
}


def machine_icon(mtype: str) -> tuple[str, str]:
    m = (mtype or "").lower()
    if "mixer" in m:
        return ("blender", ICON_COLORS["mixer"])
    if "kneader" in m:
        return ("handyman", ICON_COLORS["kneader"])
    if "cutter" in m:
        return ("content_cut", ICON_COLORS["cutter"])
    if "oven" in m:
        return ("local_fire_department", ICON_COLORS["oven"])
    if "cooler" in m:
        return ("ac_unit", ICON_COLORS["cooler"])
    if "packer" in m:
        return ("inventory_2", ICON_COLORS["packer"])
    return ("factory", "#475569")


def worker_icon(role: str) -> tuple[str, str]:
    r = (role or "").lower()
    if "qa" in r:
        return ("rule", ICON_COLORS["qa"])
    if "electric" in r:
        return ("electrical_services", ICON_COLORS["electric"])
    if "maint" in r or "maintenance" in r:
        return ("build", ICON_COLORS["maint"])
    return ("person", ICON_COLORS["worker"])


def header():
    with me.box(
        style=me.Style(
            background=BG_CARD,
            padding=me.Padding.all(20),
            border_radius=CARD_RADIUS,
            box_shadow=CARD_SHADOW,
            margin=me.Margin.symmetric(horizontal="auto", vertical=16),
            width=f"min({GRID_MAX_W}, 100%)",
            display="flex",
            align_items="center",
            justify_content="space-between",
            gap=12,
        )
    ):
        with me.box():
            me.text("Cookie Factory Copilot", style=me.Style(font_size=22, font_weight=700))
            me.text("Live telemetry • Human-in-the-loop planning", style=me.Style(color=TEXT_MUTED))
        me.button("Refresh telemetry", color="primary", on_click=refresh_telemetry)


def section(title: str):
    return me.box(
        style=me.Style(
            background=BG_CARD,
            padding=me.Padding.all(16),
            border_radius=CARD_RADIUS,
            box_shadow=CARD_SHADOW,
            width="100%",
        )
    )


def responsive_grid():
    return me.box(
        style=me.Style(
            margin=me.Margin.symmetric(horizontal="auto", vertical=8),
            width=f"min({GRID_MAX_W}, 100%)",
            display="grid",
            grid_template_columns="repeat(12, 1fr)",
            gap=SECTION_GAP,
        )
    )


def pill(label: str, bg: str = "#f0f4ff", fg: str = PRIMARY):
    me.text(
        label,
        style=me.Style(
            display="inline-block",
            padding=me.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=999,
            background=bg,
            color=fg,
            font_family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
            font_size=12,
        ),
    )


def skeleton_line(width="70%"):
    me.box(
        style=me.Style(
            height="12px",
            width=width,
            border_radius=6,
            background="#edf2f7",
            margin=me.Margin.symmetric(vertical=6),
        )
    )


CARD_H = 168


def machine_card(data: dict):
    with me.box(style=me.Style(transition="box-shadow .15s ease")):
        with me.card(
            appearance="raised",
            style=me.Style(
                min_width=250,
                max_width=360,
                background=BG_CARD,
                border_radius=CARD_RADIUS,
                box_shadow="none",
                height=f"{CARD_H}px",
                display="flex",
                flex_direction="column",
            ),
        ):
            title = f"{data.get('name','Unknown')}"
            mtype = f"{data.get('type','')}"
            ident = data.get("machine_id", "?")
            me.card_header(title=title, subtitle=f"{mtype} • {ident}")

            with me.card_content():
                with me.box(style=me.Style(display="flex", gap=12, align_items="flex-start")):
                    icon_name, icon_color = machine_icon(mtype)
                    me.icon(icon=icon_name, style=me.Style(font_size=28, color=icon_color))
                    with me.box(style=me.Style(display="flex", flex_direction="column", gap=6)):
                        if data.get("ts") is None:
                            skeleton_line("60%")
                            skeleton_line("80%")
                            skeleton_line("50%")
                        else:
                            pill(f"Power {round(data.get('power_w') or 0, 1)} W")
                            co2_val = data.get("co2_kg_per_min")
                            pill(f"CO₂ {co2_val:.6f} kg/min" if isinstance(co2_val, (int, float)) else "CO₂ —")
                            scrap = (data.get("scrap_rate_pct") or 0)
                            scrap_bg = "#fee2e2" if scrap >= 1.0 else "#f0f4ff"
                            scrap_fg = "#b91c1c" if scrap >= 1.0 else PRIMARY
                            pill(f"Scrap {scrap:.2f}%", bg=scrap_bg, fg=scrap_fg)
                ts = data.get("ts")
                me.text(
                    f"ts: {ts if ts else 'waiting for latest…'}",
                    style=me.Style(color=TEXT_MUTED, font_size=12),
                )


WORKER_CARD_H = 156


def worker_card(data, idx: int):
    with me.box(style=me.Style(transition="box-shadow .15s ease")):
        with me.card(
            appearance="raised",
            style=me.Style(
                min_width=250,
                max_width=360,
                background=BG_CARD,
                border_radius=CARD_RADIUS,
                box_shadow="none",
                height=f"{WORKER_CARD_H}px",
                display="flex",
                flex_direction="column",
            ),
        ):
            if not data:
                me.card_header(title="Unassigned", subtitle="Click to generate")
                with me.card_content():
                    with me.box(style=me.Style(display="flex", gap=12, align_items="center")):
                        me.box(
                            style=me.Style(
                                width="36px", height="36px", border_radius="50%", background="#eef2ff"
                            )
                        )
                        with me.box(style=me.Style(flex="1")):
                            skeleton_line("50%")
                            skeleton_line("70%")
                    me.button("Generate", color="primary", on_click=WORKER_HANDLERS[idx])
            else:
                name = data.get("name", "Worker")
                role = data.get("role", "Worker")
                lvl = data.get("level", 1)
                me.card_header(title=name, subtitle=f"{role} • L{lvl}")
                with me.card_content():
                    with me.box(style=me.Style(display="flex", gap=12, align_items="center")):
                        icon_name, icon_color = worker_icon(role)
                        me.icon(icon=icon_name, style=me.Style(font_size=28, color=icon_color))
                        sched = data.get("schedule") or {}
                        days_full = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                        summary = ", ".join(f"{d[:3]}:{(sched.get(d, 'Off') or 'Off')[0]}" for d in days_full)
                        me.text(summary, style=me.Style(color=TEXT_MUTED))


@me.page(
    path="/",
    title="Cookie Factory Copilot",
    on_load=on_load,
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap",
        # Material Symbols
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:FILL@0..1,GRAD@0..200,wght@100..700,opsz@24",
    ],
)
def page():
    s = me.state(State)

    header()

    machines, workers, w_loading = _get_lists()

    with responsive_grid():
        # Machines (span 7/12)
        with me.box(style=me.Style(grid_column="span 7")):
            with section("Machines"):
                me.text("Machines", style=me.Style(font_weight=700, font_size=18))
                with me.box(
                    style=me.Style(
                        display="grid",
                        grid_template_columns="repeat(auto-fill, minmax(250px, 1fr))",
                        gap=12,
                    )
                ):
                    for m in machines:
                        machine_card(m)

        # Workers (span 5/12)
        with me.box(style=me.Style(grid_column="span 5")):
            with section("Workers"):
                me.text("Workers", style=me.Style(font_weight=700, font_size=18))
                with me.box(
                    style=me.Style(
                        display="grid",
                        grid_template_columns="repeat(auto-fill, minmax(250px, 1fr))",
                        gap=12,
                    )
                ):
                    for i in range(len(workers)):
                        worker_card(workers[i], i)

        # Chat (span full width)
        with me.box(style=me.Style(grid_column="1 / -1")):
            with section("Chat"):
                me.text("Factory Copilot", style=me.Style(font_weight=700, font_size=18))
                mel.chat(transform, bot_user="AI Assistant")

    if s.status:
        with me.box(
            style=me.Style(
                margin=me.Margin.symmetric(horizontal="auto", vertical=8),
                width=f"min({GRID_MAX_W}, 100%)",
            )
        ):
            me.text(s.status, style=me.Style(color=TEXT_MUTED, font_size=12))
