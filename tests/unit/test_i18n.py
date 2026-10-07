"""Catalogue completeness: Marathi has every English key, with the same placeholders."""

from __future__ import annotations

import logging
import string

import pytest

from parkomate.core.enums import (
    AmbientReason,
    CheckCode,
    DeviceStatus,
    IdentityStatus,
    IdEntryMethod,
    OutboxStatus,
    Role,
    SessionEndReason,
    Stage,
)
from parkomate.core.errors import ErrorCode
from parkomate.i18n import (
    LANGUAGES,
    Translator,
    add_language_listener,
    get_language,
    load_catalogue,
    resolve_params,
    set_language,
    t,
    tr,
    tr_message,
)

EN = load_catalogue("en")
MR = load_catalogue("mr")


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_marathi_has_every_english_key() -> None:
    missing = sorted(set(EN) - set(MR))
    assert missing == [], f"mr.json is missing {len(missing)} key(s): {missing[:20]}"


def test_no_orphan_marathi_keys() -> None:
    assert sorted(set(MR) - set(EN)) == []


def test_placeholders_match() -> None:
    mismatched = [k for k in EN if _placeholders(EN[k]) != _placeholders(MR.get(k, EN[k]))]
    assert mismatched == []


def test_no_empty_texts() -> None:
    for catalogue in (EN, MR):
        assert [k for k, v in catalogue.items() if not v.strip()] == []


def test_every_error_code_has_title_cause_action() -> None:
    for code in ErrorCode:
        for key in (code.title_key, code.cause_key, code.action_key):
            assert key in EN, key


@pytest.mark.parametrize(
    "keys",
    [
        [s.label_key for s in Stage],
        [c.label_key for c in CheckCode],
        [d.label_key for d in DeviceStatus],
        [r.label_key for r in Role],
        [r.label_key for r in SessionEndReason],
        [r.label_key for r in AmbientReason],
        [m.label_key for m in IdEntryMethod],
        [s.label_key for s in OutboxStatus],
        [s.label_key for s in IdentityStatus],
    ],
)
def test_enum_labels_exist(keys: list[str]) -> None:
    assert [k for k in keys if k not in EN] == []


def test_translate_and_fallback(caplog: pytest.LogCaptureFixture) -> None:
    translator = Translator("mr")
    assert translator.translate(None, "stage.testing", {}) == "चाचणी"
    translator._catalogues["mr"].pop("stage.testing")
    with caplog.at_level(logging.WARNING):
        assert translator.translate(None, "stage.testing", {}) == "Testing"
        assert translator.translate(None, "stage.testing", {}) == "Testing"
    warnings = [r for r in caplog.records if "missing translation" in r.getMessage()]
    assert len(warnings) == 1  # warned once per key


def test_unknown_key_returns_key(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert t("no.such.key") == "no.such.key"
    assert any("no.such.key" in r.getMessage() for r in caplog.records)


def test_params_and_missing_params() -> None:
    assert tr("en", "error.auth_locked.cause", minutes=4).endswith("4 more minute(s).")
    assert "{minutes}" in tr("en", "error.auth_locked.cause")  # left visible, no crash


def test_resolve_nested_keys() -> None:
    params = {"check_key": "check.B3_V_C", "value": "3.21"}
    assert resolve_params("mr", params)["check"] == "पॉइंट C व्होल्टेज"
    text = tr_message(
        "en",
        "reject.reason.out_of_range",
        {**params, "unit": "V", "low": "3.25", "high": "3.35"},
    )
    assert text == "Point C voltage 3.21 V - allowed 3.25-3.35 V"


def test_language_switch_notifies() -> None:
    seen: list[str] = []
    remove = add_language_listener(seen.append)
    try:
        set_language("mr")
        set_language("mr")  # unchanged -> no second notification
        assert get_language() == "mr" and t("stage.packaging") == "पॅकेजिंग"
        set_language("xx")  # unknown -> English
        assert get_language() == "en"
    finally:
        remove()
        set_language("en")
    assert seen == ["mr", "en"]


def test_languages_constant() -> None:
    assert LANGUAGES == ("en", "mr")
