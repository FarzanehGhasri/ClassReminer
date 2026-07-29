"""
The reusable engine: "for each recipient whose schedule is due now, try
every channel, skip what doesn't apply, never let one failure stop the
rest." Everything it touches is an abstraction from core/interfaces.py —
this file has zero knowledge of CSV, SQLite, SMTP, or Telegram.

That's Dependency Inversion in practice: the high-level policy (this
file) doesn't depend on low-level detail (infrastructure/, channels/);
both depend on the interfaces in between.
"""
import logging
from datetime import datetime
from typing import List, Optional

from core.interfaces import DuplicateGuard, FailureHandler, NotificationChannel, RecipientRepository
from core.models import Recipient

logger = logging.getLogger(__name__)


class ScheduleChecker:
    """Single responsibility: decide if a recipient's schedule matches 'now'.

    lead_minutes lets the notification fire before the class starts —
    e.g. lead_minutes=30 sends the reminder 30 minutes ahead of
    schedule_time, not at schedule_time itself."""

    def __init__(self, tolerance_minutes: int, lead_minutes: int = 0):
        self._tolerance_minutes = tolerance_minutes
        self._lead_minutes = lead_minutes

    def is_due_now(self, recipient: Recipient, now: datetime) -> bool:
        if now.weekday() != recipient.schedule.weekday:
            return False
        scheduled = recipient.schedule.send_time.hour * 60 + recipient.schedule.send_time.minute
        target = (scheduled - self._lead_minutes) % (24 * 60)
        current = now.hour * 60 + now.minute
        return abs(current - target) <= self._tolerance_minutes


class Scheduler:
    """Single responsibility: orchestrate one run across all due recipients
    and all channels. Every collaborator is injected as an abstraction —
    this class never constructs a concrete implementation itself."""

    def __init__(
        self,
        repository: RecipientRepository,
        schedule_checker: ScheduleChecker,
        duplicate_guard: DuplicateGuard,
        channels: List[NotificationChannel],
        default_link: str = "",
        failure_handler: Optional[FailureHandler] = None,
    ):
        self._repository = repository
        self._schedule_checker = schedule_checker
        self._duplicate_guard = duplicate_guard
        self._channels = channels
        self._default_link = default_link
        self._failure_handler = failure_handler

    def run(self, now: datetime = None) -> None:
        now = now or datetime.now()
        try:
            recipients = self._repository.load_all()
        except Exception as error:
            logger.error("Could not load recipients: %s", error)
            self._report_failure(None, "repository", error)
            return

        for recipient in recipients:
            if self._schedule_checker.is_due_now(recipient, now):
                self._notify_on_all_channels(recipient)

    def _notify_on_all_channels(self, recipient: Recipient) -> None:
        for channel in self._channels:
            self._notify_on_channel(recipient, channel)

    def _notify_on_channel(self, recipient: Recipient, channel: NotificationChannel) -> None:
        if not channel.can_send_to(recipient):
            logger.info("Skip %s on %s: no contact info", recipient.name, channel.channel_name)
            return
        if self._duplicate_guard.already_sent(recipient.unique_key, channel.channel_name):
            logger.info("Skip %s on %s: already sent", recipient.name, channel.channel_name)
            return

        link = recipient.message_link or self._default_link
        try:
            channel.send(recipient, link)
            self._duplicate_guard.mark_sent(recipient.unique_key, channel.channel_name)
            logger.info("Sent to %s via %s", recipient.name, channel.channel_name)
        except Exception as error:
            logger.error("Failed to send to %s via %s: %s", recipient.name, channel.channel_name, error)
            self._report_failure(recipient, channel.channel_name, error)

    def _report_failure(self, recipient, channel: str, error: Exception) -> None:
        if self._failure_handler:
            self._failure_handler.handle(recipient, channel, error)