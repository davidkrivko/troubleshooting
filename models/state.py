import datetime
from dataclasses import dataclass, field


@dataclass
class BoilerState:
    serial_num: str
    boiler_id: int
    boiler_name: str
    owner_first_name: str
    is_statistic: bool
    is_learning: bool

    heating_delta: int | None = None

    relay: int = 0
    current_temp: int = 0
    last_seen: datetime.datetime = None

    heat_start_time: datetime.datetime = None
    heat_start_temp: int = None

    learning_active: bool = False

    alerts_sent: set = field(default_factory=set)
