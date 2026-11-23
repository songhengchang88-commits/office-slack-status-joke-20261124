"""Generate entry for make.fun office-jokes competition.

Deliverable requirements:
- Python 3.13 standard library only, no third-party packages, no network.
- Resolves $MAKEFUN_OUTPUT_DIR, falling back to /output and then ./output.
- Writes one one-line joke about office life to entry.txt.
- 1 to 199 characters counted as Unicode code points, UTF-8, not only
  whitespace, exactly one line.
- Validates strictly and fails loudly (non-zero exit) if violated.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class CandidateJoke:
    """One candidate joke, with its blind-ranking position."""

    id: int
    text: str
    blind_rank: int
    rationale: str


# Blind-ranked registry (independent blind judge, top 3 of 20 candidates).
# Winner is the blind rank #1 joke; the other two stay as documented
# alternates for later blind rounds, never as the output of this version.
CANDIDATE_REGISTRY: tuple[CandidateJoke, ...] = (
    CandidateJoke(
        id=1,
        text="I set my Slack status to 'in a meeting' and my boss replied, "
        "'Great, the meeting is about why your status says that.'",
        blind_rank=1,
        rationale="Cleanest turn: the status meant to deflect becomes the "
        "reason for the meeting itself; tight, recognisable, fresh.",
    ),
    CandidateJoke(
        id=2,
        text="I wrote 'per my last email' so politely that Legal called it "
        "a threat, HR called it passive-aggressive, and my boss framed it.",
        blind_rank=2,
        rationale="Triple escalation, a different punch on each beat.",
    ),
    CandidateJoke(
        id=3,
        text="I swiped my badge twelve times before security said, 'Sir, "
        "that is the broom cupboard, and you are now its manager.'",
        blind_rank=3,
        rationale="Sharp left turn from access frustration to absurd promotion.",
    ),
)


class JokeValidator:
    """Granular per-rule validation of joke text."""

    MIN_CODE_POINTS: int = 1
    MAX_CODE_POINTS: int = 199

    @classmethod
    def check_type(cls, content: str) -> None:
        if not isinstance(content, str):
            sys.stderr.write(
                f"Validation error [type]: content is {type(content).__name__}, expected str\n"
            )
            sys.exit(1)

    @classmethod
    def check_code_points(cls, content: str) -> int:
        code_points = len(content)
        if code_points < cls.MIN_CODE_POINTS or code_points > cls.MAX_CODE_POINTS:
            sys.stderr.write(
                f"Validation error [length]: code point count {code_points} "
                f"is outside [{cls.MIN_CODE_POINTS}, {cls.MAX_CODE_POINTS}]\n"
            )
            sys.exit(1)
        return code_points

    @classmethod
    def check_whitespace(cls, content: str) -> None:
        if not content.strip():
            sys.stderr.write(
                "Validation error [whitespace]: content consists entirely of whitespace\n"
            )
            sys.exit(1)

    @classmethod
    def check_single_line(cls, content: str) -> None:
        if len(content.splitlines()) != 1:
            sys.stderr.write(
                f"Validation error [lines]: expected exactly 1 logical line, "
                f"got {len(content.splitlines())}\n"
            )
            sys.exit(1)

    @classmethod
    def check_clean_line_structure(cls, content: str) -> None:
        if "\r" in content:
            sys.stderr.write("Validation error [format]: carriage return (\\r) is forbidden\n")
            sys.exit(1)
        if "\0" in content:
            sys.stderr.write("Validation error [format]: null byte (\\0) is forbidden\n")
            sys.exit(1)
        for idx, ch in enumerate(content):
            if ord(ch) < 0x20 and ch != "\n":
                sys.stderr.write(
                    f"Validation error [control_char]: illegal control char "
                    f"U+{ord(ch):04X} at index {idx}\n"
                )
                sys.exit(1)

    @classmethod
    def check_utf8(cls, content: str) -> bytes:
        try:
            raw = content.encode("utf-8")
            if raw.decode("utf-8") != content:
                raise ValueError("UTF-8 roundtrip fidelity mismatch")
            return raw
        except Exception as exc:
            sys.stderr.write(f"Validation error [utf8]: UTF-8 encoding failure: {exc}\n")
            sys.exit(1)

    @classmethod
    def validate(cls, content: str) -> None:
        cls.check_type(content)
        cls.check_code_points(content)
        cls.check_whitespace(content)
        cls.check_single_line(content)
        cls.check_clean_line_structure(content)
        cls.check_utf8(content)


def validate_all_candidates(candidates: Sequence[CandidateJoke]) -> int:
    for cand in candidates:
        JokeValidator.validate(cand.text)
        JokeValidator.validate(f"{cand.text}\n")
    return len(candidates)


def select_best_joke(candidates: Sequence[CandidateJoke]) -> CandidateJoke:
    """Deterministically select the blind-rank #1 joke."""
    if not candidates:
        sys.stderr.write("Selection error: candidates registry is empty\n")
        sys.exit(1)
    seen_ids: set[int] = set()
    for cand in candidates:
        if cand.id in seen_ids:
            sys.stderr.write(f"Registry integrity error: duplicate candidate id #{cand.id}\n")
            sys.exit(1)
        seen_ids.add(cand.id)
    ranked = sorted(candidates, key=lambda c: (c.blind_rank, len(c.text), c.id))
    winner = ranked[0]
    if winner.blind_rank != 1:
        sys.stderr.write(
            "Selection error: blind-rank #1 joke is missing from the registry\n"
        )
        sys.exit(1)
    return winner


def resolve_output_dir() -> Path:
    env_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "").strip()
    if env_dir:
        target = Path(env_dir)
        try:
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError as exc:
            sys.stderr.write(
                f"Warning: unable to create MAKEFUN_OUTPUT_DIR ({env_dir}): {exc}\n"
            )
    try:
        sandbox_dir = Path("/output")
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        probe = sandbox_dir / ".perm_probe"
        probe.touch(exist_ok=True)
        probe.unlink(missing_ok=True)
        return sandbox_dir
    except (PermissionError, OSError):
        pass
    local_dir = Path("./output")
    local_dir.mkdir(parents=True, exist_ok=True)
    return local_dir


def write_entry(out_dir: Path, content: str) -> Path:
    JokeValidator.validate(content)
    entry_path = out_dir / "entry.txt"
    temp_path = out_dir / "entry.txt.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8", newline="") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        temp_path.replace(entry_path)
    except OSError:
        with open(entry_path, "w", encoding="utf-8", newline="") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
    written_bytes = entry_path.read_bytes()
    if written_bytes.decode("utf-8") != content:
        sys.stderr.write("Verification error: on-disk content differs from validated content\n")
        sys.exit(1)
    return entry_path


def main() -> None:
    validated_count = validate_all_candidates(CANDIDATE_REGISTRY)
    winner = select_best_joke(CANDIDATE_REGISTRY)
    entry_payload = f"{winner.text}\n"
    out_dir = resolve_output_dir()
    written_file = write_entry(out_dir, entry_payload)
    code_points = len(entry_payload)
    print(
        f"Selected joke #{winner.id} (blind rank {winner.blind_rank}, "
        f"{code_points} code points) from {validated_count} candidates -> {written_file}"
    )


if __name__ == "__main__":
    main()
