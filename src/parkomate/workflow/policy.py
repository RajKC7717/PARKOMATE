"""Retry policy: which failures may be tried again, and how often.

By default only the firmware upload is retriable (``workflow.retriable_checks =
["A_UPLOAD"]``, up to ``programming.max_retries`` attempts). The communication test
(``B1_COMM``) and the electrical measurement (``B3_ELECTRICAL``) can be made retriable in
the settings (up to ``workflow.max_attempts``). Every other failure rejects at once.
"""

from __future__ import annotations

from parkomate.config.settings import Settings
from parkomate.core.enums import CheckCode

ELECTRICAL = frozenset(
    {CheckCode.B3_V_A, CheckCode.B3_V_B, CheckCode.B3_V_C, CheckCode.B3_T_REG}
)


def retry_group(code: CheckCode) -> str | None:
    """Settings name of the retry group a check belongs to (None = never retriable)."""
    if code is CheckCode.A_UPLOAD:
        return "A_UPLOAD"
    if code is CheckCode.B1_COMM:
        return "B1_COMM"
    if code in ELECTRICAL:
        return "B3_ELECTRICAL"
    return None


class RetryPolicy:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def max_attempts(self, code: CheckCode) -> int:
        group = retry_group(code)
        if group is None or group not in self._settings.workflow.retriable_checks:
            return 1
        if group == "A_UPLOAD":
            return self._settings.programming.max_retries
        return self._settings.workflow.max_attempts

    def retry_allowed(self, code: CheckCode, attempts_so_far: int) -> bool:
        """``attempts_so_far`` includes the attempt that just failed."""
        return attempts_so_far < self.max_attempts(code)
