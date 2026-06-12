# LOOP_ENGINEERING — slackops-devops-agent
최종 갱신: 2026-06-12

> 이 repo에 **현재 적용된** 자율 LOOP(overnight 무인 실행) 엔지니어링의 설명서.
> "자는 동안 Claude Code Headless 가 백로그를 스스로 구현·검증·기록·커밋한다."
> 코드 근거: `bin/overnight/{run.sh,PROMPT.md}`, `.claude/skills/`, `docs/NEXT_PLAN.md`, `.claude/settings.json`.

---

## 1. 한 줄 요약
프롬프트 1개를 헤드리스로 **반복 호출**하되, 매 회차가 작은 컨텍스트로 상태를 복원하고(`/sync`) →
백로그에서 **작업 1개**를 구현·테스트하고 → 기록하고(`/checkpoint`) → **로컬 커밋**한다.
한 회차가 곧 하나의 원자적 작업 단위이며, 회차마다 커밋되므로 **언제 멈춰도 손실은 최대 1회차**다.

## 2. 왜 이렇게 설계했나 (핵심 원리)
| 원리 | 이유 |
| --- | --- |
| **회차당 fresh context** | 매 회차 새 프로세스(`claude -p`) → 컨텍스트 비대/요약(compaction) 문제 없음. Read Path(≈130줄)만 다시 읽으면 복원됨. |
| **회차 = 작업 1개 + 즉시 커밋** | 한도/크래시가 언제 닥쳐도 미커밋 손실은 1회차뿐. 다음 회차가 `/sync`로 이어받음. |
| **테스트가 영속성·정확성 게이트** | `pytest` 전체 통과를 통과 못 하면 커밋 안 함 → 깨진 코드가 쌓이지 않음. |
| **상태는 파일에** | `NEXT_PLAN.md`(백로그) · `PROGRESS_LOG.md`(이력) · git history. 메모리가 아니라 디스크가 source of truth. |
| **최소 권한 무인 실행** | `.claude/settings.json` allowlist + `aws`/`git push`/네트워크 deny → 자는 동안 위험 동작 차단. |

## 3. 구성 요소

### 3.1 러너 — `bin/overnight/run.sh`
무인 루프. 회차마다 `claude -p "$(cat PROMPT.md)" --permission-mode acceptEdits --output-format json` 실행.

루프 1회 흐름:
```
STOP/DONE 파일 검사 → claude -p 회차 실행 → classify_outcome → 분기 → (pause) → 반복
```

제어 파일 / 환경변수:
| 항목 | 기본값 | 역할 |
| --- | --- | --- |
| `bin/overnight/STOP` | — | 존재하면 다음 회차 진입 전 **graceful 종료**(현재 회차는 마침) |
| `bin/overnight/DONE` | — | `[auto]` 백로그 소진 시 에이전트가 생성 → 러너 종료 |
| `MAX_ITER` | 50 | 폭주 방지 백스톱(총 회차 상한) |
| `ITER_TIMEOUT` | 3600s | 회차당 최대 실행 시간(`timeout`/`gtimeout`) |
| `LIMIT_WAIT` | 1800s | usage/session limit 감지 시 대기 후 재시도 |
| `PAUSE` | 30s | 회차 간 간격 |
| `MAX_CONSEC_FAIL` | 3 | 연속 실패 N회 시 **안전 중단**(깨진 상태로 토큰 소모 방지) |
| `--once` | — | 1회차만 실행(검증용) |

### 3.2 결과 분류 — `classify_outcome` (run.sh 내 python3)
limit 을 **자유 텍스트 grep 이 아니라** 구조화 신호로 판정한다(false 오판 방지):
1. `--output-format json` 의 **마지막 JSON 객체 `is_error == false`** → `success`
   (성공 회차의 result 텍스트에 "rate limit" 등이 언급돼도 무시 — 정상 회차 오판 차단)
2. 성공이 아닐 때만 limit 텍스트(`usage/session limit`, `hit your … limit`, `overloaded` 등) 검사 → `limit`
3. 그 외 → rc≠0 면 `failure`, 아니면 `success`

분기:
- `limit` → consec_fail 리셋, `LIMIT_WAIT` 대기 후 재시도(한도 윈도우 리셋되면 자동 속행)
- `failure` → consec_fail++ → `MAX_CONSEC_FAIL` 도달 시 중단
- `success` → consec_fail 리셋, 커밋 해시 로깅

### 3.3 회차 지시문 — `bin/overnight/PROMPT.md`
헤드리스 에이전트가 매 회차 수행하는 고정 절차:
1. **상태 복원**: Skill `sync` (Read Path: CONTEXT_BRIDGE → AGENT_BRIEF → STATUS → NEXT_PLAN)
2. **잔여물 복구**: `git status --porcelain` 검사. dirty = 이전 회차 중단 잔여물 → **복구가 곧
   이번 회차의 작업 1묶음**. pytest green 이면 `[recovered]` 커밋으로 직행, red 면 건드리지 않고
   Blocker 기록 + `STOP` 생성(사람 검수 필요 상태 — graceful 정지). 잔여물 위 새 작업·커밋 혼입 금지.
