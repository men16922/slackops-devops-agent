"""`/devops tf-review` — terraform plan 위험/비용/보안 리뷰.

`terraform plan` 출력(untrusted)을 sanitizer 로 격리해 위험/비용/보안 관점 리뷰. 권한 Level 1(plan 까지, apply 금지).
"""

from __future__ import annotations


def handle_tf_review() -> str:
    """terraform plan 을 실행·리뷰해 위험/비용/보안 요약 반환.

    apply 는 절대 수행하지 않는다(금지 불변).

    Returns:
        Slack 에 게시할 리뷰 요약.
    """
    raise NotImplementedError("Day 6–7: tf-review 핸들러(plan + Sanitizer + 리뷰) 구현 예정")
