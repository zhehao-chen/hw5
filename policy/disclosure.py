"""The disclosure line (Part D): every comment RepoMind posts tells its readers that an
automated agent wrote it, and how to reach a person.

The way adds the line in code (ways/planned.py, after the second pass), never by
asking the model; the hook refuses any post_comment whose body lacks it. The comment's
first two lines, label: and file:, stay first; the line comes after them.
"""

from __future__ import annotations

LINE = ("Written by RepoMind, an automated AI agent, not a person. "
        "To reach a person, mention a Ledgerline maintainer in a reply.")


def carries(body: str) -> bool:
    """True when a line after the first two is the disclosure line, exactly."""
    return any(row.strip() == LINE for row in str(body or "").splitlines()[2:])


def with_line(body: str) -> str:
    """The body with the line right after its first two lines; unchanged if it has it."""
    if carries(body):
        return body
    rows = str(body or "").splitlines()
    head, rest = rows[:2], rows[2:]
    while rest and not rest[0].strip():
        rest = rest[1:]
    return "\n".join(head + ["", LINE] + ([""] + rest if rest else []))