3. **작업 선택**: `NEXT_PLAN.md` 의 `[auto]` **최상위 미완료 1개만**. (`[manual]` 은 건너뜀, 없으면 `DONE` 생성 후 종료)
4. **구현**: 완료 기준대로 코드+테스트 → `pytest` **전체 통과까지**. 실패 시 `git restore` 후 Blocker 기록.
5. **기록**: Skill `checkpoint` (PROGRESS_LOG append + STATUS/NEXT_PLAN 갱신)
6. **커밋**: 먼저 `git status`로 파일 반영 확인(write 유실 방어) → `git add -A && git commit`(로컬만)

불변: `aws` 실 호출 금지(연동 코드는 mock/주입), `git push` 금지, 외부 네트워크 금지, 작업 1묶음 초과 금지,
한도 임박 시 5–6단계(checkpoint+commit) 우선.

### 3.4 백로그 — `docs/NEXT_PLAN.md`
러너가 소비하는 작업 큐. 각 항목에 태그 + **완료 기준 1줄**(scope 폭주 방지):
- `[auto]` = 로컬 코드+테스트로 무인 수행 가능
- `[manual]` = 운영자 수동(AWS/Slack/UI — 자격증명·외부 계정 필요)
위에서 아래로 1개씩. 완료 시 제거(이력은 PROGRESS_LOG).

### 3.5 문서 하네스 스킬 (`.claude/skills/`)
경계가 겹치지 않게 분리 — LOOP 의 각 단계를 담당:
| 스킬 | 단계 | 책임 |
| --- | --- | --- |
| `/sync` | 회차 시작 | Read Path 만 읽고 상태 복원. **읽기만** |
| `/checkpoint` | 회차 종료 전 | PROGRESS_LOG append + 조건부 갱신. **기록만** |
| `/tidy-docs` | 예산 초과 시 | archive 분리·압축. **정리만** |
| `/overnight-report` | 아침 검수 | 러너 상태·회차·커밋·pytest 재실측·잔여 백로그 보고. **읽기+검증만** |

### 3.6 무인 권한 — `.claude/settings.json`
`defaultMode: acceptEdits` + allowlist(Read/Edit/Write/Skill, `python3`/`git add|commit|status|diff|log|restore`,
`mkdir`/`ls`/`bash -n` 등). **deny: `aws`·`git push`·`curl`·`wget`·`rm -rf`·`sudo`·Web*·github MCP** →
프롬프트 멈춤 없이 돌되 위험·외부 동작은 구조적으로 차단.

## 4. 운영 (실사용)
```sh
# 가동 (Mac 절전 방지 + 백그라운드; 일반 터미널에선 nohup 권장)
caffeinate -dimsu bin/overnight/run.sh &

bin/overnight/run.sh --once     # 1회차만 (검증)
touch bin/overnight/STOP        # graceful 중단 (현재 회차 마치고 종료)
tail -f bin/overnight/logs/runner.log   # 관찰
# 아침에: /overnight-report  (또는 git log --oneline + docs/PROGRESS_LOG.md)
```
종료 조건: `DONE`(백로그 소진) · `STOP`(수동) · `MAX_ITER` 도달 · 연속 실패 N회.

## 5. 한계 / 알려진 동작
- **Mac 절전/덮개**: `caffeinate` 필수, 전원 연결 권장(배터리+덮개 닫힘은 잠듦).
- **회차 단위 손실**: 한도가 회차 중간에 닥치면 진행 중이던 1회차는 미커밋 손실 가능(직전까지는 커밋됨,
  다음 회차가 `/sync`로 복원). 2026-06-12 tf_review/pr 회차가 commit 직전 session limit 으로 끊겨 미커밋으로
  남았고, 다음 세션에서 pytest 검증 후 복구 커밋한 사례가 있다 → 이 복구를 PROMPT 2단계(잔여물 복구)로
  자동화함(green=`[recovered]` 커밋, red=무수정+STOP). 단 red 잔여물은 여전히 사람 검수가 필요하다(의도).
- **회차당 docs 재독해 비용**: Read Path 가 작아(≈130줄) 의도된 트레이드오프.
- **limit "직전" 감지가 아니라 회차 단위 저장**: 정확한 잔여 쿼터 조회가 불가하므로, 매 회차 커밋으로
  손실을 1회차로 bound 하는 설계.

## 6. 실측 효과 (이 repo)
2026-06-11~12 무인 회차로 백엔드 백로그를 연속 구현: sanitizer → claude_runner → allowlist →
logs → diagnose → 라우팅 → store(JobStore) → audit/telemetry store → telemetry → worker →
tf_review/pr. 각 회차가 테스트 동반 커밋(누적 216 passed). 발견·자가수정 사례: limit 오판 버그(#6),
중단된 회차 복구.

## 7. 관련 문서
- 설계 불변: `harness/CORE_MANDATES.md` · 핸드오프: `harness/CONTEXT_BRIDGE.md`
- 문서 운영(Read Path/Context Budget): `docs/DOCS_POLICY.md`
- 백로그: `docs/NEXT_PLAN.md` · 이력: `docs/PROGRESS_LOG.md`
