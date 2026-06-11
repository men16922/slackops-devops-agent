# STATUS — slackops-devops-agent
최종 갱신: 2026-06-11

> 현재 상태/검증/risks (≤120줄). source of truth. 갱신은 /checkpoint.

## 현재 요약
- repo 부트스트랩 완료. 빌드 Day 1 착수 직전.
- 문서 하네스(harness/ + docs/ + skill 3종) + src/app stub 골격 + pyproject/.env.example/.gitignore 생성됨.

## 검증 Baseline
- `python -m pytest tests/ -q` → import smoke test 만 존재 (의존성 미설치 환경에서도 통과 설계).
- 실 기능 테스트 없음(코드 stub 단계).

## 동작하는 것
- (없음 — 스캐폴드 단계.) 모든 src/app 모듈은 타입힌트·docstring 포함 stub, 로직 미구현.

## Active Focus
- Day 1–3 트랙: EC2 + IAM Role + Claude Code + Socket Mode + `/devops ping`.
- 다음: logs/diagnose + Context Sanitizer.

## Open Risks
- untrusted input(CloudWatch 로그·git diff)이 곧 공격면 — Sanitizer/allowlist 우회 주의.
- IAM Instance Profile 외 자격증명 절대 금지(.env 는 example 만 커밋).
- EC2 상시 가동 시 비용 — EventBridge 스케줄 stop/start 확인.
- 비-목표(범위 밖): HTTPS 공개 엔드포인트, EC2 상시 가동, Level 2(Execute), Production/배포/IAM/DB 변경,
  SQLite 를 prod 데이터스토어로 호칭.
