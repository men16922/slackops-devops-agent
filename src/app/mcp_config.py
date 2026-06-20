"""AWS API MCP 서버 설정 — agentic 데이터 접근(diagnose/logs)용.

Claude Code Headless 가 read-only AWS 도구를 **직접 호출**하도록 awslabs AWS API MCP
서버(stdio)를 등록한다. 코드가 boto3 로 선수집하는 대신 에이전트가 CloudWatch 등을
조회한다 — 권한 경계는 다음 다층으로 잡는다:
  ① IAM read-only(EC2 Instance Profile / 로컬 read-only 키),
  ② 서버 read-only 모드 강제(`READ_OPERATIONS_ONLY=true` — 변형 작업 거부),
  ③ `--strict-mcp-config` + allowlist 의 좁은 read 도구만(allowlist.py),
  ④ service 인자 검증(validated_service).
주의: MCP tool_result 는 `<untrusted_data>` 격리를 우회해 Claude 컨텍스트로 직접
들어온다 — 이는 agentic 모델의 수용된 트레이드오프이며 위 ①~④ 가 hard boundary 다.

region 함정: botocore 는 region 을 AWS_DEFAULT_REGION 에서 읽는다(AWS_REGION 만으론
NoRegionError) — 둘 다 전달한다. 자격증명 env 가 없으면(EC2) Instance Profile 로 해석된다.

pin: awslabs.aws-api-mcp-server@1.3.45 (도구 call_aws / suggest_aws_commands,
read-only env READ_OPERATIONS_ONLY) — 2026-06-20 캡처.
"""

from __future__ import annotations

import json
import os

# 서버 config 키 → Claude 도구 ID 접두사(mcp__<key>__<tool>). allowlist 와 일치해야 한다.
AWS_MCP_SERVER_NAME = "awsapi"

# 재현성 위해 버전 pin(@latest 금지). user-data 의 pre-warm 과 동일해야 한다.
AWS_MCP_PACKAGE = "awslabs.aws-api-mcp-server@1.3.45"

# allowlist(diagnose/logs)가 참조하는 read 도구 ID — 서버의 call_aws/suggest_aws_commands.
AWS_MCP_TOOLS: tuple[str, ...] = (
    f"mcp__{AWS_MCP_SERVER_NAME}__call_aws",
    f"mcp__{AWS_MCP_SERVER_NAME}__suggest_aws_commands",
)

# 부모 env 에 있으면 서버 subprocess 로 전달할 키(자격증명/프로필 — 로컬 dev 용).
_AWS_ENV_PASSTHROUGH: tuple[str, ...] = (
    "AWS_REGION",
    "AWS_DEFAULT_REGION",  # botocore 는 이걸 읽는다 — 반드시 포함
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_PROFILE",
)


def aws_mcp_config_json(server_name: str = AWS_MCP_SERVER_NAME) -> str:
    """AWS API MCP 서버(stdio, read-only) 등록용 인라인 JSON 을 만든다.

    `READ_OPERATIONS_ONLY=true` 를 항상 강제(변형 작업 거부)하고 텔레메트리는 끈다.
    region/자격증명 env 는 존재할 때만 전달(EC2 에선 부재 → Instance Profile).

    Args:
        server_name: mcpServers 키 = Claude 도구 ID 접두사(allowlist 와 일치).

    Returns:
        `claude --mcp-config` 에 넘길 JSON 문자열.
    """
    env: dict[str, str] = {
        "READ_OPERATIONS_ONLY": "true",  # IAM 위 추가 방어 — 변형 작업 거부
        "AWS_API_MCP_TELEMETRY": "false",  # 외부 텔레메트리 비활성
    }
    for key in _AWS_ENV_PASSTHROUGH:
        value = os.environ.get(key)
        if value:
            env[key] = value
    return json.dumps(
        {
            "mcpServers": {
                server_name: {
                    "command": "uvx",
                    "args": [AWS_MCP_PACKAGE],
                    "env": env,
                }
            }
        }
    )
