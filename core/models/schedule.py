from dataclasses import dataclass
from datetime import time

WEEKDAY_NAME_TO_INDEX = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
WEEKDAY_INDEX_TO_NAME = {index: name.capitalize() for name, index in WEEKDAY_NAME_TO_INDEX.items()}


@dataclass(frozen=True)
class Schedule:
    weekday: int
    send_time: time

    @staticmethod
    def from_strings(weekday_name: str, time_str: str) -> "Schedule":
        weekday_index = WEEKDAY_NAME_TO_INDEX[weekday_name.strip().lower()]
        hour, minute = (int(part) for part in time_str.strip().split(":"))
        return Schedule(weekday=weekday_index, send_time=time(hour, minute))

    @property
    def weekday_name(self) -> str:
        return WEEKDAY_INDEX_TO_NAME[self.weekday]