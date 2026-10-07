from __future__ import annotations

import pytest
from argon2 import PasswordHasher

from parkomate.auth.service import AuthService, require_admin
from parkomate.config.settings import AuthSettings, Settings
from parkomate.core.clock import FakeClock
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
from tests.conftest import PASSWORD


def _actions(repos: Repositories) -> list[str]:
    return [e.action for e in reversed(repos.audit.list_entries())]


def test_login_success_audited(auth: AuthService, operator: Operator, repos: Repositories) -> None:
    logged_in = auth.authenticate(" OP1 ", PASSWORD)
    assert logged_in.id == operator.id
    assert "login.success" in _actions(repos)
    auth.record_logout(logged_in, SessionEndReason.LOGOUT)
    assert repos.audit.list_entries(action="logout")[0].details == {"reason": "logout"}


def test_wrong_password_and_unknown_code_look_the_same(
    auth: AuthService, operator: Operator, repos: Repositories
) -> None:
    with pytest.raises(AuthError) as wrong:
        auth.authenticate("OP1", "nope")
    with pytest.raises(AuthError) as unknown:
        auth.authenticate("NOBODY", "nope")
    with pytest.raises(AuthError) as empty:
        auth.authenticate("", "nope")
    assert wrong.value.code is unknown.value.code is empty.value.code
    assert wrong.value.code is ErrorCode.AUTH_INVALID_CREDENTIALS
    failed = repos.audit.list_entries(action="login.failed")
    assert {e.details["reason"] for e in failed} == {"wrong_password", "unknown_code"}


def test_lockout_after_five_failures(
    auth: AuthService, operator: Operator, clock: FakeClock, repos: Repositories
) -> None:
    for _ in range(4):
        with pytest.raises(AuthError) as info:
            auth.authenticate("OP1", "bad")
        assert info.value.code is ErrorCode.AUTH_INVALID_CREDENTIALS
    with pytest.raises(AuthError) as locked:
        auth.authenticate("OP1", "bad")
    assert locked.value.code is ErrorCode.AUTH_LOCKED
    assert locked.value.params == {"minutes": 5}
    # Even the right password is refused while locked, with minutes remaining.
    clock.advance(minutes=2, seconds=10)
    with pytest.raises(AuthError) as still:
        auth.authenticate("OP1", PASSWORD)
    assert still.value.code is ErrorCode.AUTH_LOCKED
    assert still.value.params == {"minutes": 3}
    assert auth.lock_minutes_remaining(repos.operators.require(operator.id)) == 3
    clock.advance(minutes=3)
    assert auth.authenticate("OP1", PASSWORD).failed_attempts == 0
    assert "login.lockout" in _actions(repos)


def test_failures_reset_after_lock_expires(
    auth: AuthService, operator: Operator, clock: FakeClock
) -> None:
    for _ in range(5):
        with pytest.raises(AuthError):
            auth.authenticate("OP1", "bad")
    clock.advance(minutes=6)
    with pytest.raises(AuthError) as info:  # first failure of a fresh set: not locked again
        auth.authenticate("OP1", "bad")
    assert info.value.code is ErrorCode.AUTH_INVALID_CREDENTIALS


def test_configurable_lockout(repos: Repositories, fast_hasher: PasswordHasher) -> None:
    settings = Settings(auth=AuthSettings(max_failed_attempts=2, lockout_minutes=1))
    auth = AuthService(repos, lambda: settings.auth, hasher=fast_hasher)
    auth.create_first_admin("ADM", "Admin", PASSWORD)
    with pytest.raises(AuthError):
        auth.authenticate("ADM", "x")
    with pytest.raises(AuthError) as info:
        auth.authenticate("ADM", "x")
    assert info.value.code is ErrorCode.AUTH_LOCKED and info.value.params == {"minutes": 1}


def test_admin_unlock(
    auth: AuthService, operator: Operator, admin: Operator, repos: Repositories
) -> None:
    for _ in range(5):
        with pytest.raises(AuthError):
            auth.authenticate("OP1", "bad")
    with pytest.raises(PermissionDeniedError):
        auth.unlock(operator, operator.id)
    auth.unlock(admin, operator.id)
    assert auth.authenticate("OP1", PASSWORD).locked_until is None
    assert "operator.unlock" in _actions(repos)


