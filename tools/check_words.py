#!/usr/bin/env python3
"""Checks Talk Like Paatti word lists before they go live.

Usage:  python3 tools/check_words.py talklikepaatti/words.json talklikepaatti/words-test.json

Runs the same rules as WordSafety.swift in the app. Exits with an error (and lists every problem)
if any word is missing a field, uses an unknown topic, is too long, has an unsuitable emoji, or
contains a term from tools/blocklist.txt.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

CATEGORIES = {"greetings", "family", "food", "animals", "colors", "numbers", "body", "feelings", "everyday"}
REQUIRED = ["id", "tamil", "romanized", "sayItLike", "english", "emoji", "category"]
LIMITS = {"id": 40, "tamil": 60, "romanized": 60, "english": 80, "tip": 240}
MAX_BEATS, MAX_BEAT_LENGTH = 14, 14
BLOCKED_EMOJI = {"🍆", "🍑", "💦", "💩", "🖕", "🔞", "🍺", "🍻", "🍷", "🍸", "🥃", "🚬",
                 "💉", "💊", "🔫", "💣", "🔪", "🗡️", "☠️", "💀", "🩸", "🎰"}
ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


def load_blocklist() -> list[str]:
    path = Path(__file__).with_name("blocklist.txt")
    if not path.exists():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            terms.append(line)
    return terms


def fold(text: str) -> str:
    """Lowercase and strip accents (only used for English-letter matching)."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


def contains_term(text: str, term: str) -> bool:
    if term.isascii():
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", fold(text)) is not None
    return term in text


def emoji_ok(emoji: str) -> bool:
    if not emoji or emoji in BLOCKED_EMOJI or len(emoji) > 8:
        return False
    if any(c.isascii() and c.isalnum() for c in emoji):
        return False
    return any(ord(c) > 0x2000 for c in emoji)


def check_file(path: Path, blocklist: list[str]) -> list[str]:
    problems = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001
        return [f"{path}: not valid JSON ({error})"]

    if not isinstance(data.get("version"), int) or data["version"] < 1:
        problems.append(f"{path}: \"version\" must be a whole number of 1 or more")
    removed = data.get("removed", [])
    if not isinstance(removed, list) or not all(isinstance(x, str) for x in removed):
        problems.append(f"{path}: \"removed\" must be a list of word ids")

    seen = set()
    for index, word in enumerate(data.get("words", [])):
        label = f"{path}: word {index + 1} ({word.get('id', 'no id')})"
        for field in REQUIRED:
            value = word.get(field)
            if value is None or (isinstance(value, str) and not value.strip()) or value == []:
                problems.append(f"{label}: missing \"{field}\"")
        word_id = str(word.get("id", ""))
        if word_id and not ID_PATTERN.match(word_id):
            problems.append(f"{label}: id must be lowercase letters, numbers and _")
        if word_id in seen:
            problems.append(f"{label}: duplicate id")
        seen.add(word_id)
        if word.get("category") not in CATEGORIES:
            problems.append(f"{label}: unknown category \"{word.get('category')}\" (use one of: {', '.join(sorted(CATEGORIES))})")
        for field, limit in LIMITS.items():
            if len(str(word.get(field) or "")) > limit:
                problems.append(f"{label}: \"{field}\" is longer than {limit} characters")
        beats = word.get("sayItLike") or []
        if not isinstance(beats, list) or len(beats) > MAX_BEATS or any(len(str(b)) > MAX_BEAT_LENGTH for b in beats):
            problems.append(f"{label}: \"sayItLike\" must be a list of up to {MAX_BEATS} short beats")
        if not emoji_ok(str(word.get("emoji", ""))):
            problems.append(f"{label}: emoji must be a single, suitable emoji")
        texts = [str(word.get(f) or "") for f in ("tamil", "romanized", "english", "tip")]
        texts.append(" ".join(str(b) for b in beats) if isinstance(beats, list) else "")
        for term in blocklist:
            if any(contains_term(text, term) for text in texts):
                problems.append(f"{label}: contains a blocked term")
                break
    return problems


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]] or [Path("talklikepaatti/words.json")]
    blocklist = load_blocklist()
    problems = []
    for path in paths:
        if path.exists():
            problems += check_file(path, blocklist)
    if problems:
        print("Word list check FAILED:\n")
        print("\n".join(f"  - {p}" for p in problems))
        return 1
    print(f"Word list check passed ({', '.join(str(p) for p in paths)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
