"""One repository class per aggregate. Every write runs in a transaction."""

from parkomate.data.repositories.audit import AuditRepo
from parkomate.data.repositories.checks import CheckResultRepo
from parkomate.data.repositories.counters import CounterRepo
from parkomate.data.repositories.devices import DeviceRepo
from parkomate.data.repositories.operators import OperatorRepo
from parkomate.data.repositories.outbox import OutboxRepo
from parkomate.data.repositories.sessions import SessionRepo

__all__ = [
    "AuditRepo",
    "CheckResultRepo",
    "CounterRepo",
    "DeviceRepo",
    "OperatorRepo",
    "OutboxRepo",
    "SessionRepo",
]
