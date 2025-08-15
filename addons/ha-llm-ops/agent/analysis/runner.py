from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from .context import build_context
from .llm.base import LLM
from .llm.mock import MockLLM
from .llm.openai import OpenAI
from .parse import parse_result
from .patterns import PatternStore, validate_pattern
from .prompt_builder import build_prompt
from .storage import list_incidents
from .types import IncidentRef

LOGGER = logging.getLogger(__name__)


class AnalysisLogger:
    """Write analysis results to rotating JSONL files."""

    def __init__(self, directory: Path, max_bytes: int = 1_000_000) -> None:
        self.directory = directory
        self.max_bytes = max_bytes
        self.directory.mkdir(parents=True, exist_ok=True)
        self._counter = 0
        self._file: TextIO = self._open_file()

    def _open_file(self) -> TextIO:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = self.directory / f"analyses_{timestamp}_{self._counter}.jsonl"
        self._counter += 1
        return path.open("a", encoding="utf-8")

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, sort_keys=True)
        if self._file.tell() + len(line) + 1 > self.max_bytes:
            self._file.close()
            self._file = self._open_file()
        self._file.write(line + "\n")
        self._file.flush()


def create_llm(backend: str | None = None) -> LLM:
    """Return an ``LLM`` instance based on ``backend`` or environment."""

    if backend is None:
        backend = "OPENAI" if os.getenv("OPENAI_API_KEY") else "MOCK"
    backend = backend.upper()
    if backend == "OPENAI":
        return OpenAI()
    return MockLLM()


class AnalysisRunner:
    """Periodic incident analyzer writing results to disk."""

    def __init__(
        self,
        incident_dir: Path,
        analysis_dir: Path,
        llm: LLM,
        *,
        rate_seconds: float = 60.0,
        max_lines: int = 50,
        max_bytes: int = 1_000_000,
        now_fn: Callable[[], float] = time.monotonic,
        patterns_path: Path | None = None,
    ) -> None:
        self.incident_dir = incident_dir
        self.llm = llm
        self.rate_seconds = rate_seconds
        self.max_lines = max_lines
        self._now = now_fn
        self._next_run = 0.0
        self._backoff = 1.0
        self._processed: set[Path] = set()
        self.logger = AnalysisLogger(analysis_dir, max_bytes=max_bytes)
        if patterns_path is None:
            patterns_path = analysis_dir / "recurring.json"
        self.patterns = PatternStore(patterns_path)

    def _analyze(self, incident: IncidentRef) -> None:
        LOGGER.debug("building context for %s", incident.path)
        bundle = build_context(incident, max_lines=self.max_lines)
        LOGGER.debug(
            "context for %s has %d event(s)",
            incident.path,
            len(bundle.events),
        )
        context_text = json.dumps(bundle.events, sort_keys=True)
        matched = self.patterns.match(context_text)
        if matched:
            LOGGER.info("incident %s matched pattern %s", incident.path, matched)
            self.patterns.update(matched, incident.end)
            return
        prompt = build_prompt(bundle)
        LOGGER.debug("sending prompt to LLM for %s", incident.path)
        raw = self.llm.generate(prompt.text, timeout=30)
        LOGGER.debug("LLM response for %s: %s", incident.path, raw)
        result = parse_result(raw)
        LOGGER.debug("parsed LLM result for %s: %s", incident.path, result)
        trigger = bundle.events[-1] if bundle.events else None
        record = {
            "incident": str(incident.path),
            "result": result.model_dump(),
            "event": trigger,
        }
        self.logger.write(record)
        LOGGER.info("analysis recorded for %s", incident.path)
        pattern = result.recurrence_pattern
        if validate_pattern(pattern):
            LOGGER.debug("adding recurrence pattern for %s: %s", incident.path, pattern)
            self.patterns.add(pattern, incident.end)

    def run_once(self) -> None:
        now = self._now()
        if now < self._next_run:
            return
        LOGGER.debug("scanning incidents in %s", self.incident_dir)
        incidents = list_incidents(self.incident_dir)
        LOGGER.debug("found %d incident(s)", len(incidents))
        try:
            for inc in incidents:
                if inc.path in self._processed:
                    LOGGER.debug("skipping already processed incident %s", inc.path)
                    continue
                LOGGER.debug("processing incident %s", inc.path)
                self._analyze(inc)
                self._processed.add(inc.path)
        except Exception:  # pragma: no cover - defensive
            LOGGER.exception("analysis failed")
            self._next_run = now + self._backoff
            self._backoff = min(self._backoff * 2, 60)
            return
        self._next_run = now + self.rate_seconds
        self._backoff = 1.0

    async def run_forever(self) -> None:
        while True:
            self.run_once()
            await asyncio.sleep(max(self._next_run - self._now(), 0))


__all__ = ["AnalysisRunner", "create_llm"]
