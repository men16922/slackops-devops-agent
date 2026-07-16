"""관측된 도구 호출 — allowlist 는 무엇이 허용되는지만 말한다.

stream-json 이벤트에서 실제 tool_use/tool_result 를 복원하고, 그것이 감사 궤적의
자식 스텝과 capability 재집계로 이어지는지 검증한다. 실제 이벤트 모양은
Claude Code 2.1.210 실행에서 측정한 것이다.
"""

from __future__ import annotations

import json

import pytest

from app.claude_runner import ToolCall, _parse_result
from app.command_guard import CommandGuardError, resolve_tool
from app.execution_plan import capabilities_for_tools, risk_score
from app.store import SqliteAuditStore, SqliteJobStore, SqliteTelemetryStore, result_digest
from app.store import JobSource, build_step_tree
from app.worker import AUDIT_TOOL_CALL, CommandOutcome, Worker
from tests._helpers import counter_clock, counter_id


def _stream(*events: dict[str, object]) -> str:
    return "\n".join(json.dumps(e) for e in events)


def _tool_use(use_id: str, command: str) -> dict[str, object]:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": use_id,
                    "name": "Bash",
                    "input": {"command": command, "description": "d"},
                }
            ]
        },
    }


def _tool_result(use_id: str, content: str, is_error: bool = False) -> dict[str, object]:
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": use_id, "content": content, "is_error": is_error}
            ]
        },
    }


