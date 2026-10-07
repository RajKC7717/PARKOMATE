"""Operators, login, roles and lockout.

* Passwords are hashed with Argon2id (``argon2-cffi`` defaults) and re-hashed on login when
  the parameters change.
* After ``auth.max_failed_attempts`` wrong passwords the account is locked for
  ``auth.lockout_minutes``. While locked, the password is not even checked.
* Unknown operator codes and wrong passwords give the same answer (no account probing), and
  an unknown code still costs one hash verification (no timing probe).
* Every login, logout, failed attempt and admin change is written to the audit log.
"""

from __future__ import annotations

import logging
import math
import re
import threading
from collections.abc import Callable
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from parkomate.config.settings import AuthSettings
from parkomate.core.enums import Role, SessionEndReason
from parkomate.core.errors import (
    AuthError,
    ErrorCode,
    InputError,
    PermissionDeniedError,
    RecordStateError,
)
from parkomate.core.models import Operator
from parkomate.data import Repositories

log = logging.getLogger(__name__)

_CODE_RE = re.compile(r"^[A-Za-z0-9_.-]{2,32}$")


class AuthService:
    def __init__(
        self,
        repos: Repositories,
        settings: Callable[[], AuthSettings],
        *,
        hasher: PasswordHasher | None = None,
    ) -> None:
        self._repos = repos
        self._settings = settings
        self._hasher = hasher or PasswordHasher()
        self._lock = threading.Lock()
        self._dummy_hash: str | None = None

    # ------------------------------------------------------------------ hashing
    def hash_password(self, password: str) -> str:
        return self._hasher.hash(password)

    def _verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False
        except (VerificationError, InvalidHashError):
            log.exception("stored password hash could not be verified")
            return False

    def _burn_time(self, password: str) -> None:
        """Spend one verification on unknown codes so timing does not reveal them."""
        with self._lock:
            if self._dummy_hash is None:
                self._dummy_hash = self._hasher.hash("parkomate-dummy-password")
        self._verify(self._dummy_hash, password)

    # ------------------------------------------------------------------ validation
    def validate_password(self, password: str) -> None:
        minimum = self._settings().min_password_length
        if len(password) < minimum or not password.strip():
            raise AuthError(
                f"password shorter than {minimum} characters",
                code=ErrorCode.AUTH_WEAK_PASSWORD,
                params={"min": minimum},
            )

    @staticmethod
    def validate_code(code: str) -> str:
        code = code.strip()
        if not _CODE_RE.match(code):
            raise InputError(
                f"invalid operator code {code!r}",
                params={"value": code},
            )
        return code

    # ------------------------------------------------------------------ login
    def authenticate(self, operator_code: str, password: str) -> Operator:
        """Check credentials. Returns the operator or raises :class:`AuthError`."""
        settings = self._settings()
        code = operator_code.strip()
        operator = self._repos.operators.get_by_code(code) if code else None
        if operator is None:
            self._burn_time(password)
            self._repos.audit.record(
                None, "login.failed", {"operator_code": code, "reason": "unknown_code"}
            )
            raise AuthError("unknown operator code", code=ErrorCode.AUTH_INVALID_CREDENTIALS)

        now = self._repos.clock.now()
        failed = operator.failed_attempts
        if operator.locked_until is not None:
            if now < operator.locked_until:
                minutes = self.lock_minutes_remaining(operator)
                self._repos.audit.record(
                    operator.id, "login.failed", {"reason": "locked", "minutes_left": minutes}
                )
                raise AuthError(
                    "account locked",
                    code=ErrorCode.AUTH_LOCKED,
                    params={"minutes": minutes},
                )
            failed = 0  # lock expired: a fresh set of attempts

        password_hash = self._repos.operators.get_password_hash(operator.id)
        if not self._verify(password_hash, password):
            failed += 1
            if failed >= settings.max_failed_attempts:
                locked_until = now + timedelta(minutes=settings.lockout_minutes)
                self._repos.operators.set_lock_state(operator.id, 0, locked_until)
                self._repos.audit.record(
                    operator.id,
                    "login.lockout",
                    {"attempts": failed, "locked_until": locked_until.isoformat()},
                )
                raise AuthError(
                    "too many failed attempts - account locked",
                    code=ErrorCode.AUTH_LOCKED,
                    params={"minutes": math.ceil(settings.lockout_minutes)},
                )
            self._repos.operators.set_lock_state(operator.id, failed, None)
            self._repos.audit.record(
                operator.id, "login.failed", {"reason": "wrong_password", "attempts": failed}
            )
            raise AuthError("wrong password", code=ErrorCode.AUTH_INVALID_CREDENTIALS)

        if not operator.is_active:
            self._repos.audit.record(operator.id, "login.failed", {"reason": "inactive"})
            raise AuthError("operator is deactivated", code=ErrorCode.AUTH_INACTIVE)

        self._repos.operators.set_lock_state(operator.id, 0, None)
        if self._hasher.check_needs_rehash(password_hash):
            self._repos.operators.set_password_hash(operator.id, self.hash_password(password))
        self._repos.audit.record(operator.id, "login.success", {})
        return self._repos.operators.require(operator.id)

    def record_logout(self, operator: Operator, reason: SessionEndReason) -> None:
        self._repos.audit.record(operator.id, "logout", {"reason": reason.value})

    def lock_minutes_remaining(self, operator: Operator) -> int:
        if operator.locked_until is None:
            return 0
        seconds = (operator.locked_until - self._repos.clock.now()).total_seconds()
        return max(0, math.ceil(seconds / 60))

    # ------------------------------------------------------------------ operators
    def has_admin(self) -> bool:
        return self._repos.operators.count_active_admins() > 0

    def list_operators(self, *, include_inactive: bool = True) -> list[Operator]:
        return self._repos.operators.list_all(include_inactive=include_inactive)

    def create_first_admin(self, operator_code: str, full_name: str, password: str) -> Operator:
        """First-run bootstrap (CLI). Refused once an active admin exists."""
        if self.has_admin():
            raise RecordStateError("an administrator already exists")
        operator = self._create(operator_code, full_name, password, Role.ADMIN)
        self._repos.audit.record(
            None,
            "operator.create",
            {"operator_id": operator.id, "role": "admin", "bootstrap": True},
        )
        return operator

    def create_operator(
        self, actor: Operator, operator_code: str, full_name: str, password: str, role: Role
    ) -> Operator:
        self._require_admin(actor)
        operator = self._create(operator_code, full_name, password, role)
        self._repos.audit.record(
            actor.id, "operator.create", {"operator_id": operator.id, "role": role.value}
        )
        return operator

    def _create(self, operator_code: str, full_name: str, password: str, role: Role) -> Operator:
        code = self.validate_code(operator_code)
        name = full_name.strip()
        if not name:
            raise InputError("full name must not be empty")
        self.validate_password(password)
        if self._repos.operators.get_by_code(code) is not None:
            raise AuthError(
                f"operator code {code!r} already exists",
                code=ErrorCode.AUTH_DUPLICATE_OPERATOR,
                params={"code": code},
            )
        return self._repos.operators.create(code, name, self.hash_password(password), role)

    def reset_password(self, actor: Operator, operator_id: int, new_password: str) -> None:
        self._require_admin(actor)
        self.validate_password(new_password)
        self._repos.operators.require(operator_id)
        with self._repos.db.transaction():
            self._repos.operators.set_password_hash(operator_id, self.hash_password(new_password))
            self._repos.operators.set_lock_state(operator_id, 0, None)
            self._repos.audit.record(
                actor.id, "operator.password_reset", {"operator_id": operator_id}
            )

    def change_own_password(self, operator: Operator, old_password: str, new_password: str) -> None:
        if not self._verify(self._repos.operators.get_password_hash(operator.id), old_password):
            raise AuthError("old password wrong", code=ErrorCode.AUTH_INVALID_CREDENTIALS)
        self.validate_password(new_password)
        with self._repos.db.transaction():
            self._repos.operators.set_password_hash(operator.id, self.hash_password(new_password))
            self._repos.audit.record(operator.id, "operator.password_changed", {})

    def set_active(self, actor: Operator, operator_id: int, active: bool) -> None:
        self._require_admin(actor)
        target = self._repos.operators.require(operator_id)
        if not active:
            if target.id == actor.id:
                raise RecordStateError("administrators cannot deactivate themselves")
            if target.role is Role.ADMIN and self._repos.operators.count_active_admins() <= 1:
                raise RecordStateError("cannot deactivate the last active administrator")
        with self._repos.db.transaction():
            self._repos.operators.set_active(operator_id, active)
            self._repos.audit.record(
                actor.id,
                "operator.activate" if active else "operator.deactivate",
                {"operator_id": operator_id},
            )

    def set_role(self, actor: Operator, operator_id: int, role: Role) -> None:
        self._require_admin(actor)
        target = self._repos.operators.require(operator_id)
        if (
            target.role is Role.ADMIN
            and role is not Role.ADMIN
            and target.is_active
            and self._repos.operators.count_active_admins() <= 1
        ):
            raise RecordStateError("cannot demote the last active administrator")
        with self._repos.db.transaction():
            self._repos.operators.set_role(operator_id, role)
            self._repos.audit.record(
                actor.id, "operator.role", {"operator_id": operator_id, "role": role.value}
            )

    def unlock(self, actor: Operator, operator_id: int) -> None:
        self._require_admin(actor)
        self._repos.operators.require(operator_id)
        with self._repos.db.transaction():
            self._repos.operators.set_lock_state(operator_id, 0, None)
            self._repos.audit.record(actor.id, "operator.unlock", {"operator_id": operator_id})

    @staticmethod
    def _require_admin(actor: Operator) -> None:
        require_admin(actor)


def require_admin(actor: Operator) -> None:
    """Raise :class:`PermissionDeniedError` unless ``actor`` is an active admin."""
    if actor.role is not Role.ADMIN or not actor.is_active:
        raise PermissionDeniedError(
            f"operator {actor.operator_code!r} is not an administrator",
            context={"operator_id": actor.id},
        )
