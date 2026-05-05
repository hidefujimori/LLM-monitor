import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class RetryQueue:
    """File-based FIFO queue for failed HEC events with a configurable size cap."""

    def __init__(self, queue_dir: str, max_bytes: int = 300 * 1024 * 1024):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self._seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _files(self) -> list[Path]:
        """Queue files sorted oldest first (by filename = timestamp_seq)."""
        return sorted(self.queue_dir.glob("*.jsonl"))

    def _total_bytes(self) -> int:
        return sum(f.stat().st_size for f in self._files())

    def _evict_oldest(self, need_bytes: int) -> None:
        """Delete oldest files until there is room for need_bytes."""
        for f in self._files():
            if self._total_bytes() + need_bytes <= self.max_bytes:
                break
            logger.warning("Queue limit reached (%.1f MB), dropping %s",
                           self.max_bytes / 1024 ** 2, f.name)
            f.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push(self, events: list[dict[str, Any]]) -> None:
        """Persist a batch of events that failed to send."""
        if not events:
            return
        self._seq += 1
        data = "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n"
        encoded = data.encode()
        self._evict_oldest(len(encoded))
        path = self.queue_dir / f"{int(time.time())}_{self._seq:06d}.jsonl"
        path.write_bytes(encoded)
        logger.info("Queued %d events → %s  (queue %.1f MB / %.0f MB)",
                    len(events), path.name,
                    self._total_bytes() / 1024 ** 2, self.max_bytes / 1024 ** 2)

    def drain(self, send_fn: Callable[[list[dict[str, Any]]], bool]) -> int:
        """
        Replay queued batches oldest-first using send_fn.
        Stops at the first failure so order is preserved.
        Returns total number of events successfully replayed.
        """
        total_sent = 0
        for f in self._files():
            try:
                lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
                events = [json.loads(l) for l in lines]
            except Exception as e:
                logger.error("Corrupt queue file %s, discarding: %s", f.name, e)
                f.unlink(missing_ok=True)
                continue

            if send_fn(events):
                f.unlink(missing_ok=True)
                total_sent += len(events)
                logger.info("Replayed %d events from %s", len(events), f.name)
            else:
                logger.debug("Splunk still unreachable, stopping drain")
                break

        return total_sent

    def size_mb(self) -> float:
        return self._total_bytes() / 1024 ** 2

    def pending_batches(self) -> int:
        return len(self._files())
