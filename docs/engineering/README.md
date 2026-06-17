# Engineering — 에이전트 운영 5개 개념 (바이블 → 해석)

이 디렉터리는 이 repo의 **AI 에이전트 운영 하네스**를 5개 개념으로 정의한다. 구조는 **바이블 → 해석**:
- **바이블**(`*_ENGINEERING.md`) = **범용·portable** 개념 문서. 특정 repo에 묶이지 않는다(다른 프로젝트로 가져갈 수 있다).
- **해석**(`interp/INTERPRETATION.md`) = 그 개념을 **이 repo의 실제 파일·명령·메커니즘에 매핑**한 적용 문서.

바이블은 "무엇/왜", 해석은 "이 repo에서 어떻게"를 담는다.

## 5개 개념
| 개념 | 바이블(범용) |
| --- | --- |
| 하네스(상위 운영 체계) | [HARNESS_ENGINEERING.md](HARNESS_ENGINEERING.md) |
| 자율 무인 루프 | [LOOP_ENGINEERING.md](LOOP_ENGINEERING.md) |
| 다중 에이전트 병렬 | [AGENTIC_ENGINEERING.md](AGENTIC_ENGINEERING.md) |
| 컨텍스트·연속성 | [CONTEXT_ENGINEERING.md](CONTEXT_ENGINEERING.md) |
| 프롬프트 | [PROMPT_ENGINEERING.md](PROMPT_ENGINEERING.md) |

이 repo 매핑: [interp/INTERPRETATION.md](interp/INTERPRETATION.md) (`/harness-init`가 생성한 스켈레톤을 채워라).

## Read Order
1. **개념을 처음 잡을 때**: 바이블 `HARNESS_ENGINEERING.md`(전체 상) → 필요한 개념의 바이블.
2. **이 repo에서 실제로 돌릴 때**: `interp/INTERPRETATION.md`(러너·gate·파일 경로).
3. 무인 루프 운영 = `LOOP_ENGINEERING.md` + `scripts/overnight/run.sh`.
4. 문서/상태/세션 연속성 = `CONTEXT_ENGINEERING.md` + `/sync`·`/checkpoint` skills.

## 권위 / 상위 문서
- 문서 운영 규칙·라인 예산: `.claude/harness-config.json` (skills가 읽음) + `CONTEXT_ENGINEERING.md`.
- 백로그/레인 태그: `docs/NEXT_PLAN.md`.
