from __future__ import annotations

import asyncio

from veris_api.db.dispatch import worker_is_live
from veris_api.db.session import dispose_engine


async def check() -> bool:
    try:
        return await worker_is_live()
    finally:
        await dispose_engine()


def main() -> None:
    raise SystemExit(0 if asyncio.run(check()) else 1)


if __name__ == "__main__":
    main()
