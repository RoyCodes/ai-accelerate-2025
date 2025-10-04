import mesop as me
from dataclasses import field
import httpx

# Page State:

SLOTS = 5

@me.stateclass
class State:
   button_label: str = "Generate"
   in_progress: bool = False
   machines: list = field(default_factory=lambda: [None] * SLOTS)   # OK
   workers: list = field(default_factory=lambda: [None] * SLOTS)    # OK
   m_loading: list = field(default_factory=lambda: [False] * SLOTS) # OK
   w_loading: list = field(default_factory=lambda: [False] * SLOTS) # OK
   status: str = ""

# Page Functions:

root_url = "http://localhost:8000"
# root_url = "https://placeholder.com"

#generate telemetry
async def on_generate_button_click(event: me.ClickEvent):
   state = me.state(State)
   if state.in_progress:
      return
   state.in_progress = True
   state.button_label = "Generating..."

   async with httpx.AsyncClient() as client:
    # call fastapi

    response = await client.post(f"{root_url}/api/generate/start")
    state.button_label = response.text
    state.in_progress = False

async def gen_machine(evt: me.ClickEvent, idx: int):
    s = me.state(State)
    s.m_loading[idx] = True
    try:
        async with httpx.AsyncClient(base_url=root_url, timeout=8) as client:
            r = await client.post("/api/machines/generate")
            r.raise_for_status()
            s.machines[idx] = r.json()
    except Exception as e:
        s.status = f"Machine {idx+1}: {e}"
    finally:
        s.m_loading[idx] = False

async def gen_worker(evt: me.ClickEvent, idx: int):
    s = me.state(State)
    s.w_loading[idx] = True
    try:
        async with httpx.AsyncClient(base_url=root_url, timeout=8) as client:
            r = await client.post("/api/workers/generate")
            r.raise_for_status()
            s.workers[idx] = r.json()
    except Exception as e:
        s.status = f"Worker {idx+1}: {e}"
    finally:
        s.w_loading[idx] = False

# Page Rendering:

# Global Style:
ROOT_BOX_STYLE = me.Style(
    background="#e7f2ff",
    height="100%",
    font_family="Inter",
    display="flex",
    flex_direction="column",
)

# Page Components:
def header():
   with me.box(
      style=me.Style(
         padding=me.Padding.all(16),
      ),
   ):
    me.text("Hello, World!")

def button():
   state = me.state(State)
   me.button(
      label=state.button_label, 
      color="primary", 
      type="flat",
      on_click=on_generate_button_click,
      )

def _sensor_preview(sensors: dict) -> list[str]:
    return [f"{k}: {v}" for k, v in list(sensors.items())[:5]]
   
def machine_card(data: dict | None, idx: int):
    s = me.state(State)
    with me.card(appearance="raised", style=me.Style(min_width=220, background="#f3f4f6")):
        if data is None:
            label = "Generating…" if s.m_loading[idx] else "Generate"
            me.button(label, color="primary", type="flat", on_click=lambda e, i=idx: gen_machine(e, i))
        else:
            me.card_header(title=f"{data['name']}", subtitle=f"{data['mtype']}")
            with me.card_content():
                me.icon(icon="factory")  # Material Symbols name
                for line in _sensor_preview(data.get("sensors", {})):
                    me.text(line)

def worker_card(data: dict | None, idx: int):
    s = me.state(State)
    with me.card(appearance="raised", style=me.Style(min_width=220, background="#f3f4f6")):
        if data is None:
            label = "Generating…" if s.w_loading[idx] else "Generate"
            me.button(label, color="primary", type="flat", on_click=lambda e, i=idx: gen_worker(e, i))
        else:
            role = data.get("role", "Worker")
            lvl = data.get("level", 1)
            me.card_header(title=data["name"], subtitle=f"{role} • L{lvl}")
            with me.card_content():
                me.icon(icon="person")
                sched = data.get("schedule", {})
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                me.text(", ".join(f"{d[:3]}:{sched.get(d, 'Off')[0]}" for d in days))

# Page Path and Tree:
@me.page(
    path="/",
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap"
    ],
)
def page():
    s = me.state(State)
    with me.box(style=ROOT_BOX_STYLE):
        header()
        with me.box(style=me.Style(
            background="grey",
            width="min(800px, 100%)",
            margin=me.Margin.symmetric(
                horizontal="auto",
                vertical=36,
                ),
            padding=me.Padding.all(16)
        )):
            me.text("Hello from ai-accelerate-2025!")
            button()
            with me.box(
               style=me.Style(
                  display="flex",
                  flex_direction="row",
                  gap=16,
                  margin=me.Margin.all(15),
                  max_width=500
               )
            ):
                with me.card(appearance='raised'):
                    me.card_header(
                        title="Machines",
                        subtitle="Current machines on site.",
                )
                    me.icon("FactoryRounded")

        # Machines section
        with me.box(style=me.Style(
            background="#fff",
            padding=me.Padding.all(16),
            border_radius=12,
            margin=me.Margin.symmetric(horizontal="auto", vertical=12),
            width="min(900px, 100%)",
        )):
            me.text("Machines", style=me.Style(font_weight=700, font_size=18))
            # row of cards → flex row, wrapping
            with me.box(style=me.Style(display="flex", flex_direction="row", flex_wrap="wrap", gap=12)):
                for i in range(SLOTS):
                    machine_card(s.machines[i], i)

        # Workers section
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