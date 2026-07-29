"""
Deliberately empty. `core` is never imported as a whole (no
`from core import X`) — always via its submodules:
`core.models`, `core.interfaces`, `core.scheduler`. Adding re-exports
here would also risk a circular import, since core.scheduler imports
from core.interfaces and core.models.
"""

from core.models.recipient import Recipient
from core.models.schedule import WEEKDAY_NAME_TO_INDEX, Schedule

__all__ = ["Recipient", "Schedule", "WEEKDAY_NAME_TO_INDEX"]