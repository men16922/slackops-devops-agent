"""ChatStore — web↔에이전트 비동기 대화 버스(단일테이블 공유).

web 이 사용자 turn 을 쓰면(status=AWAITING_AGENT), 에이전트(outbound-only)가 DynamoDB 를
폴링·claim 해 Claude 를 스트리밍 실행하고 assistant 메시지에 청크를 append 한다. web 은 메시지를
폴링해 자라나는 응답을 렌더한다. 에이전트가 인바운드 포트를 열지 않으므로 Socket Mode 불변 유지.

단일테이블 키(JOB#/AUDIT# 규약과 일관, 새 GSI 불필요 — 기존 GSI1 오버로딩):
  대화 메타  PK=CHAT#{conv}  SK=META        GSI1=CHATSTATUS#{status}/{updated_at}  GSI2=CHATFEED/{created_at}
  메시지     PK=CHAT#{conv}  SK=MSG#{seq:06d}

DynamoDB 는 문자열 attribute 의 in-place append 가 없어 청크를 list(`chunks`)로 list_append 하고
읽을 때 join 한다(Sqlite 는 content 문자열 `||` concat — 외부로는 둘 다 Message.content 동일).
boto3 는 lazy import — 미설치 환경 import-safe.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from app.store._util import utcnow_iso as _utcnow_iso

META_SK = "META"
CHATFEED_PK = "CHATFEED"
_CLAIM_SCAN_LIMIT = 10


class ChatStatus(str, Enum):
    """대화 상태머신. OPEN ⇄ AWAITING_AGENT → STREAMING → OPEN | DONE."""

    OPEN = "open"  # 다음 사용자 입력 대기
    AWAITING_AGENT = "awaiting_agent"  # 사용자 입력됨 → 에이전트가 claim 해야 함
    STREAMING = "streaming"  # 에이전트가 Claude 스트리밍 중
    DONE = "done"  # 종료


# 에이전트가 claim 가능한 상태(사용자 입력 대기분).
CHAT_CLAIMABLE = ChatStatus.AWAITING_AGENT


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """대화 메시지 1건(두 백엔드 공통 표현 — content 는 완성된 문자열)."""

    conv_id: str
    seq: int
    role: ChatRole
    content: str
    done: bool
    created_at: str


@dataclass
class Conversation:
    """대화 1건의 메타."""

    id: str
    status: ChatStatus
    created_at: str
    updated_at: str
    msg_count: int = 0
    proposed_job_id: str | None = None


class ChatStore(Protocol):
    """web(producer) ↔ 에이전트(consumer) 공유 대화 버스 인터페이스.

    구현은 claim 의 원자성(동시 에이전트가 같은 대화를 중복 처리하지 않음)을 보장해야 한다.
    """

    def create_conversation(self) -> Conversation: ...
    def get_conversation(self, conv_id: str) -> Conversation | None: ...
    def list_messages(self, conv_id: str) -> list[Message]: ...
    def append_user_message(self, conv_id: str, content: str) -> Message | None: ...
    def claim_conversation(self) -> Conversation | None: ...
    def start_assistant_message(self, conv_id: str) -> Message: ...
    def append_chunk(self, conv_id: str, seq: int, text: str) -> None: ...
    def finish_turn(
        self,
        conv_id: str,
        seq: int,
        *,
        status: ChatStatus,
        proposed_job_id: str | None = None,
    ) -> Conversation | None: ...


# ────────────────────────────────────────────────────────────────────────
# SQLite 구현 (로컬/테스트)
# ────────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    msg_count       INTEGER NOT NULL DEFAULT 0,
    proposed_job_id TEXT
);
CREATE TABLE IF NOT EXISTS chat_messages (
    conv_id    TEXT NOT NULL,
    seq        INTEGER NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (conv_id, seq)
);
"""


