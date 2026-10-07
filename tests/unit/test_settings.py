from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from parkomate.config.manager import (
    SettingsManager,
    diff_settings,
    load_settings_file,
    settings_to_toml,
    validate_settings,
)
from parkomate.config.secrets import MemorySecretStore, require_secret
from parkomate.config.settings import Settings
from parkomate.core.errors import PermissionDeniedError, SecretMissingError, SettingsError
from parkomate.core.models import Operator
from parkomate.data import Repositories

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "settings.example.toml"


def test_defaults_are_valid() -> None:
    settings = Settings()
    assert settings.limits.v_c_low == 3.25
    assert settings.limits.temp_margin_c == 3.0
    assert settings.limits.sensor_reading_count == 5
    assert settings.programming.max_retries == 3
    assert settings.station.language == "en"


def test_example_file_is_valid_and_equals_defaults() -> None:
    assert load_settings_file(EXAMPLE) == Settings()


def test_example_documents_every_key() -> None:
    from parkomate.config.manager import flatten

    example = flatten(tomllib.loads(EXAMPLE.read_text(encoding="utf-8")))
    defaults = flatten(Settings().model_dump(mode="json"))
    assert set(example) == set(defaults)


def _problem_keys(exc: SettingsError) -> list[str]:
    return [key for key, _ in exc.problems]


def test_bad_value_names_exact_key() -> None:
    with pytest.raises(SettingsError) as info:
        validate_settings({"limits": {"v_c_low": "abc"}})
    assert _problem_keys(info.value) == ["limits.v_c_low"]
    assert "abc" in info.value.problems[0][1]


def test_unknown_key_rejected_with_hint() -> None:
    with pytest.raises(SettingsError) as info:
        validate_settings({"email": {"password": "hunter2"}})
    key, problem = info.value.problems[0]
    assert key == "email.password"
    assert "keyring" in problem


def test_low_must_be_below_high() -> None:
    with pytest.raises(SettingsError) as info:
        validate_settings({"limits": {"v_b_low": 5.2, "v_b_high": 5.1}})
    assert "v_b_low" in info.value.problems[0][1]


def test_email_enabled_requires_fields() -> None:
    with pytest.raises(SettingsError) as info:
        validate_settings({"email": {"enabled": True}})
    assert "host" in info.value.problems[0][1]
    assert "recipients" in info.value.problems[0][1]


def test_email_addresses_validated() -> None:
    with pytest.raises(SettingsError) as info:
        validate_settings({"email": {"recipients": ["ok@example.com", "not-an-email"]}})
    assert _problem_keys(info.value) == ["email.recipients"]


def test_server_requires_https_except_localhost() -> None:
    with pytest.raises(SettingsError):
        validate_settings({"server": {"base_url": "http://api.example.com"}})
    ok = validate_settings({"server": {"base_url": "http://localhost:8000/"}})
    assert ok.server.base_url == "http://localhost:8000"


@pytest.mark.parametrize(
    ("section", "values"),
    [
        ("limits", {"sensor_reading_count": 11}),
        ("measurement", {"allowed_ip": "999.1.1.1"}),
        ("camera", {"id_pattern": "(["}),
        ("station", {"language": "de"}),
        ("station", {"station_id": "bad id with spaces"}),
        ("server", {"whitelist_path": "no-slash"}),
        ("timeouts", {"ping_s": 0}),
    ],
)
def test_invalid_values(section: str, values: dict[str, object]) -> None:
    with pytest.raises(SettingsError) as info:
        validate_settings({section: values})
    assert _problem_keys(info.value)[0].startswith(section)


def test_toml_syntax_error(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text("[limits\nv_a_low = 1", encoding="utf-8")
    with pytest.raises(SettingsError) as info:
        load_settings_file(path)
    assert info.value.problems[0][0] == "(syntax)"


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SettingsError):
        load_settings_file(tmp_path / "nope.toml")


def test_manager_creates_defaults_on_first_run(tmp_path: Path) -> None:
    manager = SettingsManager(tmp_path / "settings.toml")
    settings = manager.load()
    assert settings == Settings()
    assert (tmp_path / "settings.toml").exists()
    assert load_settings_file(tmp_path / "settings.toml") == settings


def test_manager_current_before_load_raises(tmp_path: Path) -> None:
    with pytest.raises(SettingsError):
        _ = SettingsManager(tmp_path / "s.toml").current


