"""Tests for CHANGELOG.md — enforces the one-liner house style."""

from pathlib import Path

MAX_LENGTH = 80
CHANGELOG_PATH = Path(__file__).parent.parent / "CHANGELOG.md"


class TestChangelogEntryLength:

    def test_no_entry_exceeds_80_characters(self):
        lines = CHANGELOG_PATH.read_text().splitlines()
        entries = [line for line in lines if line.startswith("- ")]
        assert entries, "expected at least one changelog entry"

        too_long = [f"{len(line)} chars: {line}" for line in entries if len(line) > MAX_LENGTH]
        assert not too_long, "CHANGELOG.md entries must be one-liners, max 80 characters:\n" + "\n".join(too_long)