def test_inactive_operator(auth: AuthService, operator: Operator, admin: Operator) -> None:
    auth.set_active(admin, operator.id, False)
    with pytest.raises(AuthError) as info:
        auth.authenticate("OP1", PASSWORD)
    assert info.value.code is ErrorCode.AUTH_INACTIVE
    with pytest.raises(AuthError) as wrong:  # a wrong password still says "invalid"
        auth.authenticate("OP1", "bad")
    assert wrong.value.code is ErrorCode.AUTH_INVALID_CREDENTIALS
    auth.set_active(admin, operator.id, True)
    assert auth.authenticate("OP1", PASSWORD).is_active


def test_first_admin_only_once(auth: AuthService, admin: Operator) -> None:
    assert auth.has_admin()
    with pytest.raises(RecordStateError):
        auth.create_first_admin("ADM2", "Second", PASSWORD)


def test_operator_management_validation(auth: AuthService, admin: Operator) -> None:
    with pytest.raises(AuthError) as weak:
        auth.create_operator(admin, "OP2", "Two", "123", Role.OPERATOR)
    assert weak.value.code is ErrorCode.AUTH_WEAK_PASSWORD and weak.value.params == {"min": 6}
    with pytest.raises(InputError):
        auth.create_operator(admin, "bad code!", "Two", PASSWORD, Role.OPERATOR)
    with pytest.raises(InputError):
        auth.create_operator(admin, "OP2", "   ", PASSWORD, Role.OPERATOR)
    auth.create_operator(admin, "OP2", "Two", PASSWORD, Role.OPERATOR)
    with pytest.raises(AuthError) as dup:
        auth.create_operator(admin, "op2", "Dup", PASSWORD, Role.OPERATOR)
    assert dup.value.code is ErrorCode.AUTH_DUPLICATE_OPERATOR


def test_operators_cannot_manage(auth: AuthService, operator: Operator) -> None:
    for call in (
        lambda: auth.create_operator(operator, "X1", "X", PASSWORD, Role.OPERATOR),
        lambda: auth.reset_password(operator, operator.id, PASSWORD),
        lambda: auth.set_active(operator, operator.id, False),
        lambda: auth.set_role(operator, operator.id, Role.ADMIN),
    ):
        with pytest.raises(PermissionDeniedError):
            call()
    with pytest.raises(PermissionDeniedError):
        require_admin(operator)


def test_last_admin_protected(auth: AuthService, admin: Operator, operator: Operator) -> None:
    with pytest.raises(RecordStateError):
        auth.set_active(admin, admin.id, False)  # cannot deactivate yourself
    with pytest.raises(RecordStateError):
        auth.set_role(admin, admin.id, Role.OPERATOR)  # last admin cannot be demoted
    second = auth.create_operator(admin, "ADM2", "Second", PASSWORD, Role.ADMIN)
    auth.set_role(admin, operator.id, Role.ADMIN)
    auth.set_role(admin, operator.id, Role.OPERATOR)
    auth.set_active(admin, second.id, False)
    with pytest.raises(RecordStateError):
        auth.set_active(second.model_copy(update={"is_active": True}), admin.id, False)


def test_reset_and_change_password(
    auth: AuthService, operator: Operator, admin: Operator, repos: Repositories
) -> None:
    auth.reset_password(admin, operator.id, "new-password-1")
    assert auth.authenticate("OP1", "new-password-1")
    with pytest.raises(AuthError):
        auth.change_own_password(operator, "wrong", "another-pass")
    auth.change_own_password(operator, "new-password-1", "another-pass")
    assert auth.authenticate("OP1", "another-pass")
    assert {"operator.password_reset", "operator.password_changed"} <= set(_actions(repos))


def test_password_rehashed_when_parameters_change(
    repos: Repositories, settings: Settings, operator: Operator
) -> None:
    stronger = PasswordHasher(time_cost=2, memory_cost=128, parallelism=1)
    auth = AuthService(repos, lambda: settings.auth, hasher=stronger)
    before = repos.operators.get_password_hash(operator.id)
    auth.authenticate("OP1", PASSWORD)
    after = repos.operators.get_password_hash(operator.id)
    assert before != after and "t=2" in after


def test_corrupt_hash_is_a_failed_login(
    auth: AuthService, operator: Operator, repos: Repositories
) -> None:
    repos.operators.set_password_hash(operator.id, "not-an-argon2-hash")
    with pytest.raises(AuthError):
        auth.authenticate("OP1", PASSWORD)


def test_list_operators(auth: AuthService, admin: Operator, operator: Operator) -> None:
    assert [o.operator_code for o in auth.list_operators()] == ["ADM1", "OP1"]
