#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def encrypted_objects(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        (
            item
            for item in payload.get("data", [])
            if isinstance(item, dict) and str(item.get("name", "")).endswith(".dump.age")
        ),
        key=lambda item: parse_time(str(item["time-created"])),
        reverse=True,
    )


def deletion_plan(
    payload: dict[str, Any], daily_count: int, weekly_count: int
) -> list[str]:
    backups = encrypted_objects(payload)
    keep = {str(item["name"]) for item in backups[:daily_count]}
    represented_weeks = {
        parse_time(str(item["time-created"])).isocalendar()[:2]
        for item in backups[:daily_count]
    }
    weekly_kept = 0
    for item in backups[daily_count:]:
        week = parse_time(str(item["time-created"])).isocalendar()[:2]
        if week in represented_weeks or weekly_kept >= weekly_count:
            continue
        keep.add(str(item["name"]))
        represented_weeks.add(week)
        weekly_kept += 1

    delete: set[str] = set()
    available = {str(item.get("name", "")) for item in payload.get("data", [])}
    for item in backups:
        name = str(item["name"])
        if name not in keep:
            delete.add(name)
            checksum = f"{name}.sha256"
            if checksum in available:
                delete.add(checksum)

    encrypted_names = {str(item["name"]) for item in backups}
    for name in available:
        if name.endswith(".dump.age.sha256") and name.removesuffix(".sha256") not in encrypted_names:
            delete.add(name)
    return sorted(delete)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory")
    parser.add_argument("--daily", type=int, default=7)
    parser.add_argument("--weekly", type=int, default=4)
    parser.add_argument("--total-bytes", action="store_true")
    args = parser.parse_args()
    with open(args.inventory, encoding="utf-8") as source:
        payload = json.load(source)
    if args.total_bytes:
        print(sum(int(item.get("size", 0)) for item in payload.get("data", [])))
        return
    for name in deletion_plan(payload, args.daily, args.weekly):
        print(name)


if __name__ == "__main__":
    main()
