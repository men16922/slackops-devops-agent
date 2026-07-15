"""audit trajectory — 최종 응답이 아니라 실행 궤적을 감사한다.

한 job 의 이벤트가 부모/자식으로 재구성되고, 각 스텝이 "무엇이 무슨 권한으로 어디에
무엇을 반환했는지"를 결과 본문 없이 고정하는지 검증한다.
"""

from __future__ import annotations

from app.store import SqliteAuditStore, build_step_tree, result_digest
from app.store.audit_store import AuditEvent, event_hash, verify_event_chain
from tests._helpers import counter_clock


def _store() -> SqliteAuditStore:
    return SqliteAuditStore(clock=counter_clock())


class TestTrajectoryFields:
    def test_step_id_is_assigned_by_the_store(self) -> None:
        audit = _store()
        first = audit.append("job-1", "claimed")
        second = audit.append("job-1", "done", parent_step_id=first.step_id)
        # 호출자가 정하지 않는다 — 스텝 식별자를 위조해 부모를 바꿀 수 없다.
        assert first.step_id and second.step_id != first.step_id

    def test_fields_round_trip_through_sqlite(self) -> None:
        audit = _store()
        audit.append(
            "job-1",
            "done",
            tool_name="gh pr create",
            capabilities=("read", "write-low"),
            target_resource="repo:o/r",
            result_hash=result_digest("PR opened"),
        )
        (event,) = audit.list_for_job("job-1")
        assert event.tool_name == "gh pr create"
        assert event.capabilities == ("read", "write-low")
        assert event.target_resource == "repo:o/r"
        assert event.result_hash == result_digest("PR opened")

    def test_result_hash_proves_the_body_without_storing_it(self) -> None:
        audit = _store()
        audit.append("job-1", "done", result_hash=result_digest("secret output"))
        (event,) = audit.list_for_job("job-1")
        assert "secret output" not in str(event.__dict__)
        assert event.result_hash == result_digest("secret output")
        assert event.result_hash != result_digest("secret outpu")


class TestStepTree:
    def test_events_reconstruct_as_a_tree(self) -> None:
        audit = _store()
        root = audit.append("job-1", "claimed")
        approval = audit.append("job-1", "awaiting_approval", parent_step_id=root.step_id)
        grant = audit.append(
            "job-1", "write_credentials_issued", parent_step_id=approval.step_id
        )
        tree = build_step_tree(audit.list_for_job("job-1"))

        assert [e.step_id for e in tree[""]] == [root.step_id]
        assert [e.step_id for e in tree[root.step_id]] == [approval.step_id]
        # 실 push 를 그것을 허가한 승인으로 되짚을 수 있다.
        assert [e.step_id for e in tree[approval.step_id]] == [grant.step_id]

    def test_pre_trajectory_events_are_not_silently_reparented(self) -> None:
        legacy = AuditEvent(job_id="job-1", ts="t", seq=1, action="done")
        assert build_step_tree([legacy]) == {}


class TestHashBackCompat:
    def test_trajectory_fields_are_covered_by_the_hash(self) -> None:
        audit = _store()
        event = audit.append("job-1", "done", tool_name="gh pr create")
        assert verify_event_chain([event])
        # 도구 이름을 갈아끼우면 체인이 깨져야 한다.
        event.tool_name = "rm -rf"
        assert not verify_event_chain([event])

    def test_events_without_trajectory_hash_exactly_as_before(self) -> None:
        # 스키마가 늘었다고 DynamoDB 에 이미 있는 과거 체인이 무효가 되면 안 된다 —
        # 그러면 tamper-evidence 자체가 쓸모없어진다.
        legacy = AuditEvent(
            job_id="job-1", ts="2026-01-01T00:00:00Z", seq=1, action="done", actor="worker"
        )
        import hashlib
        import json

        expected = hashlib.sha256(
            json.dumps(
                {
                    "job_id": "job-1",
                    "ts": "2026-01-01T00:00:00Z",
                    "seq": 1,
                    "action": "done",
                    "actor": "worker",
                    "detail": "",
                    "context": {},
                    "prev_event_hash": "",
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        assert event_hash(legacy) == expected

    def test_chain_still_links_across_the_schema_change(self) -> None:
        audit = _store()
        first = audit.append("job-1", "claimed")
        second = audit.append("job-1", "done", parent_step_id=first.step_id)
        assert second.prev_event_hash == first.event_hash
        assert verify_event_chain([first, second])
