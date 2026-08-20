#!/usr/bin/env python3
"""Insert an ID into blacklist.txt at its sorted position (ascending)."""

import bisect
import sys
from itertools import pairwise
from pathlib import Path

BLACKLIST = Path(__file__).resolve().parent.parent / "blacklist.txt"


def add_entry(lines: list[str], user_id: int, reason: str) -> list[str]:
    header = [l for l in lines if l.lstrip().startswith("#")]
    entries = [l for l in lines if not l.lstrip().startswith("#")]

    ids = [int(l.split("#", 1)[0].strip()) for l in entries]
    if user_id in ids:
        raise ValueError(f"{user_id} is already in the list")

    pos = bisect.bisect_left(ids, user_id)
    new_line = f"{user_id} # {reason}\n" if reason else f"{user_id}\n"
    entries.insert(pos, new_line)
    return header + entries


def check_order(lines: list[str]) -> int:
    """Print out-of-order and duplicate IDs. Returns an exit code."""
    entries = [l for l in lines if not l.lstrip().startswith("#")]
    ids = [int(l.split("#", 1)[0].strip()) for l in entries]

    disorder = [(a, b) for a, b in pairwise(ids) if a > b]
    dupes = sorted({i for i in ids if ids.count(i) > 1})

    if not disorder and not dupes:
        print(f"ok: {len(ids)} ids, sorted, no duplicates")
        return 0

    if disorder:
        print(f"out of order: {len(disorder)}")
        for a, b in disorder:
            print(f"  {a} -> {b}")
    if dupes:
        print(f"duplicates: {len(dupes)}")
        for i in dupes:
            print(f"  {i}")
    return 1


def selftest() -> None:
    lines = ["# header\n", "1 # a\n", "5 # b\n", "10 # c\n"]
    result = add_entry(lines, 7, "test")
    assert result == ["# header\n", "1 # a\n", "5 # b\n", "7 # test\n", "10 # c\n"], (
        result
    )
    try:
        add_entry(lines, 5, "dup")
        assert False, "duplicate was not caught"
    except ValueError:
        pass

    assert check_order(["1\n", "2\n", "3\n"]) == 0
    assert check_order(["2\n", "1\n"]) == 1
    assert check_order(["1\n", "1\n"]) == 1

    print("selftest ok")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        selftest()
        return

    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        lines = BLACKLIST.read_text(encoding="utf-8").splitlines(keepends=True)
        sys.exit(check_order(lines))

    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        sys.exit("Usage: add_ban.py <telegram_id> [reason]")

    user_id = int(sys.argv[1])
    reason = " ".join(sys.argv[2:])

    lines = BLACKLIST.read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        lines = add_entry(lines, user_id, reason)
    except ValueError as e:
        sys.exit(str(e))

    BLACKLIST.write_text("".join(lines), encoding="utf-8")
    print(f"Added: {user_id} # {reason}")


if __name__ == "__main__":
    main()
