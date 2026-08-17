from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "prune-object-storage.py"
SPEC = importlib.util.spec_from_file_location("prune_object_storage", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def object_record(name: str, created: str, size: int = 100) -> dict[str, object]:
    return {"name": name, "time-created": created, "size": size}


class ObjectStoragePruningTests(unittest.TestCase):
    def test_keeps_recent_backups_and_distinct_weekly_anchors(self) -> None:
        records = [
            object_record(f"postgres/recent-{day}.dump.age", f"2026-08-{day:02d}T03:00:00Z")
            for day in range(17, 10, -1)
        ]
        records.extend(
            [
                object_record("postgres/week-32.dump.age", "2026-08-05T03:00:00Z"),
                object_record("postgres/week-31.dump.age", "2026-07-29T03:00:00Z"),
                object_record("postgres/week-30.dump.age", "2026-07-22T03:00:00Z"),
                object_record("postgres/old-same-week.dump.age", "2026-07-21T03:00:00Z"),
            ]
        )
        records.extend(
            object_record(f"{record['name']}.sha256", str(record["time-created"]), 16)
            for record in list(records)
        )

        deleted = MODULE.deletion_plan({"data": records}, daily_count=7, weekly_count=2)

        self.assertIn("postgres/week-30.dump.age", deleted)
        self.assertIn("postgres/old-same-week.dump.age", deleted)
        self.assertIn("postgres/week-30.dump.age.sha256", deleted)
        self.assertNotIn("postgres/week-32.dump.age", deleted)
        self.assertNotIn("postgres/week-31.dump.age", deleted)

    def test_deletes_orphaned_checksum(self) -> None:
        payload = {
            "data": [
                object_record(
                    "postgres/orphan.dump.age.sha256", "2026-08-17T03:00:00Z", 16
                )
            ]
        }

        self.assertEqual(
            MODULE.deletion_plan(payload, daily_count=7, weekly_count=4),
            ["postgres/orphan.dump.age.sha256"],
        )


if __name__ == "__main__":
    unittest.main()
