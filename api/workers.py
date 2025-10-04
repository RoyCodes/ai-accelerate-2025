class Worker:
    uuid: str
    name: str = "New Worker"
    role: str = "Novice Operator"
    assigned_machine: str = "None"
    schedule: dict[str, str] = {"Monday": "Off", "Tuesday": "Day", "Wednesday": "Night", "Thursday": "Day", "Friday": "Off"}    