#!/usr/bin/env python3
"""Insert a Telegram ID or email into blacklist.txt at its sorted position."""

import bisect
import re
import sys
import urllib.request
from itertools import pairwise
from pathlib import Path

BLACKLIST = Path(__file__).resolve().parent.parent / "blacklist.txt"
EMAIL_RE = re.compile(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+")


def entry_key(value: str) -> tuple[int, int | str]:
    """Sort key: Telegram IDs ascending first, then emails alphabetically."""
    value = value.strip().lower()
    if value.isascii() and value.isdigit():
        return (0, int(value))
    if EMAIL_RE.fullmatch(value):
        return (1, value)
    raise ValueError(f"not a Telegram ID or email: {value!r}")


def line_key(line: str) -> tuple[int, int | str]:
    return entry_key(line.split("#", 1)[0])


def add_entry(lines: list[str], entry: str, reason: str) -> list[str]:
    header = [l for l in lines if l.lstrip().startswith("#")]
    entries = [l for l in lines if not l.lstrip().startswith("#")]

    key = entry_key(entry)
    keys = [line_key(l) for l in entries]
    if key in keys:
        raise ValueError(f"{key[1]} is already in the list")

    pos = bisect.bisect_left(keys, key)
    new_line = f"{key[1]} # {reason}\n" if reason else f"{key[1]}\n"
    entries.insert(pos, new_line)
    return header + entries


def check_order(lines: list[str]) -> int:
    """Print out-of-order and duplicate entries. Returns an exit code."""
    entries = [l for l in lines if not l.lstrip().startswith("#")]
    keys = [line_key(l) for l in entries]

    disorder = [(a[1], b[1]) for a, b in pairwise(keys) if a > b]
    dupes = sorted({k for k in keys if keys.count(k) > 1})

    if not disorder and not dupes:
        print(f"ok: {len(keys)} entries, sorted, no duplicates")
        return 0

    if disorder:
        print(f"out of order: {len(disorder)}")
        for a, b in disorder:
            print(f"  {a} -> {b}")
    if dupes:
        print(f"duplicates: {len(dupes)}")
        for k in dupes:
            print(f"  {k[1]}")
    return 1


def strip_mentions(reason: str) -> str:
    reason = re.sub(r"@[A-Za-z0-9_]+\s*", "", reason)
    return re.sub(r"\s+", " ", reason).strip()


def parse_list(text: str) -> dict[tuple[int, int | str], str]:
    """Parse an entry-per-line list (`entry` or `entry # reason`) into {key: reason}."""
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        value, _, reason = line.partition("#")
        try:
            key = entry_key(value)
        except ValueError:
            continue
        result[key] = strip_mentions(reason.strip())
    return result


def merge_missing(
    lines: list[str], other: dict[tuple[int, int | str], str]
) -> tuple[list[str], int]:
    """Append entries from `other` missing in `lines`, keep the file sorted."""
    header = [l for l in lines if l.lstrip().startswith("#")]
    entries = [l for l in lines if not l.lstrip().startswith("#")]
    keys = {line_key(l) for l in entries}

    missing = {key: reason for key, reason in other.items() if key not in keys}
    for key, reason in missing.items():
        entries.append(f"{key[1]} # {reason}\n" if reason else f"{key[1]}\n")

    entries.sort(key=line_key)
    return header + entries, len(missing)


def sync(url: str) -> None:
    with urllib.request.urlopen(url) as r:
        text = r.read().decode("utf-8")
    other = parse_list(text)

    lines = BLACKLIST.read_text(encoding="utf-8").splitlines(keepends=True)
    lines, added = merge_missing(lines, other)
    BLACKLIST.write_text("".join(lines), encoding="utf-8")
    print(f"added {added} entries from {len(other)} in source")


def selftest() -> None:
    lines = ["# header\n", "1 # a\n", "5 # b\n", "10 # c\n"]
    result = add_entry(lines, "7", "test")
    assert result == ["# header\n", "1 # a\n", "5 # b\n", "7 # test\n", "10 # c\n"], (
        result
    )
    for dup in ("5", "a@x.io"):
        try:
            add_entry(lines + ["a@x.io\n"], dup, "dup")
            assert False, "duplicate was not caught"
        except ValueError:
            pass

    result = add_entry(["2\n", "b@x.io\n"], "A@x.io", "")
    assert result == ["2\n", "a@x.io\n", "b@x.io\n"], result
    assert add_entry(["b@x.io\n"], "3", "") == ["3\n", "b@x.io\n"]
    try:
        add_entry([], "not-an-entry", "")
        assert False, "garbage was not rejected"
    except ValueError:
        pass

    assert check_order(["1\n", "2\n", "3\n"]) == 0
    assert check_order(["2\n", "1\n"]) == 1
    assert check_order(["1\n", "1\n"]) == 1
    assert check_order(["9\n", "a@x.io\n", "b@x.io\n"]) == 0
    assert check_order(["a@x.io\n", "9\n"]) == 1

    assert strip_mentions("@user hello") == "hello"
    assert parse_list("# h\n1 # @user a\n2\nE@x.io # e\n") == {
        (0, 1): "a",
        (0, 2): "",
        (1, "e@x.io"): "e",
    }

    merged, added = merge_missing(
        ["# h\n", "1 # a\n", "5 # b\n"], {(0, 1): "x", (0, 3): "c", (1, "e@x.io"): ""}
    )
    assert added == 2
    assert merged == ["# h\n", "1 # a\n", "3 # c\n", "5 # b\n", "e@x.io\n"], merged

    print("selftest ok")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        selftest()
        return

    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        lines = BLACKLIST.read_text(encoding="utf-8").splitlines(keepends=True)
        sys.exit(check_order(lines))

    if len(sys.argv) == 3 and sys.argv[1] == "--sync":
        sync(sys.argv[2])
        return

    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        sys.exit("Usage: add_ban.py <telegram_id|email> [reason] | --check | --sync <url>")

    entry = sys.argv[1]
    reason = " ".join(sys.argv[2:])

    lines = BLACKLIST.read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        lines = add_entry(lines, entry, reason)
    except ValueError as e:
        sys.exit(str(e))

    BLACKLIST.write_text("".join(lines), encoding="utf-8")
    print(f"Added: {entry_key(entry)[1]} # {reason}")


if __name__ == "__main__":
    main()
