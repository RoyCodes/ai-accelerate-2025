from dataclasses import dataclass, field
from typing import ClassVar
import uuid, random, time

@dataclass
class Machine:
    machine_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "New Machine"
    mtype: str = "Generic"
    line: str = "A"
    manual: str = ""
    sensors: dict[str, float] = field(default_factory=dict)
    MTYPE: ClassVar[str] = "Generic"
    DEFAULT_NAME: ClassVar[str] = "New Machine"
    DEFAULT_MANUAL: ClassVar[str] = ""
    SENSOR_DEFS: ClassVar[dict[str, tuple[float, float]]] = {}

    @classmethod
    def new(cls, *, line: str | None = None, name: str | None = None) -> "Machine":
        """Create a randomized instance from this class’s SENSOR_DEFS."""
        rngs = cls.SENSOR_DEFS
        sensors = {k: round(random.uniform(lo, hi), 3) for k, (lo, hi) in rngs.items()}
        return cls(
            name=name or cls.DEFAULT_NAME,
            mtype=cls.MTYPE,
            line=line or random.choice(list("ABC")),
            manual=cls.DEFAULT_MANUAL,
            sensors=sensors,
        )

    def snapshot(self) -> dict[str, float | int | str]:
        return {"ts": time.time(), "machine_id": self.machine_id, "type": self.mtype, "line": self.line, **self.sensors}

    def tick(self) -> None:
        """Small jitter (~1% of each sensor’s range) based on class SENSOR_DEFS."""
        for key, val in self.sensors.items():
            lo, hi = self.SENSOR_DEFS.get(key, (val - 1.0, val + 1.0))
            step = (hi - lo) * 0.01 or 0.05
            self.sensors[key] = round(val + random.uniform(-step, step), 4)

# ------------------ Concrete cookie-factory machines ------------------

class Mixer(Machine):
    MTYPE = "Mixer"
    DEFAULT_NAME = "Mixer 3000"
    DEFAULT_MANUAL = "https://example.com/mixer_manual.pdf"
    SENSOR_DEFS = {
        "temp_c": (26, 32),
        "speed_rpm": (800, 1200),
        "vibration_g": (0.02, 0.05),
        "motor_current_a": (4.0, 8.0),
        "bowl_load_kg": (50, 120),
    }

class Kneader(Machine):
    MTYPE = "Kneader"
    DEFAULT_NAME = "Kneader Pro"
    DEFAULT_MANUAL = "https://example.com/kneader_manual.pdf"
    SENSOR_DEFS = {
        "dough_temp_c": (24, 30),
        "torque_nm": (60, 120),
        "motor_current_a": (5.0, 9.0),
        "speed_rpm": (60, 150),
    }

class Cutter(Machine):
    MTYPE = "Cutter"
    DEFAULT_NAME = "CookieCutter X"
    DEFAULT_MANUAL = "https://example.com/cutter_manual.pdf"
    SENSOR_DEFS = {
        "blade_rpm": (800, 1600),
        "blade_vibration_g": (0.01, 0.03),
        "air_pressure_bar": (5.5, 7.0),
        "piece_length_mm": (48, 52),
    }

class Oven(Machine):
    MTYPE = "Oven"
    DEFAULT_NAME = "Tunnel Oven"
    DEFAULT_MANUAL = "https://example.com/oven_manual.pdf"
    SENSOR_DEFS = {
        "zone1_temp_c": (185, 200),
        "zone2_temp_c": (190, 210),
        "humidity_pct": (5, 12),
        "belt_speed_mpm": (3, 6),
    }

class Cooler(Machine):
    MTYPE = "Cooler"
    DEFAULT_NAME = "Spiral Cooler"
    DEFAULT_MANUAL = "https://example.com/cooler_manual.pdf"
    SENSOR_DEFS = {
        "air_temp_c": (18, 24),
        "airflow_cfm": (500, 800),
        "humidity_pct": (30, 50),
        "belt_speed_mpm": (3, 6),
    }

class Packer(Machine):
    MTYPE = "Packer"
    DEFAULT_NAME = "Flow Packer"
    DEFAULT_MANUAL = "https://example.com/packer_manual.pdf"
    SENSOR_DEFS = {
        "seal_temp_c": (170, 195),
        "seal_pressure_bar": (1.6, 2.4),
        "conveyor_speed_mpm": (4, 8),
        "reject_rate_pct": (0.0, 1.5),
    }

# ------------------ Helpers ------------------

REGISTRY: tuple[type[Machine], ...] = (Mixer, Kneader, Cutter, Oven, Cooler, Packer)

def generate_new_machine(kind: str | None = None, line: str | None = None, name: str | None = None) -> Machine:
    if kind:
        kind = kind.strip().lower()
        by_alias = {cls.MTYPE.lower(): cls for cls in REGISTRY}
        cls = by_alias.get(kind)
        if not cls:
            raise ValueError(f"Unknown machine kind: {kind!r}")
    else:
        cls = random.choice(REGISTRY)
    return cls.new(line=line, name=name)