def test_save_admin_only(tmp_path: Path, operator: Operator) -> None:
    manager = SettingsManager(tmp_path / "settings.toml")
    manager.load()
    with pytest.raises(PermissionDeniedError):
        manager.save(Settings(), operator)


def test_save_validates_writes_audits_and_notifies(
    tmp_path: Path, admin: Operator, repos: Repositories
) -> None:
    manager = SettingsManager(tmp_path / "settings.toml", audit=repos.audit)
    manager.load()
    seen: list[tuple[str, ...]] = []
    manager.add_listener(lambda _s, changed: seen.append(changed))
    raw = manager.current.model_dump(mode="json")
    raw["limits"]["v_c_high"] = 3.4
    raw["station"]["station_id"] = "BENCH-7"
    changes = manager.save(raw, admin)
    assert changes == {
        "limits.v_c_high": (3.35, 3.4),
        "station.station_id": ("STATION-01", "BENCH-7"),
    }
    assert load_settings_file(tmp_path / "settings.toml").limits.v_c_high == 3.4
    entry = repos.audit.list_entries(action="settings.update")[0]
    assert entry.operator_id == admin.id
    assert entry.details["changes"]["limits.v_c_high"] == [3.35, 3.4]
    assert seen == [("limits.v_c_high", "station.station_id")]


def test_save_rejects_invalid(tmp_path: Path, admin: Operator) -> None:
    manager = SettingsManager(tmp_path / "settings.toml")
    manager.load()
    with pytest.raises(SettingsError):
        manager.save({"limits": {"v_a_low": 30, "v_a_high": 20}}, admin)
    assert manager.current == Settings()


def test_save_without_changes_is_noop(tmp_path: Path, admin: Operator, repos: Repositories) -> None:
    manager = SettingsManager(tmp_path / "settings.toml", audit=repos.audit)
    manager.load()
    assert manager.save(Settings(), admin) == {}
    assert repos.audit.list_entries(action="settings.update") == []


def test_reload_notifies_changed_keys(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    manager = SettingsManager(path)
    manager.load()
    received: list[tuple[Settings, tuple[str, ...]]] = []
    remove = manager.add_listener(lambda s, changed: received.append((s, changed)))
    data = Settings().model_dump(mode="json")
    data["programming"]["max_retries"] = 5
    path.write_text(settings_to_toml(validate_settings(data)), encoding="utf-8")
    new = manager.reload()
    assert new.programming.max_retries == 5
    assert received[0][1] == ("programming.max_retries",)
    remove()
    manager.reload()
    assert len(received) == 1


def test_listener_failure_does_not_break_reload(tmp_path: Path) -> None:
    manager = SettingsManager(tmp_path / "settings.toml")
    manager.load()

    def boom(_s: Settings, _c: tuple[str, ...]) -> None:
        raise RuntimeError("listener bug")

    manager.add_listener(boom)
    assert manager.reload() == Settings()


def test_diff_settings_empty_for_equal() -> None:
    assert diff_settings(Settings(), Settings()) == {}


def test_secret_store_and_require() -> None:
    store = MemorySecretStore({"smtp_password": "pw"})
    assert require_secret(store, "smtp_password") == "pw"
    store.delete("smtp_password")
    with pytest.raises(SecretMissingError) as info:
        require_secret(store, "smtp_password")
    assert info.value.params == {"name": "smtp_password"}
    store.set("x", "y")
    assert store.get("x") == "y"


def test_keyring_store_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    import keyring
    from keyring.backend import KeyringBackend

    class Memory(KeyringBackend):
        priority = 1  # type: ignore[assignment]

        def __init__(self) -> None:
            super().__init__()
            self.values: dict[tuple[str, str], str] = {}

        def get_password(self, service: str, username: str) -> str | None:
            return self.values.get((service, username))

        def set_password(self, service: str, username: str, password: str) -> None:
            self.values[(service, username)] = password

        def delete_password(self, service: str, username: str) -> None:
            import keyring.errors

            if (service, username) not in self.values:
                raise keyring.errors.PasswordDeleteError(username)
            del self.values[(service, username)]

    from parkomate.config.secrets import KeyringSecretStore

    previous = keyring.get_keyring()
    keyring.set_keyring(Memory())
    try:
        store = KeyringSecretStore("ParkomateTest")
        assert store.get("a") is None
        store.set("a", "b")
        assert store.get("a") == "b"
        store.delete("a")
        store.delete("a")  # deleting twice is fine
        assert store.get("a") is None
    finally:
        keyring.set_keyring(previous)
