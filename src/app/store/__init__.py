"""Job store 패키지 — 이중 컨트롤플레인(Slack+Web) 공유 큐 + audit/telemetry.

JobStore/AuditStore/TelemetryStore 프로토콜 + 구현(Sqlite* 로컬/테스트, DynamoDb* 운영).
DynamoDb* 구현은 boto3 lazy import 로 미설치 환경에서도 import-safe.
"""

from __future__ import annotations

from app.store.audit_store import (
    AuditEvent,
    AuditStore,
    DynamoDbAuditStore,
    SqliteAuditStore,
)
from app.store.base import (
    CLAIMABLE_STATUSES,
    TERMINAL_STATUSES,
    Job,
    JobSource,
    JobStatus,
    JobStore,
)
from app.store.chat_store import (
    CHAT_CLAIMABLE,
    ChatRole,
    ChatStatus,
    ChatStore,
    Conversation,
    DynamoDbChatStore,
    Message,
    SqliteChatStore,
)
from app.store.dynamodb_store import DynamoDbJobStore
from app.store.sqlite_store import SqliteJobStore
from app.store.telemetry_store import (
    DynamoDbTelemetryStore,
    MetricRecord,
    SqliteTelemetryStore,
    TelemetryStore,
)

__all__ = [
    "CHAT_CLAIMABLE",
    "CLAIMABLE_STATUSES",
    "TERMINAL_STATUSES",
    "AuditEvent",
    "AuditStore",
    "ChatRole",
    "ChatStatus",
    "ChatStore",
    "Conversation",
    "DynamoDbAuditStore",
    "DynamoDbChatStore",
    "DynamoDbJobStore",
    "DynamoDbTelemetryStore",
    "Job",
    "JobSource",
    "JobStatus",
    "JobStore",
    "Message",
    "MetricRecord",
    "SqliteAuditStore",
    "SqliteChatStore",
    "SqliteJobStore",
    "SqliteTelemetryStore",
    "TelemetryStore",
]
