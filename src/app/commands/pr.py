"""`/devops pr <설명>` — branch → 수정 → test → PR (사람 확인 게이트).

권한 Level 1. 출력 게이트(주입 방어 3계층): 변경 diff 를 Slack 스레드에 먼저 게시하고
사람 확인 후에만 진행. branch protection 으로 에이전트 PR 자동 머지 차단.
"""

from __future__ import annotations


def handle_pr(description: str) -> str:
    """설명을 받아 branch 생성 → 코드 수정 → test → PR 생성.

    PR 머지는 하지 않는다(branch protection + 사람 확인 게이트).

    Args:
        description: 변경 설명(검증된 값).

    Returns:
        Slack 에 게시할 diff/PR 링크 + 확인 요청.
    """
    raise NotImplementedError("Day 6–7: pr 핸들러(branch→수정→test→PR + 출력 게이트) 구현 예정")
