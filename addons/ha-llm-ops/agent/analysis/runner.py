from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .context import build_context
from .llm.base import LLM
from .llm.mock import MockLLM
from .llm.openai import OpenAI
from .parse import parse_result
from .prompt_builder import build_prompt
from .storage import list_incidents
from .types import IncidentRef


class AnalysisLogger:
    """Write analysis results to rotating JSONL files."""

    def __init__(self, directory: Path, max_bytes: int = 1_000_000) -> None:
        self.directory = directory
        self.max_bytes = max_bytes
        self.directory.mkdir(parents=True, exist_ok=True)
        self._counter = 0
        self._file = self._open_file()

    def _open_file(self):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = self.directory / f"analyses_{timestamp}_{self._counter}.jsonl"
        self._counter += 1
        return path.open("a", encoding="utf-8")

    def write(self, record: dict) -> None:
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

    def _analyze(self, incident: IncidentRef) -> None:
        bundle = build_context(incident, max_lines=self.max_lines)
        prompt = build_prompt(bundle)
        raw = self.llm.generate(prompt.text, timeout=30)
        result = parse_result(raw)
        record = {"incident": str(incident.path), "result": result.model_dump()}
        self.logger.write(record)

    def run_once(self) -> None:
        now = self._now()
        if now < self._next_run:
            return
        incidents = list_incidents(self.incident_dir)
        try:
            for inc in incidents:
                if inc.path in self._processed:
                    continue
                self._analyze(inc)
                self._processed.add(inc.path)
        except Exception:  # pragma: no cover - defensive
            logging.exception("analysis failed")
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
