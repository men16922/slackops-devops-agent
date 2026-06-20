# QA_TEST — 직접 검증 (미결사항만)

> **사람이 직접 눈으로 확인해야 하는 것 중 아직 안 끝난 것**만 모은 문서.
> 자동 게이트(`make check` — pytest/ruff/mypy)와 **로컬 풀 e2e 는 전부 ✅ 완료**(PROGRESS_LOG 참고) → 여기서 제외.
> 실행 방법: 에이전트 = [SLACK_GUIDE.md](SLACK_GUIDE.md) · 대시보드 = [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md) ·
> 인프라 실행/제출물 = `docs/runbooks/deploy-checklist.md`(권위).

---

## 1. 잔여 검증 — AWS 배포 후 (유일한 잔여 트랙)
> 클라우드 e2e(`/devops ping`, IAM Instance Profile 로 CloudWatch RO via AWS MCP)는 **2026-06-20 검증 완료 후 EC2 종료**.
> 아래는 제출물 확보를 위해 **재기동 시 1회씩** 확인할 미결 항목.

- [ ] **실 DynamoDB 데이터** — `slackops-agent` 에 실 항목(Job/Audit/Metric) 적재 → **콘솔 스크린샷**(제출물).
- [ ] **실측 수치** — diagnose 1회: 소요 N초 / 비용 $0.0X / tool call M회 (`devops.run` span 또는 대시보드 Telemetry).
- [ ] **Vercel 대시보드** — 실 DynamoDB 읽어 피드 렌더 + **Team ID/링크 확보**(DASHBOARD_GUIDE §7).
- [ ] **출력 게이트 + branch protection** — 승인 없이 머지 불가(실 GitHub, PR 게이트 검증 시).
- [ ] *(선택)* **EventBridge** — 평일 stop/start 스케줄 동작(상시 가동 금지). 현재는 종료로 대체 — 재기동 시 결정.
- [ ] *(선택)* **ADOT Collector** — CloudWatch EMF + X-Ray 로 수치 확인(`deploy/adot/collector-config.yaml`).

> 제출물(다이어그램/스크린샷/데모영상/텍스트/링크/아티클) 생산 체크리스트는 `deploy-checklist.md` [E]·[F].

---

## 2. 심사 충족 — DB 정당화 (제출 설명·영상에 그대로)
> Slack 과 Vercel 두 control plane 이 하나의 작업 큐를 공유 → **DynamoDB conditional write** 로 별도 코디네이터 없이
> atomic job claim + optimistic-lock 승인 게이트 구현. (Aurora 아닌 DynamoDB 인 이유)

- **Technical** — 단일테이블 + conditional write(atomic claim / 중복승인 차단). GSI2 = FEED/AUDIT/METRIC 피드.
- **Design** — 웹 TS `lib/ddb` 가 파이썬 `store/` 단일테이블 계약을 미러(GSI 질의·ConditionExpression 동형).
- **Impact** — 대상 = 소규모 팀 온콜/플랫폼 엔지니어. 콘솔 왕복·수동 진단 토일 감소. 공개 포트 0 + 최소권한 + 사람 승인 → 안전 출시.
- **Originality** — 에이전트 자율 *제안* + 사람 *경계*가 단일 큐 공유. 단순 챗봇 아닌 안전 운영 패턴 레퍼런스.

---

## 3. 알려진 한계 / 주의 (제출 설명에 정직히)
- **CloudWatch 가 AWS MCP `tool_result` 로 유입(D13) → `<untrusted_data>` 격리 우회.** 경계 = IAM 읽기전용 + `READ_OPERATIONS_ONLY` + `--strict-mcp-config` + 읽기전용 tool allowlist.
- DynamoDB Local 은 **in-memory** — `docker compose down`/재기동 시 데이터 소멸, `up` 시 시드 재주입. 웹 채팅은 폴링 자가복구+재시도로 새 대화 무중단.
- `tool_calls` 계측: 스트리밍 경로(`chat_agent`)는 수집, worker(비스트림 `run_headless`) metric 은 아직 `None`.
- L2(Execute)/prod/IAM/DB 변경은 **비활성**(금지 불변) — MVP 범위 밖.
- 로컬 worker 의 pr execute 는 실 push 라 GitHub 인증 환경(=AWS/EC2)에서만 검증.
- SQLite 는 **MVP/테스트 한정** — prod 데이터스토어로 호칭하지 않는다(운영 = DynamoDB).
