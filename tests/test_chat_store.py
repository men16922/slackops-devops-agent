"""ChatStore 테스트 — Sqlite 와 DynamoDb(moto) 구현을 같은 케이스로 동치 검증.

대화 버스 전체 흐름: 생성 → 사용자 turn(AWAITING_AGENT) → 에이전트 claim(STREAMING, 중복 None)
→ assistant 메시지 스트리밍 청크 append → finish_turn(OPEN + proposed_job 링크). 단일테이블
공존(JOB# 과 CHAT# SK 분리)도 암묵 검증. 실 AWS 호출 없음(moto).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from app.store import (
    ChatRole,
    ChatStatus,
    Conversation,
    DynamoDbChatStore,
    SqliteChatStore,
)

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

TABLE_NAME = "slackops-agent-test"


def _dynamo_resource() -> object:
    import boto3

    from tests._helpers import create_single_table

    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    create_single_table(ddb, TABLE_NAME)
    return ddb


@pytest.fixture
def chat_store(request: pytest.FixtureRequest) -> Iterator[object]:
    from tests._helpers import counter_clock, counter_id

    if request.param == "sqlite":
        s = SqliteChatStore(":memory:", clock=counter_clock(), id_factory=counter_id())
        yield s
        s.close()
    else:
        from moto import mock_aws

        with mock_aws():
            yield DynamoDbChatStore(
                TABLE_NAME,
                dynamodb=_dynamo_resource(),
                clock=counter_clock(),
                id_factory=counter_id(),
            )


def _both(fn: object) -> object:
    return pytest.mark.parametrize("chat_store", ["sqlite", "dynamo"], indirect=True)(fn)


@_both
def test_create_conversation_open(chat_store: object) -> None:
    conv = chat_store.create_conversation()
    assert isinstance(conv, Conversation)
    assert conv.status is ChatStatus.OPEN
    assert chat_store.get_conversation(conv.id) == conv


@_both
def test_user_message_sets_awaiting(chat_store: object) -> None:
    conv = chat_store.create_conversation()
    msg = chat_store.append_user_message(conv.id, "api 로그 좀 봐줘")
    assert msg is not None
    assert (msg.role, msg.content, msg.done, msg.seq) == (
        ChatRole.USER,
        "api 로그 좀 봐줘",
        True,
        0,
    )
    refreshed = chat_store.get_conversation(conv.id)
    assert refreshed is not None and refreshed.status is ChatStatus.AWAITING_AGENT


@_both
def test_claim_is_atomic(chat_store: object) -> None:
    conv = chat_store.create_conversation()
    chat_store.append_user_message(conv.id, "hi")
    claimed = chat_store.claim_conversation()
    assert claimed is not None and claimed.id == conv.id
    assert claimed.status is ChatStatus.STREAMING
    # 두 번째 claim 은 대상 없음(이미 STREAMING).
    assert chat_store.claim_conversation() is None


@_both
def test_streaming_chunks_accumulate_and_finish(chat_store: object) -> None:
    conv = chat_store.create_conversation()
    chat_store.append_user_message(conv.id, "진단해줘")
    chat_store.claim_conversation()

    amsg = chat_store.start_assistant_message(conv.id)
    assert amsg.role is ChatRole.ASSISTANT and amsg.done is False and amsg.seq == 1
    chat_store.append_chunk(conv.id, amsg.seq, "## 진단\n")
    chat_store.append_chunk(conv.id, amsg.seq, "원인은 자격증명.")

    msgs = chat_store.list_messages(conv.id)
    assert [m.role for m in msgs] == [ChatRole.USER, ChatRole.ASSISTANT]
    assert msgs[1].content == "## 진단\n원인은 자격증명."
    assert msgs[1].done is False

    conv2 = chat_store.finish_turn(
        conv.id, amsg.seq, status=ChatStatus.OPEN, proposed_job_id="job-99"
    )
    assert conv2 is not None
    assert conv2.status is ChatStatus.OPEN
    assert conv2.proposed_job_id == "job-99"
    assert chat_store.list_messages(conv.id)[1].done is True


@_both
def test_append_rejected_while_streaming(chat_store: object) -> None:
    conv = chat_store.create_conversation()
    chat_store.append_user_message(conv.id, "first")
    chat_store.claim_conversation()  # → STREAMING
    # 스트리밍 중에는 사용자 turn 적재 거부(가드).
    assert chat_store.append_user_message(conv.id, "second") is None


@_both
def test_multi_turn_seq_monotonic(chat_store: object) -> None:
    conv = chat_store.create_conversation()
    chat_store.append_user_message(conv.id, "turn1")
    chat_store.claim_conversation()
    a1 = chat_store.start_assistant_message(conv.id)
    chat_store.finish_turn(conv.id, a1.seq, status=ChatStatus.OPEN)
    # 두 번째 턴.
    u2 = chat_store.append_user_message(conv.id, "turn2")
    assert u2 is not None and u2.seq == 2
    chat_store.claim_conversation()
    a2 = chat_store.start_assistant_message(conv.id)
    assert a2.seq == 3
    seqs = [m.seq for m in chat_store.list_messages(conv.id)]
    assert seqs == [0, 1, 2, 3]