def _result(text: str = "done") -> dict[str, object]:
    return {
        "type": "result",
        "result": text,
        "total_cost_usd": 0.02,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


class TestStreamParsing:
    def test_tool_use_pairs_with_its_result(self) -> None:
        stdout = _stream(
            _tool_use("toolu_1", "git status --porcelain"),
            _tool_result("toolu_1", "A  x.py"),
            _result("all good"),
        )
        parsed = _parse_result(0, stdout, "")
        assert parsed.output == "all good"
        assert parsed.tokens == 15 and parsed.cost_usd == 0.02
        assert parsed.tool_calls == (
            ToolCall(
                tool_use_id="toolu_1",
                name="Bash",
                command="git status --porcelain",
                result_hash=result_digest("A  x.py"),
                is_error=False,
            ),
        )

    def test_order_is_preserved(self) -> None:
        stdout = _stream(
            _tool_use("t1", "git status"),
            _tool_result("t1", "a"),
            _tool_use("t2", "git diff --stat"),
            _tool_result("t2", "b"),
            _result(),
        )
        assert [c.command for c in _parse_result(0, stdout, "").tool_calls] == [
            "git status",
            "git diff --stat",
        ]

    def test_tool_error_is_recorded(self) -> None:
        stdout = _stream(
            _tool_use("t1", "git status"), _tool_result("t1", "boom", True), _result()
        )
        (call,) = _parse_result(0, stdout, "").tool_calls
        assert call.is_error is True

    def test_tool_use_without_result_still_appears(self) -> None:
        # 결과가 없다고 호출 사실을 지우면 안 된다 — 궤적에 구멍이 생긴다.
        stdout = _stream(_tool_use("t1", "git status"), _result())
        (call,) = _parse_result(0, stdout, "").tool_calls
        assert call.command == "git status" and call.result_hash == ""

    def test_single_json_object_still_parses(self) -> None:
        # 실행기를 주입하는 테스트는 예전 `--output-format json` 모양을 그대로 쓴다 —
        # 파서가 한쪽만 알면 mock 과 실물이 갈라진다.
        parsed = _parse_result(0, json.dumps({"result": "ok", "total_cost_usd": 0.01}), "")
        assert parsed.output == "ok" and parsed.tool_calls == ()

    def test_non_json_falls_back_to_raw_text(self) -> None:
        assert _parse_result(1, "", "boom").output == "boom"


class TestObservedCapability:
    def test_observed_argv_resolves_to_the_declared_tool(self) -> None:
        assert resolve_tool("pr", "git push -u origin feat/x") == "Bash(git push:*)"
        assert resolve_tool("pr", "git status --porcelain") == "Bash(git status:*)"

    def test_unauthorized_argv_does_not_resolve(self) -> None:
        with pytest.raises(CommandGuardError):
            resolve_tool("pr", "curl http://evil")

    def test_capability_is_recomputed_from_what_actually_ran(self) -> None:
        # 정적 allowlist 는 pr 에 write-low 를 허용하지만, 읽기만 돌았다면 관측 capability 는
        # read 뿐이어야 한다 — 이것이 D20 의 "정적 집계" 한계를 메우는 지점이다.
        observed = tuple(sorted({resolve_tool("pr", c) for c in ("git status", "git diff")}))
        caps = capabilities_for_tools(observed)
        assert caps == ("read",)
        assert risk_score(caps) < risk_score(capabilities_for_tools(("Bash(git push:*)",)))


class TestWorkerTrajectory:
    def _worker(self, outcome: CommandOutcome):
        jobs = SqliteJobStore(clock=counter_clock(), id_factory=counter_id())
        audit = SqliteAuditStore(clock=counter_clock())
        metrics = SqliteTelemetryStore(clock=counter_clock())
        worker = Worker(jobs, audit, metrics, executors={"pr": lambda _job: outcome})
        return jobs, audit, worker

    def test_each_observed_call_becomes_a_child_step(self) -> None:
        outcome = CommandOutcome(
            result="opened",
            tool_steps=(
                ToolCall("t1", "Bash", "git status --porcelain", result_digest("A x"), False),
                ToolCall("t2", "Bash", "git push -u origin feat/x", result_digest("ok"), False),
            ),
        )
        jobs, audit, worker = self._worker(outcome)
        job = jobs.enqueue("pr", args="fix", source=JobSource.SLACK)
        worker.process_one()

        events = audit.list_for_job(job.id)
        tool_steps = [e for e in events if e.action == AUDIT_TOOL_CALL]
        assert [e.tool_name for e in tool_steps] == [
            "Bash(git status:*)",
            "Bash(git push:*)",
        ]
        # 실제 도구 호출이 claim(루트) 아래 자식으로 달린다.
        tree = build_step_tree(events)
        root = tree[""][0]
        assert {e.step_id for e in tool_steps} <= {e.step_id for e in tree[root.step_id]}
        # 결과 본문은 남기지 않고 해시만 남는다.
        assert tool_steps[0].result_hash == result_digest("A x")

    def test_done_step_carries_observed_capabilities(self) -> None:
        outcome = CommandOutcome(
            result="opened",
            tool_steps=(ToolCall("t1", "Bash", "git status", result_digest("A x"), False),),
        )
        jobs, audit, worker = self._worker(outcome)
        job = jobs.enqueue("pr", args="fix", source=JobSource.SLACK)
        worker.process_one()

        done = [e for e in audit.list_for_job(job.id) if e.action == "done"][0]
        assert done.capabilities == ("read",)

    def test_unresolvable_command_is_kept_not_erased(self) -> None:
        # guard 를 통과한 것만 실행됐어야 한다. 그래도 해석 불가한 명령줄이 나오면
        # 감사에서 지우는 것이 아니라 있는 그대로 드러내야 한다.
        outcome = CommandOutcome(
            result="x", tool_steps=(ToolCall("t1", "Bash", "curl http://evil", "", False),)
        )
        jobs, audit, worker = self._worker(outcome)
        job = jobs.enqueue("pr", args="fix", source=JobSource.SLACK)
        worker.process_one()

        step = [e for e in audit.list_for_job(job.id) if e.action == AUDIT_TOOL_CALL][0]
        assert step.tool_name == "unresolved:Bash"
        assert step.detail == "curl http://evil"


class TestCapabilityDriftGate:
    """관측 capability 는 기록이 아니라 게이트다 — 넘으면 job 이 실패해야 한다."""

    def _run(self, outcome: CommandOutcome, command: str = "pr"):
        jobs = SqliteJobStore(clock=counter_clock(), id_factory=counter_id())
        audit = SqliteAuditStore(clock=counter_clock())
        metrics = SqliteTelemetryStore(clock=counter_clock())
        worker = Worker(jobs, audit, metrics, executors={command: lambda _job: outcome})
        job = jobs.enqueue(command, args="fix", source=JobSource.SLACK)
        final = worker.process_one()
        return job, audit, final

    def test_authorized_calls_pass(self) -> None:
        from app.store import JobStatus

        outcome = CommandOutcome(
            result="ok",
            tool_steps=(ToolCall("t1", "Bash", "git status --porcelain", "", False),),
        )
        _job, _audit, final = self._run(outcome)
        # 정상 경로에서 게이트는 조용하다 — 상시 거부로 퇴화하지 않았는지 확인.
        assert final is not None and final.status is JobStatus.DONE

    def test_unauthorized_argv_fails_the_job(self) -> None:
        from app.store import JobStatus
        from app.worker import AUDIT_CAPABILITY_DRIFT

        # guard 를 우회해 실행된 것이 관측되면, 기록만 하고 넘어가면 안 된다.
        outcome = CommandOutcome(
            result="ok", tool_steps=(ToolCall("t1", "Bash", "curl http://evil", "", False),)
        )
        job, audit, final = self._run(outcome)
        assert final is not None and final.status is JobStatus.FAILED
        drift = [e for e in audit.list_for_job(job.id) if e.action == AUDIT_CAPABILITY_DRIFT]
        assert len(drift) == 1
        assert "does not authorize" in drift[0].context["reason"]

    def test_drift_still_records_what_ran(self) -> None:
        # 실패해도 궤적에 구멍이 생기면 안 된다.
        outcome = CommandOutcome(
            result="ok", tool_steps=(ToolCall("t1", "Bash", "curl http://evil", "", False),)
        )
        job, audit, _final = self._run(outcome)
        steps = [e for e in audit.list_for_job(job.id) if e.action == AUDIT_TOOL_CALL]
        assert [e.detail for e in steps] == ["curl http://evil"]

    def test_guard_denied_call_is_not_drift(self) -> None:
        from app.store import JobStatus
        from app.worker import AUDIT_CAPABILITY_DRIFT

        # The PreToolUse guard denies a compound `a && b` (unresolvable), recorded
        # with is_error=True but never run — the model then retries with an
        # authorized call. A blocked call must not fail the job for the guard doing
        # its job; drift is only for a call that bypassed the guard and ran.
        outcome = CommandOutcome(
            result="ok",
            tool_steps=(
                ToolCall("t1", "Bash", "git status --porcelain && git branch", "", True),
                ToolCall("t2", "Bash", "git status --porcelain", "", False),
            ),
        )
        job, audit, final = self._run(outcome)
        assert final is not None and final.status is JobStatus.DONE
        assert not [
            e for e in audit.list_for_job(job.id) if e.action == AUDIT_CAPABILITY_DRIFT
        ]
        # the blocked call is still in the trajectory (tamper-evidence)
        steps = [e.detail for e in audit.list_for_job(job.id) if e.action == AUDIT_TOOL_CALL]
        assert "git status --porcelain && git branch" in steps

    def test_capability_outside_the_authorized_set_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.store import JobStatus

        # tf-review 는 read 만 인가된다. write 도구가 관측되면 초과다.
        monkeypatch.setattr(
            "app.command_guard.resolve_tool", lambda _c, _l: "Bash(git push:*)"
        )
        outcome = CommandOutcome(
            result="ok", tool_steps=(ToolCall("t1", "Bash", "terraform plan", "", False),)
        )
        _job, _audit, final = self._run(outcome, command="tf-review")
        assert final is not None and final.status is JobStatus.FAILED
