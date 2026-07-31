#!/usr/bin/env python3
"""Найти вероятные дубли подписок (dry-run по умолчанию).

Группировка: user + route + dates + threshold + flexibility + pax + currency.

Примеры:
  python scripts/find_watch_duplicates.py
  python scripts/find_watch_duplicates.py --db /opt/flyping/data/flyping.db
  python scripts/find_watch_duplicates.py --delete-duplicates --keep-oldest
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Allow running from repo root without install.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class DupKey:
    user_id: int
    origin: str
    destination: str
    depart_date: str
    return_date: str
    max_price: float
    flexibility_days: int
    adults: int
    children: int
    infants: int
    currency: str


def _key_of(w) -> DupKey:
    return DupKey(
        user_id=int(w.user_id),
        origin=str(w.origin or "").upper(),
        destination=str(w.destination or "").upper(),
        depart_date=str(w.depart_date or ""),
        return_date=str(w.return_date or ""),
        max_price=float(w.max_price),
        flexibility_days=int(w.flexibility_days or 0),
        adults=int(w.adults or 1),
        children=int(w.children or 0),
        infants=int(w.infants or 0),
        currency=str(w.currency or "RUB").upper(),
    )


async def _run(args: argparse.Namespace) -> int:
    if args.db:
        os.environ["DB_PATH"] = str(args.db)

    from flypingavia.config import get_settings
    from flypingavia.db.models import Watch
    from flypingavia.db.session import init_db, session_scope
    from sqlalchemy import select

    get_settings.cache_clear()
    import flypingavia.db.session as sess

    sess._engine = None
    sess._session_factory = None
    await init_db()

    async with session_scope() as session:
        result = await session.execute(
            select(Watch).where(Watch.is_active.is_(True)).order_by(Watch.id.asc())
        )
        watches = list(result.scalars().all())

    groups: dict[DupKey, list] = defaultdict(list)
    for w in watches:
        groups[_key_of(w)].append(w)

    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"active watches: {len(watches)}")
    print(f"duplicate groups: {len(dup_groups)}")

    delete_ids: list[int] = []
    for key, items in sorted(dup_groups.items(), key=lambda kv: kv[0].user_id):
        items_sorted = sorted(items, key=lambda w: (w.created_at or datetime.min, w.id))
        print("---")
        print(
            f"user={key.user_id} {key.origin}->{key.destination} "
            f"dep={key.depart_date or '-'} ret={key.return_date or '-'} "
            f"thr={key.max_price} flex=±{key.flexibility_days} "
            f"pax={key.adults}/{key.children}/{key.infants} {key.currency} "
            f"count={len(items_sorted)}"
        )
        for i, w in enumerate(items_sorted):
            mark = "KEEP" if (args.keep_oldest and i == 0) else (
                "KEEP" if (not args.keep_oldest and i == len(items_sorted) - 1) else "DUP"
            )
            print(
                f"  [{mark}] id={w.id} created_at={w.created_at} "
                f"last_price={w.last_price}"
            )
            if mark == "DUP":
                delete_ids.append(int(w.id))

    if not args.delete_duplicates:
        print("\nDry-run only. To delete: --delete-duplicates --keep-oldest")
        return 0

    if not delete_ids:
        print("Nothing to delete.")
        return 0

    if not args.keep_oldest and not args.keep_newest:
        print("Refusing delete without --keep-oldest or --keep-newest")
        return 2

    async with session_scope() as session:
        for wid in delete_ids:
            w = await session.get(Watch, wid)
            if w is not None:
                w.is_active = False
        await session.flush()

    print(f"Deactivated {len(delete_ids)} duplicate watches: {delete_ids}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Find (and optionally deactivate) watch duplicates")
    p.add_argument("--db", help="Path to SQLite DB (sets DB_PATH)")
    p.add_argument(
        "--delete-duplicates",
        action="store_true",
        help="Deactivate duplicates (default: dry-run)",
    )
    p.add_argument(
        "--keep-oldest",
        action="store_true",
        help="When deleting, keep the oldest watch in each group",
    )
    p.add_argument(
        "--keep-newest",
        action="store_true",
        help="When deleting, keep the newest watch in each group",
    )
    args = p.parse_args()
    if args.keep_oldest and args.keep_newest:
        p.error("Choose only one of --keep-oldest / --keep-newest")
    # Default keep policy for delete mode.
    if args.delete_duplicates and not args.keep_oldest and not args.keep_newest:
        args.keep_oldest = True
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
