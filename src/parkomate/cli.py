"""Command line.

    python -m parkomate [--mock] [--scenario NAME] [--kiosk]   start the station UI
    python -m parkomate admin create                          first-run administrator
    python -m parkomate admin unlock CODE                     unlock a locked operator
    python -m parkomate admin reset-password CODE             set a new password
    python -m parkomate settings check                        validate settings.toml
    python -m parkomate secrets set NAME                      store a secret in the keyring
    python -m parkomate secrets delete NAME
    python -m parkomate outbox send                           send pending e-mails now
    python -m parkomate report SESSION_ID [--format xlsx|csv|both] [--out DIR]

``--data-dir`` / ``PARKOMATE_DATA_DIR`` and ``--settings`` / ``PARKOMATE_SETTINGS`` select
the data folder and settings file.
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from parkomate import __version__
from parkomate.app import AppContext, build_context
from parkomate.app_paths import ENV_DATA_DIR, ENV_SETTINGS, AppPaths
from parkomate.config.manager import load_settings_file
from parkomate.core.errors import ParkomateError, SettingsError
from parkomate.core.models import Operator
from parkomate.hardware.mocks.scenarios import ENV_SCENARIO, MockScenario
from parkomate.i18n import t


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parkomate", description=t("cli.description"))
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--data-dir", type=Path, help=t("cli.help.data_dir"))
    parser.add_argument("--settings", type=Path, help=t("cli.help.settings"))
    parser.add_argument("--mock", action="store_true", help=t("cli.help.mock"))
    parser.add_argument(
        "--scenario",
        choices=[s.value for s in MockScenario],
        help=t("cli.help.scenario"),
    )
    parser.add_argument("--kiosk", action="store_true", help=t("cli.help.kiosk"))
    sub = parser.add_subparsers(dest="command")

    admin = sub.add_parser("admin", help=t("cli.help.admin"))
    admin_sub = admin.add_subparsers(dest="admin_command", required=True)
    create = admin_sub.add_parser("create", help=t("cli.help.admin_create"))
    create.add_argument("--code")
    create.add_argument("--name")
    create.add_argument("--password-stdin", action="store_true", help=t("cli.help.password_stdin"))
    unlock = admin_sub.add_parser("unlock", help=t("cli.help.admin_unlock"))
    unlock.add_argument("code")
    reset = admin_sub.add_parser("reset-password", help=t("cli.help.admin_reset"))
    reset.add_argument("code")
    reset.add_argument("--password-stdin", action="store_true", help=t("cli.help.password_stdin"))

    settings = sub.add_parser("settings", help=t("cli.help.settings_cmd"))
    settings_sub = settings.add_subparsers(dest="settings_command", required=True)
    settings_sub.add_parser("check", help=t("cli.help.settings_check"))

    secrets = sub.add_parser("secrets", help=t("cli.help.secrets"))
    secrets_sub = secrets.add_subparsers(dest="secrets_command", required=True)
    secret_set = secrets_sub.add_parser("set", help=t("cli.help.secrets_set"))
    secret_set.add_argument("name")
    secret_delete = secrets_sub.add_parser("delete", help=t("cli.help.secrets_delete"))
    secret_delete.add_argument("name")

    outbox = sub.add_parser("outbox", help=t("cli.help.outbox"))
    outbox_sub = outbox.add_subparsers(dest="outbox_command", required=True)
    outbox_sub.add_parser("send", help=t("cli.help.outbox_send"))

    report = sub.add_parser("report", help=t("cli.help.report"))
    report.add_argument("session_id", type=int)
    report.add_argument("--format", choices=["xlsx", "csv", "both"])
    report.add_argument("--out", type=Path)
    return parser


def _read_new_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass(t("cli.prompt.password"))
    second = getpass.getpass(t("cli.prompt.password_again"))
    if first != second:
        raise ParkomateError("passwords differ", params={"key": "cli.password_mismatch"})
    return first


def _print_error(exc: ParkomateError) -> None:
    if isinstance(exc, SettingsError) and exc.problems:
        print(t("cli.settings_invalid"), file=sys.stderr)
        for key, problem in exc.problems:
            print(f"  {key}: {problem}", file=sys.stderr)
        return
    message_key = exc.params.get("key") if isinstance(exc.params.get("key"), str) else None
    if message_key:
        print(t(message_key), file=sys.stderr)
        return
    print(f"{t(exc.title_key, **exc.params)} - {t(exc.cause_key, **exc.params)}", file=sys.stderr)
    print(f"[{exc.code.value}] {exc.message}", file=sys.stderr)


def _cli_actor(ctx: AppContext) -> Operator:
    """CLI admin actions are performed as the first active administrator (machine access)."""
    admins = [o for o in ctx.auth.list_operators(include_inactive=False) if o.is_admin]
    if not admins:
        raise ParkomateError("no administrator", params={"key": "cli.no_admin"})
    return admins[0]


def _utf8_console() -> None:
    """Windows consoles default to a legacy code page that cannot print Marathi."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(OSError, ValueError):
                reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    _utf8_console()
    args = _parser().parse_args(argv)
    if args.data_dir is not None:
        os.environ[ENV_DATA_DIR] = str(args.data_dir)
    if args.settings is not None:
        os.environ[ENV_SETTINGS] = str(args.settings)
    if args.scenario:
        os.environ[ENV_SCENARIO] = args.scenario

    if args.command is None:
        from parkomate.ui.main import run_ui

        return run_ui(mock=True if args.mock else None, kiosk=args.kiosk)

    try:
        if args.command == "settings":
            paths = AppPaths.default()
            load_settings_file(paths.settings_file)
            print(t("cli.settings_ok", path=str(paths.settings_file)))
            return 0
        ctx = build_context(mock=True, configure_logging=False)
        try:
            return _run_command(ctx, args)
        finally:
            ctx.close()
    except ParkomateError as exc:
        _print_error(exc)
        return 1