class SqliteChatStore:
    """SQLite 기반 ChatStore — claim 은 BEGIN IMMEDIATE 로 원자적."""

    def __init__(
        self,
        db_path: str = ":memory:",
        *,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or _utcnow_iso
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self._conn = sqlite3.connect(db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def create_conversation(self) -> Conversation:
        now = self._clock()
        conv = Conversation(
            id=self._id_factory(), status=ChatStatus.OPEN, created_at=now, updated_at=now
        )
        self._conn.execute(
            "INSERT INTO conversations (id, status, created_at, updated_at, msg_count) "
            "VALUES (?, ?, ?, ?, 0)",
            (conv.id, conv.status.value, now, now),
        )
        return conv

    def get_conversation(self, conv_id: str) -> Conversation | None:
        row = self._conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        return _conv_from_row(row) if row else None

    def list_messages(self, conv_id: str) -> list[Message]:
        rows = self._conn.execute(
            "SELECT * FROM chat_messages WHERE conv_id = ? ORDER BY seq", (conv_id,)
        ).fetchall()
        return [_msg_from_row(r) for r in rows]

    def append_user_message(self, conv_id: str, content: str) -> Message | None:
        now = self._clock()
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT status, msg_count FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            if row is None or row["status"] == ChatStatus.STREAMING.value:
                self._conn.execute("COMMIT")
                return None
            seq = int(row["msg_count"])
            self._conn.execute(
                "INSERT INTO chat_messages (conv_id, seq, role, content, done, created_at) "
                "VALUES (?, ?, ?, ?, 1, ?)",
                (conv_id, seq, ChatRole.USER.value, content, now),
            )
            self._conn.execute(
                "UPDATE conversations SET status = ?, msg_count = msg_count + 1, "
                "updated_at = ? WHERE id = ?",
                (ChatStatus.AWAITING_AGENT.value, now, conv_id),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return Message(conv_id, seq, ChatRole.USER, content, True, now)

    def claim_conversation(self) -> Conversation | None:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT id FROM conversations WHERE status = ? ORDER BY updated_at LIMIT 1",
                (ChatStatus.AWAITING_AGENT.value,),
            ).fetchone()
            if row is None:
                self._conn.execute("COMMIT")
                return None
            now = self._clock()
            self._conn.execute(
                "UPDATE conversations SET status = ?, updated_at = ? "
                "WHERE id = ? AND status = ?",
                (
                    ChatStatus.STREAMING.value,
                    now,
                    row["id"],
                    ChatStatus.AWAITING_AGENT.value,
                ),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return self.get_conversation(row["id"])

    def start_assistant_message(self, conv_id: str) -> Message:
        now = self._clock()
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT msg_count FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            seq = int(row["msg_count"]) if row else 0
            self._conn.execute(
                "INSERT INTO chat_messages (conv_id, seq, role, content, done, created_at) "
                "VALUES (?, ?, ?, '', 0, ?)",
                (conv_id, seq, ChatRole.ASSISTANT.value, now),
            )
            self._conn.execute(
                "UPDATE conversations SET msg_count = msg_count + 1, updated_at = ? "
                "WHERE id = ?",
                (now, conv_id),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return Message(conv_id, seq, ChatRole.ASSISTANT, "", False, now)

    def append_chunk(self, conv_id: str, seq: int, text: str) -> None:
        self._conn.execute(
            "UPDATE chat_messages SET content = content || ? WHERE conv_id = ? AND seq = ?",
            (text, conv_id, seq),
        )

    def finish_turn(
        self,
        conv_id: str,
        seq: int,
        *,
        status: ChatStatus,
        proposed_job_id: str | None = None,
    ) -> Conversation | None:
        now = self._clock()
        self._conn.execute(
            "UPDATE chat_messages SET done = 1 WHERE conv_id = ? AND seq = ?",
            (conv_id, seq),
        )
        if proposed_job_id is not None:
            self._conn.execute(
                "UPDATE conversations SET status = ?, updated_at = ?, proposed_job_id = ? "
                "WHERE id = ?",
                (status.value, now, proposed_job_id, conv_id),
            )
        else:
            self._conn.execute(
                "UPDATE conversations SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, conv_id),
            )
        return self.get_conversation(conv_id)


# ────────────────────────────────────────────────────────────────────────
# DynamoDB 단일테이블 구현 (운영)
# ────────────────────────────────────────────────────────────────────────


class DynamoDbChatStore:
    """DynamoDB 단일테이블 ChatStore (Job 과 같은 테이블, GSI1 오버로딩)."""

    def __init__(
        self,
        table_name: str = "slackops-agent",
        *,
        dynamodb: Any | None = None,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or _utcnow_iso
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        if dynamodb is None:
            import boto3  # lazy: 미설치/자격증명 없는 환경 import-safe

            dynamodb = boto3.resource("dynamodb")
        self._table = dynamodb.Table(table_name)

    def create_conversation(self) -> Conversation:
        now = self._clock()
        conv = Conversation(
            id=self._id_factory(), status=ChatStatus.OPEN, created_at=now, updated_at=now
        )
        self._table.put_item(Item=_conv_to_item(conv))
        return conv

    def get_conversation(self, conv_id: str) -> Conversation | None:
        resp = self._table.get_item(Key={"PK": f"CHAT#{conv_id}", "SK": META_SK})
        item = resp.get("Item")
        return _conv_from_item(item) if item else None

    def list_messages(self, conv_id: str) -> list[Message]:
        from boto3.dynamodb.conditions import Key  # lazy

        resp = self._table.query(
            KeyConditionExpression=Key("PK").eq(f"CHAT#{conv_id}")
            & Key("SK").begins_with("MSG#"),
            ScanIndexForward=True,
        )
        return [_msg_from_item(item) for item in resp.get("Items", [])]

    def append_user_message(self, conv_id: str, content: str) -> Message | None:
        from botocore.exceptions import ClientError  # lazy

        now = self._clock()
        # 대화가 STREAMING 이 아닐 때만 사용자 turn 적재 + msg_count 원자 증가.
        try:
            resp = self._table.update_item(
                Key={"PK": f"CHAT#{conv_id}", "SK": META_SK},
                UpdateExpression="ADD msg_count :one SET #s = :await, GSI1PK = :gpk, "
                "updated_at = :now",
                ConditionExpression="attribute_exists(PK) AND #s <> :streaming",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":one": 1,
                    ":await": ChatStatus.AWAITING_AGENT.value,
                    ":gpk": f"CHATSTATUS#{ChatStatus.AWAITING_AGENT.value}",
                    ":now": now,
                    ":streaming": ChatStatus.STREAMING.value,
                },
                ReturnValues="UPDATED_NEW",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return None
            raise
        seq = int(resp["Attributes"]["msg_count"]) - 1
        self._table.put_item(Item=_msg_to_item(conv_id, seq, ChatRole.USER, now, done=True))
        self._set_message_content(conv_id, seq, content)
        return Message(conv_id, seq, ChatRole.USER, content, True, now)

    def claim_conversation(self) -> Conversation | None:
        from boto3.dynamodb.conditions import Key  # lazy

        resp = self._table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq(
                f"CHATSTATUS#{ChatStatus.AWAITING_AGENT.value}"
            ),
            ScanIndexForward=True,
            Limit=_CLAIM_SCAN_LIMIT,
        )
        for item in resp.get("Items", []):
            claimed = self._conditional_status(
                item["id"],
                expected=ChatStatus.AWAITING_AGENT,
                new=ChatStatus.STREAMING,
            )
            if claimed is not None:
                return claimed
        return None

    def start_assistant_message(self, conv_id: str) -> Message:
        now = self._clock()
        resp = self._table.update_item(
            Key={"PK": f"CHAT#{conv_id}", "SK": META_SK},
            UpdateExpression="ADD msg_count :one SET updated_at = :now",
            ExpressionAttributeValues={":one": 1, ":now": now},
            ReturnValues="UPDATED_NEW",
        )
        seq = int(resp["Attributes"]["msg_count"]) - 1
        self._table.put_item(
            Item=_msg_to_item(conv_id, seq, ChatRole.ASSISTANT, now, done=False)
        )
        return Message(conv_id, seq, ChatRole.ASSISTANT, "", False, now)

    def append_chunk(self, conv_id: str, seq: int, text: str) -> None:
        # DynamoDB 는 문자열 in-place append 불가 → chunks 리스트에 list_append.
        self._table.update_item(
            Key={"PK": f"CHAT#{conv_id}", "SK": f"MSG#{seq:06d}"},
            UpdateExpression="SET chunks = list_append("
            "if_not_exists(chunks, :empty), :c)",
            ExpressionAttributeValues={":c": [text], ":empty": []},
        )

    def finish_turn(
        self,
        conv_id: str,
        seq: int,
        *,
        status: ChatStatus,
        proposed_job_id: str | None = None,
    ) -> Conversation | None:
        self._table.update_item(
            Key={"PK": f"CHAT#{conv_id}", "SK": f"MSG#{seq:06d}"},
            UpdateExpression="SET done = :t",
            ExpressionAttributeValues={":t": True},
        )
        names = {"#s": "status"}
        values: dict[str, Any] = {
            ":new": status.value,
            ":gpk": f"CHATSTATUS#{status.value}",
            ":now": self._clock(),
        }
        set_parts = ["#s = :new", "GSI1PK = :gpk", "updated_at = :now"]
        if proposed_job_id is not None:
            set_parts.append("proposed_job_id = :pj")
            values[":pj"] = proposed_job_id
        resp = self._table.update_item(
            Key={"PK": f"CHAT#{conv_id}", "SK": META_SK},
            UpdateExpression="SET " + ", ".join(set_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return _conv_from_item(resp["Attributes"])

    # ── 내부 ──────────────────────────────────────────────────
    def _set_message_content(self, conv_id: str, seq: int, content: str) -> None:
        self._table.update_item(
            Key={"PK": f"CHAT#{conv_id}", "SK": f"MSG#{seq:06d}"},
            UpdateExpression="SET chunks = :c",
            ExpressionAttributeValues={":c": [content]},
        )

    def _conditional_status(
        self, conv_id: str, *, expected: ChatStatus, new: ChatStatus
    ) -> Conversation | None:
        from botocore.exceptions import ClientError  # lazy

        try:
            resp = self._table.update_item(
                Key={"PK": f"CHAT#{conv_id}", "SK": META_SK},
                UpdateExpression="SET #s = :new, GSI1PK = :gpk, updated_at = :now",
                ConditionExpression="#s = :expected",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":new": new.value,
                    ":gpk": f"CHATSTATUS#{new.value}",
                    ":now": self._clock(),
                    ":expected": expected.value,
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return None
            raise
        return _conv_from_item(resp["Attributes"])


# ── 행/항목 ↔ 도메인 변환 ────────────────────────────────────────────────
def _conv_from_row(row: sqlite3.Row) -> Conversation:
    return Conversation(
        id=row["id"],
        status=ChatStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        msg_count=int(row["msg_count"]),
        proposed_job_id=row["proposed_job_id"],
    )


def _msg_from_row(row: sqlite3.Row) -> Message:
    return Message(
        conv_id=row["conv_id"],
        seq=int(row["seq"]),
        role=ChatRole(row["role"]),
        content=row["content"],
        done=bool(row["done"]),
        created_at=row["created_at"],
    )


def _conv_to_item(conv: Conversation) -> dict[str, Any]:
    item: dict[str, Any] = {
        "PK": f"CHAT#{conv.id}",
        "SK": META_SK,
        "GSI1PK": f"CHATSTATUS#{conv.status.value}",
        "GSI1SK": conv.updated_at,
        "GSI2PK": CHATFEED_PK,
        "GSI2SK": conv.created_at,
        "id": conv.id,
        "status": conv.status.value,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "msg_count": conv.msg_count,
    }
    if conv.proposed_job_id is not None:
        item["proposed_job_id"] = conv.proposed_job_id
    return item


def _conv_from_item(item: dict[str, Any]) -> Conversation:
    return Conversation(
        id=item["id"],
        status=ChatStatus(item["status"]),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        msg_count=int(item.get("msg_count", 0)),
        proposed_job_id=item.get("proposed_job_id"),
    )


def _msg_to_item(
    conv_id: str, seq: int, role: ChatRole, created_at: str, *, done: bool
) -> dict[str, Any]:
    return {
        "PK": f"CHAT#{conv_id}",
        "SK": f"MSG#{seq:06d}",
        "conv_id": conv_id,
        "seq": seq,
        "role": role.value,
        "chunks": [],
        "done": done,
        "created_at": created_at,
    }


def _msg_from_item(item: dict[str, Any]) -> Message:
    chunks = item.get("chunks", [])
    return Message(
        conv_id=item["conv_id"],
        seq=int(item["seq"]),
        role=ChatRole(item["role"]),
        content="".join(chunks),
        done=bool(item.get("done", False)),
        created_at=item["created_at"],
    )
