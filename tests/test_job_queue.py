"""SQLite job queue 테스트 — enqueue/dequeue 클레임/상태 갱신."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.job_queue import JobQueue, JobStatus


@pytest.fixture
def queue(tmp_path: Path) -> JobQueue:
    q = JobQueue(str(tmp_path / "jobs.db"))
    yield q
    q.close()


def test_enqueue_then_dequeue_fifo(queue: JobQueue) -> None:
    first = queue.enqueue("logs", {"service": "api"})
    queue.enqueue("ping", {})

    claimed = queue.dequeue()
    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.command == "logs"
    assert claimed.payload == {"service": "api"}
    assert claimed.status == JobStatus.RUNNING


def test_dequeue_empty_returns_none(queue: JobQueue) -> None:
    assert queue.dequeue() is None


def test_dequeue_claims_atomically(queue: JobQueue) -> None:
    """클레임된 작업(RUNNING)은 다시 dequeue 되지 않는다."""
    queue.enqueue("ping", {})
    assert queue.dequeue() is not None
    assert queue.dequeue() is None


def test_update_status(queue: JobQueue) -> None:
    job = queue.enqueue("ping", {})
    queue.update_status(job.id, JobStatus.DONE)
    # DONE 이므로 dequeue 대상 아님
    assert queue.dequeue() is None


def test_update_status_unknown_job(queue: JobQueue) -> None:
    with pytest.raises(KeyError):
        queue.update_status("no-such-id", JobStatus.FAILED)