def _run_command(ctx: AppContext, args: argparse.Namespace) -> int:
    if args.command == "admin":
        if args.admin_command == "create":
            if ctx.auth.has_admin():
                print(t("cli.admin_exists"), file=sys.stderr)
                return 1
            code = args.code or input(t("cli.prompt.code"))
            name = args.name or input(t("cli.prompt.name"))
            password = _read_new_password(args.password_stdin)
            operator = ctx.auth.create_first_admin(code, name, password)
            print(t("cli.admin_created", code=operator.operator_code))
            return 0
        target = ctx.repos.operators.get_by_code(args.code)
        if target is None:
            print(t("cli.operator_not_found", code=args.code), file=sys.stderr)
            return 1
        actor = _cli_actor(ctx)
        if args.admin_command == "unlock":
            ctx.auth.unlock(actor, target.id)
            print(t("cli.operator_unlocked", code=target.operator_code))
            return 0
        password = _read_new_password(args.password_stdin)
        ctx.auth.reset_password(actor, target.id, password)
        print(t("cli.password_reset_done", code=target.operator_code))
        return 0
    if args.command == "secrets":
        if args.secrets_command == "set":
            value = getpass.getpass(t("cli.prompt.secret", name=args.name))
            ctx.secrets.set(args.name, value)
            print(t("cli.secret_saved", name=args.name))
        else:
            ctx.secrets.delete(args.name)
            print(t("cli.secret_deleted", name=args.name))
        return 0
    if args.command == "outbox":
        report = ctx.outbox.process_due()
        if report.skipped:
            print(t("cli.outbox_disabled"))
        else:
            print(t("cli.outbox_result", sent=report.sent, failed=report.failed))
        return 0 if report.failed == 0 else 1
    if args.command == "report":
        paths = ctx.exporter.export_session(args.session_id, fmt=args.format, out_dir=args.out)
        for path in paths:
            print(path)
        return 0
    raise AssertionError(f"unhandled command {args.command}")  # pragma: no cover


__all__ = ["main"]
