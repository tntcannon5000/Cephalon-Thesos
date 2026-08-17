from __future__ import annotations

import argparse
import asyncio

from veris_api.db.identity import seed_allowlist
from veris_api.db.session import dispose_engine
from veris_api.event_loop import configure_platform_event_loop
from veris_api.security import normalize_email


async def _bootstrap_access(emails: list[str], admin_email: str | None) -> None:
    normalized = list(dict.fromkeys(normalize_email(email) for email in emails))
    normalized_admin = normalize_email(admin_email) if admin_email else None
    if normalized_admin and normalized_admin not in normalized:
        normalized.append(normalized_admin)
    inserted = await seed_allowlist(normalized, admin_email=normalized_admin)
    print(f"Access bootstrap complete: {inserted} address(es) added.")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Thesos management commands")
    commands = root.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser(
        "bootstrap-access",
        help="Seed exact private-alpha addresses and the one initial administrator",
    )
    bootstrap.add_argument("--email", action="append", required=True)
    bootstrap.add_argument("--admin-email")
    return root


async def _run(arguments: argparse.Namespace) -> None:
    try:
        if arguments.command == "bootstrap-access":
            await _bootstrap_access(arguments.email, arguments.admin_email)
    finally:
        await dispose_engine()


def main() -> None:
    configure_platform_event_loop()
    asyncio.run(_run(parser().parse_args()))


if __name__ == "__main__":
    main()
