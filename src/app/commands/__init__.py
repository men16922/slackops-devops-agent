"""Slack 명령 핸들러 패키지 (MVP).

명령: ping / logs / diagnose / tf_review / pr.
각 핸들러는 permissions 게이트 + sanitizer 격리 + claude_runner 실행을 조합한다.
"""

from __future__ import annotations
