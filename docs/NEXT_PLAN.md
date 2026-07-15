# NEXT_PLAN — slackops-devops-agent
Last updated: 2026-07-15

> **Open work only** (≤120 lines). Remove when done (history → PROGRESS_LOG/COMPLETED_SUMMARY). Authority: this file > docs/plans/.
> Tags: `[auto]` = doable in an unattended overnight round (local code+tests). `[manual]` = operator manual (AWS/Slack/UI).
> `[blocked]` = same item hit a Blocker twice — no unattended retry before human review (rounds append and skip).
> Unattended rounds do one `[auto]` top-to-bottom. Each item's "Done:" criterion must be met to finish.

## ★ Active — v2 AWSKRUG 발표 데모 (plan: docs/plans/2026-06-25-awskrug-demo.md, branch `v2`)
> Slack 해커톤 제출은 **폐기**(Devpost §3 Eligibility 한국 미달 — plan 부록 §7). 목표 = AWSKRUG 라이브 데모.
> D1/D2/D2.5/D3 **코드완료·게이트 green**(358 passed). 핵심 미완 = **실 Slack 검증**(사람 타이핑). 상세 단계는 plan §4.
- [x] D1 Assistant 핸들러 · D2 승인게이트(버튼↔출력게이트)+poll-in-thread · D2.5 포스트모템 Canvas(스파이크 통과) — 2026-06-26.
- [x] D3 로컬 mock 폴백 — Assistant 콘솔(`make demo-assistant[-mock]`) real+오프라인 e2e + **인젝션 방어 장면 검증** — 2026-07-02.
- [x] **실 Slack sandbox e2e** — DM 폴백 경로로 6항목 전부 통과(스트리밍/버튼/approved 전이/Canvas/footer/payload) — 2026-07-02.
      ⏰ Canvas 는 무료 트라이얼 **7/19 종료** — 캡처/데모 그 전에.
- [x] `[auto]` Modal diff 승인 + Message Shortcut 구현: 버튼/승인 요청 메시지 shortcut이 diff modal(최대 28K)을 열고,
      allowlist·낙관적 상태 전이를 재검증한다 (2026-07-15, local/CI). 실제 Slack App shortcut 등록·클릭 검증은 아래 수동 항목.
- [ ] `[manual]` Slack App에 `review_slackops_job` Message Shortcut을 등록하고 Modal diff 승인/거부를 실 Slack에서 확인.
      Done: 비허용 사용자는 modal을 열거나 상태를 바꾸지 못하고, 허용 사용자의 결정은 원본 메시지와 감사 기록에 남음.
- [x] `[manual]` D4 실 AWS 1회(EC2 start→`handle_diagnose` 실 CloudWatch 진단+write-denied 확인→EC2 stop) — 2026-07-06.
- [ ] `[manual]` AWSKRUG 슬라이드 디자인 마무리 (라이브 시연으로 대체, 사전 녹화 폐기).
- [ ] `[manual]` 다음 실 Slack/EC2 리허설에서 SSM에 동기화한 `SLACK_APPROVER_IDS`를 기존 인스턴스 환경 파일에 반영하고 승인 버튼 검증.
      Done: 비허용 버튼 클릭은 거부되고, 허용 승인자는 감사 기록에 남음.
## (폐기) H0 Devpost 제출 — 한국 자격 미달로 중단 (인프라/코드는 v2 가 재사용)
- [x] 클라우드 배포 + 이벤트구동 풀루프 live · Vercel 배포 · DynamoDB 증빙 — 2026-06-20 (자산은 유지, 비용 ≈ $0).

## Day 1–3 — AWS/Slack execution (deploy/README.md order) — A–C DONE 2026-06-20
- [x] Slack App (Socket Mode) created + SSM SecureString tokens (bot/app/CLAUDE_CODE_OAUTH_TOKEN) stored.
- [x] `deploy/iam/create-role.sh` (role+profile, +AmazonSSMManagedInstanceCore for Session Manager).
- [x] `deploy/ec2/launch-instance.sh` (repo public-transitioned for unauth clone; 3 systemd services active) → `/devops ping` pong verified → EC2 terminated.
- [ ] `[manual]` `deploy/eventbridge/create-schedules.sh <id>` — skipped (terminate instead of schedule; revisit on redeploy).
- [x] `[auto]` P3 pilot guardrail scaffold: separate-account contract, context-key-bound read-only policy, CloudTrail violation query,
      and CI isolation regression added (2026-07-15). No AWS role, endpoint, or managed MCP session was created.
