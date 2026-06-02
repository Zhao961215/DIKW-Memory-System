"""
skill_auto_trigger.py — Auto-load skills when user message matches trigger keywords.

Scan all available skill directories for SKILL.md files, parse their frontmatter
for ``triggers`` (a list of keywords), and if the user's message contains any
trigger word, load the full skill content and return it for injection.

Usage (added to conversation_loop.py before user_msg construction)::

    from agent.skill_auto_trigger import auto_load_triggered_skills
    skill_text = auto_load_triggered_skills(user_message)
    if skill_text:
        user_message = skill_text + "\\n\\n---\\n\\n" + user_message
"""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import List, Tuple

# ── Cache ──────────────────────────────────────────────────────────────────
# Keyed on (skills_dir_hash, user_message) — rebuilt when skills change.
_TRIGGER_CACHE: dict[int, list[tuple[str, str, str]]] = {}  # hash → [(skill_name, content, triggers_str)]


def _get_home() -> Path:
    """Return the Hermes home directory (~/.hermes)."""
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def _parse_frontmatter_simple(text: str) -> dict:
    """Minimal frontmatter parser — extracts ``triggers`` and ``name`` from YAML frontmatter.

    Handles:
      - ``triggers: [记住, 保存]`` (inline array)
      - ``name: dikw-memory-flow``
    """
    result: dict = {}
    # Match content between --- markers
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return result
    body = m.group(1)
    for line in body.split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        # Parse inline array: [记住, 保存]
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip("'\"") for v in val[1:-1].split(",")]
            result[key] = items
        else:
            result[key] = val.strip("'\"")
    return result


def _scan_all_triggers() -> list[tuple[str, str, str]]:
    """Scan all skill directories and return list of (skill_name, content, triggers_str).

    Each entry represents one skill with its full SKILL.md content and
    a space-separated trigger string for fast matching.

    Results are cached in ``_TRIGGER_CACHE`` and invalidated when the
    directory modification time changes.
    """
    skills_dir = _get_home() / "skills"
    if not skills_dir.exists():
        return []

    # Simple cache key: concatenated stat mtimes
    cache_key = _build_cache_key(skills_dir)
    if cache_key in _TRIGGER_CACHE:
        return _TRIGGER_CACHE[cache_key]

    result: list[tuple[str, str, str]] = []
    for skill_file in skills_dir.rglob("SKILL.md"):
        try:
            raw = skill_file.read_text(encoding="utf-8")
            fm = _parse_frontmatter_simple(raw)
            triggers = fm.get("triggers", [])

            if not triggers:
                continue  # no trigger words → never auto-match

            name = fm.get("name", skill_file.parent.name)
            # Full skill content (including frontmatter — the agent needs to see it)
            triggers_str = " ".join(str(t).lower() for t in triggers)
            result.append((name, raw, triggers_str))
        except Exception:
            pass

    _TRIGGER_CACHE[cache_key] = result
    return result


def _build_cache_key(skills_dir: Path) -> int:
    """Build a cache key from directory stat info."""
    import stat as _stat
    key = 0
    try:
        for p in skills_dir.rglob("SKILL.md"):
            st = p.stat()
            # Mix mtime + size into a simple int
            key ^= hash((st.st_mtime_ns, st.st_size, str(p)))
    except Exception:
        pass
    return key


def auto_load_triggered_skills(user_message: str) -> str | None:
    """Check if the user's message matches any skill trigger.

    Returns the full SKILL.md content of the first matching skill,
    or None if no match is found.
    """
    if not user_message or not user_message.strip():
        return None

    msg_lower = user_message.lower()

    for name, content, triggers_str in _scan_all_triggers():
        # Check each trigger word
        for trigger in triggers_str.split():
            if not trigger:
                continue
            if trigger in msg_lower:
                # Found a match — package the skill content
                return f"[Auto-loaded skill: {name}]\n\n{content}"

    return None


def clear_trigger_cache() -> None:
    """For testing — clear the in-memory cache so ``_scan_all_triggers`` rescans."""
    _TRIGGER_CACHE.clear()
