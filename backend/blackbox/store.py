"""Incident persistence + live event fan-out.

Every mutation persists the full state to data/incidents/{id}.json and pushes a
snapshot to all subscribed SSE queues. Snapshots (not deltas) keep the UI
idempotent and reconnect-safe.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

from .config import settings
from .models import IncidentStage, IncidentState, now_iso


class IncidentStore:
    def __init__(self, root: Path | None = None):
        self.root = root or settings.incidents_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self._states: dict[str, IncidentState] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called once from FastAPI startup so worker threads can publish."""
        self._loop = loop

    # -- persistence ----------------------------------------------------------

    def _path(self, incident_id: str) -> Path:
        return self.root / f"{incident_id}.json"

    def save(self, state: IncidentState) -> None:
        state.updated_at = now_iso()
        with self._lock:
            self._states[state.id] = state
            tmp = self._path(state.id).with_suffix(".json.tmp")
            tmp.write_text(state.model_dump_json(indent=2))
            tmp.replace(self._path(state.id))
        self._publish(state)

    def get(self, incident_id: str) -> IncidentState | None:
        with self._lock:
            if incident_id in self._states:
                return self._states[incident_id]
        p = self._path(incident_id)
        if p.exists():
            state = IncidentState.model_validate_json(p.read_text())
            with self._lock:
                self._states[incident_id] = state
            return state
        return None

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("inc_*.json"))

    def latest(self) -> IncidentState | None:
        ids = self.list_ids()
        if not ids:
            return None
        states = [s for i in ids if (s := self.get(i)) is not None]
        return max(states, key=lambda s: s.created_at) if states else None

    def clear_all(self) -> int:
        """Demo reset: forget all incidents."""
        with self._lock:
            n = len(list(self.root.glob("inc_*.json")))
            for p in self.root.glob("inc_*.json"):
                p.unlink()
            self._states.clear()
        return n

    # -- live events ----------------------------------------------------------

    def subscribe(self, incident_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.setdefault(incident_id, []).append(q)
        return q

    def unsubscribe(self, incident_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(incident_id, [])
        if q in subs:
            subs.remove(q)

    def _publish(self, state: IncidentState) -> None:
        subs = self._subscribers.get(state.id, [])
        if not subs or self._loop is None:
            return
        payload = state.model_dump_json()

        def _push() -> None:
            for q in list(subs):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass  # slow consumer; it will re-sync from the next snapshot

        self._loop.call_soon_threadsafe(_push)

    # -- guarded stage transitions ---------------------------------------------

    def advance(self, state: IncidentState, target: IncidentStage) -> None:
        if not state.can_advance_to(target):
            raise ValueError(f"illegal stage transition {state.stage} -> {target}")
        state.stage = target
        self.save(state)


store = IncidentStore()