- [ ] `[manual]` P3 organization expansion pilot: allow managed AWS MCP only in a separate role/context-key/CloudTrail environment;
      verify selected-server VPC endpoint support before making it a requirement. Done: real distinct account IDs, an approved pilot-only
      trust policy, and an empty CloudTrail violation query prove no generic MCP role reaches this runtime.

## Secure Agent Runtime — Notion 레퍼런스 P0/P1 대조 (docs/DECISIONS D19)
> 레퍼런스: Notion "SlackOps Safe DevOps Agent" §8 Implementation Priority. **번호 체계가 repo 의
> P1/P2/P3(audit sink/scope boundary/managed-MCP pilot)와 다르다** — 섞어 쓰지 말 것.
- [x] `[auto]` P0 command allowlist + argument schema: argv 정규화(`;`/`$()`/backtick/redirect/glob/traversal)
      후 명령별 스키마 검증을 PreToolUse hook 으로 강제 (2026-07-16, 실 런타임 실측 통과).
- [x] `[auto]` P0 write executor 상시권한 제거 + 승인 hash 검증 후 target-scoped 단기 credential 발급/회수/감사
      (2026-07-16, local/CI). GitHub App 등록 전이라 실 토큰 경로는 미검증.
- [ ] `[manual]` GitHub App 등록(대상 저장소 1개, `contents:write`+`pull_requests:write`만) → SSM 4개 파라미터
      (`PR_REPOSITORY`/`GITHUB_APP_ID`/`GITHUB_INSTALLATION_ID`/`GITHUB_APP_PRIVATE_KEY_B64`) 저장 →
      EC2 에서 `pr` execute 1회 리허설. Done: 승인 전 push 시도가 자격 부재로 실패하고, 승인 후에는
      installation token 으로 PR 이 열리며 `write_credentials_issued` 감사가 남는다.
- [x] `[auto]` P1 multi-tool capability aggregation + 재승인 조건: 선언적 5종 taxonomy, 체인 누적 risk score,
      `RISK_CEILING=10`(write-high/privileged 는 단독으로 초과), plan 에 score/ceiling/account/region 고정,
      read→write 상승·score 변경·계정/리전 변경 재승인 트리거 (2026-07-16, DECISIONS D20).
- [x] `[auto]` P1 audit trajectory 필드: step_id/parent_step_id/tool_name/capabilities/target_resource/result_hash,
      store 가 step_id 부여, worker 가 phase 트리 emit(`write_credentials_issued` 부모 = 승인 스텝), `build_step_tree`,
      해시 back-compat(빈 필드는 payload 제외 → 기존 DynamoDB 체인 유효), web 미러 (2026-07-16, DECISIONS D21).
- [ ] `[auto]` P1 per-tool-call 궤적: 현재 트리는 **phase 단위**다. 한 Claude 호출 안의 도구별 하위 스텝을 남기려면
      `--output-format stream-json` 파싱이 필요하다(`json` 출력엔 tool call 정보가 없어 `claude_runner` 가
      tool_calls 를 제공하지 못한다 — `StreamResult.tool_uses` 는 이미 있다).
      Done: 한 job 의 트리에서 Claude 호출 아래 실제 도구 호출이 자식 스텝으로 보이고, capability 집계가 정적
      allowlist 가 아니라 **관측된 도구**로 재계산된다(현재 D20 한계를 해소).
- [ ] `[auto]` P1 post-condition 확장: 현재 remote diff 비교만이고 `pr` 전용. 단 L2(Execute)가 비활성이라
      health/replica/config 재조회는 **검증할 실제 변경이 없다** — L2 를 열 때까지는 값어치가 낮다.

## Day 6–7 — tf-review + pr remaining
- [ ] `[manual]` GitHub App minimal scope + branch protection (block auto-merge) setup.

## Day 8–9 — Observability
- [ ] `[manual]` Configure ADOT Collector on EC2 + capture diagnose numbers once (N sec/$0.0X/M tool calls).

## Later — presentation/article (manual)
- [ ] `[manual]` Record demo + slides / AWSKRUG talk / PACE paragraph / article draft.
