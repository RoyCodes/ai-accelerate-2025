# workers.py (Python 3.13)
from dataclasses import dataclass, field
from typing import ClassVar, Self
import uuid, random

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
SHIFTS = ("Off", "Day", "Night")

# ----- Base model -----
@dataclass
class Worker:
    worker_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "New Worker"
    role: str = "Operator"
    level: int = 1                     # 1=Novice, 2=Intermediate, 3=Expert
    line: str = "A"
    skills: set[str] = field(default_factory=set)   # e.g. {"Mixer","Oven"}
    schedule: dict[str, str] = field(default_factory=dict)  # DAY -> "Off|Day|Night"

    # class-level “facts” for subclasses
    DEFAULT_ROLE: ClassVar[str] = "Operator"
    SKILL_POOL: ClassVar[tuple[str, ...]] = tuple()    # machine types this role can work on

    @classmethod
    def new(
        cls: type[Self],
        *,
        name: str | None = None,
        level: int | None = None,
        line: str | None = None,
    ) -> Self:
        """Create a randomized worker for this role."""
        lvl = level or random.choice((1, 2, 3))
        nm = name or _random_name()
        ln = line or random.choice(list("ABC"))

        # skills: more breadth with higher level
        pool = cls.SKILL_POOL or ("Mixer", "Kneader", "Cutter", "Oven", "Cooler", "Packer")
        k = {1: (1, 2), 2: (2, 3), 3: (3, 4)}[lvl]
        n_skills = random.randint(*k)
        skills = set(random.sample(pool, min(n_skills, len(pool))))

        sched = _random_schedule(day_bias="Day" if cls is Operator else None)

        return cls(
            name=nm,
            role=f"{cls.DEFAULT_ROLE}",
            level=lvl,
            line=ln,
            skills=skills,
            schedule=sched,
        )

    # convenience helpers you can call from the agent/planner
    def is_available(self, day: str, shift: str = "Day") -> bool:
        return self.schedule.get(day, "Off") == shift

    def availability_summary(self) -> str:
        return ", ".join(f"{d[:3]}:{self.schedule.get(d,'Off')[0]}" for d in DAYS)

# ----- Concrete roles -----
class Operator(Worker):
    DEFAULT_ROLE = "Operator"
    SKILL_POOL = ("Mixer", "Kneader", "Cutter", "Oven", "Cooler", "Packer")

class MaintenanceTech(Worker):
    DEFAULT_ROLE = "Maintenance Technician"
    SKILL_POOL = ("Mixer", "Kneader", "Cutter", "Oven", "Cooler", "Packer")

class Electrician(Worker):
    DEFAULT_ROLE = "Electrician"
    SKILL_POOL = ("Oven", "Packer", "Cooler")

class QATech(Worker):
    DEFAULT_ROLE = "QA Technician"
    SKILL_POOL = ("Cutter", "Oven", "Packer")

# ----- Registry + factory -----
REGISTRY: tuple[type[Worker], ...] = (Operator, MaintenanceTech, Electrician, QATech)

def generate_new_worker(kind: str | None = None, *, level: int | None = None, line: str | None = None, name: str | None = None) -> Worker:
    if kind:
        kind = kind.strip().lower()
        by_alias = {cls.__name__.lower(): cls for cls in REGISTRY}
        by_alias.update({
            "operator": Operator,
            "maintenancetech": MaintenanceTech, "maintenance": MaintenanceTech, "tech": MaintenanceTech,
            "electrician": Electrician, "qa": QATech, "qa_tech": QATech,
        })
        cls = by_alias.get(kind)
        if not cls:
            raise ValueError(f"Unknown worker kind: {kind!r}")
    else:
        cls = random.choice(REGISTRY)
    return cls.new(name=name, level=level, line=line)

# ----- Internals -----
_FIRST = ("Sam", "Alex", "Jordan", "Taylor", "Morgan", "Riley", "Casey", "Avery", "Jamie", "Dakota")
_LAST  = ("Lee", "Patel", "Garcia", "Nguyen", "Kim", "Davis", "Miller", "Lopez", "Hernandez", "Brown")

def _random_name() -> str:
    return f"{random.choice(_FIRST)} {random.choice(_LAST)}"

def _random_schedule(*, day_bias: str | None = None) -> dict[str, str]:
    """
    Return a simple Mon–Fri schedule like:
    {"Monday":"Day","Tuesday":"Off","Wednesday":"Day","Thursday":"Night","Friday":"Off"}
    day_bias="Day" bumps probability of Day shift.
    """
    # base probabilities for each day
    p_off, p_day, p_night = 0.25, 0.60, 0.15
    if day_bias == "Day":
        p_off, p_day, p_night = 0.20, 0.70, 0.10

    sched: dict[str, str] = {}
    workdays = 0
    for d in DAYS:
        r = random.random()
        if r < p_off:
            sched[d] = "Off"
        elif r < p_off + p_day:
            sched[d] = "Day"; workdays += 1
        else:
            sched[d] = "Night"; workdays += 1

    # ensure at least 3 workdays and at least 1 Off for demos
    if workdays < 3:
        for d in DAYS:
            if sched[d] == "Off":
                sched[d] = "Day"; workdays += 1
                if workdays >= 3: break
    if "Off" not in sched.values():
        sched[random.choice(DAYS)] = "Off"
    return sched
