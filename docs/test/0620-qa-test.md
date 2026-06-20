# QA TEST — 클라우드 체크리스트 (F1–F5 + 거버넌스 Detections)

> **로컬 전부 검증 완료** (대시보드 Playwright · 실 Claude L0 풀루프 done $0.14 · Slack `/devops ping`+작업 생명주기 알림 라이브 ·
> 이모지/자동갱신 fix · `make demo-incident` 스케줄러/주입). 상세 = PROGRESS_LOG 2026-06-20.
> 자동 게이트: `make check` **310 passed** · ruff · mypy(31) · doc-budget / web `next build` green.
> **다음 세션 = 클라우드(EC2 + 실 AWS) 캡처.**

---

## ☁️ 클라우드 체크리스트 (제출 캡처용)

- [ ] **EC2 배포** — `docs/runbooks/deploy-checklist.md` [B]~[C] (systemd 4개 active: slack/worker/chat-agent/monitor) → `/devops ping` pong.
- [ ] **실 CloudWatch diagnose** — `/devops diagnose <svc>` → Instance Profile로 실 로그/트레이스 진단(blind 아님).
- [ ] **실 거버넌스 스캔 findings** — `/devops detect iam` 또는 Detections Scan now → **실 IAM Access Analyzer findings**.
- [ ] **write-denied** — 쓰기 op 시도 → `"denied by security policy"`(read-only 경계 증명). ★ 제출 강추 컷.
- [ ] **alarm 트리거 시나리오** — **`make cloud-alarm`**(실 AWS 자격) → 실 alarm 강제 ALARM → 신호화 → 에이전트 diagnose 제안(실 큐) →
      worker 실행 → Slack 알림. `ARGS=--real` = Tier2(Claude가 alarm 직접 조회). 끝나면 `make cloud-alarm-clean`.
- [ ] **실 DynamoDB 데이터 + 콘솔 스크린샷** — Job/Audit/Metric 실 항목.
- [ ] **Vercel 배포** — 읽기전용 IAM 키 → web/(Root=`web`, `DDB_ENDPOINT` 미설정) → **링크/Team ID** (`docs/guide/{kr,en}/DASHBOARD_GUIDE.md §7`).
- [ ] **Slack 슬래시 명령 클라우드** — `/devops logs/diagnose/detect/tf-review` (로컬 ping만 확인했으니 클라우드에서 나머지).
- [ ] **💰 비용 안전** — 스캔은 **IAM Access Analyzer(무료)만**. **AWS Config recorder 켜지 말 것**(과금). roadmap 3종 미배선→호출 불가.
      read API·`set-alarm-state` 무료. alarm ~$0.10/월(cloud-alarm-clean). Claude 추론비는 AWS 아님(구독). 캡처 후 **EC2 stop**.

---

## 주의 / 메모 (클라우드)
- **pr GitHub 인증**: push/PR은 표준 git/gh CLI(`gh auth login`) — `.env`의 `GITHUB_APP_*`는 미배선 placeholder(채울 필요 없음). 진짜 PR은 인증된 EC2에서만.
- **alarm→큐 자동 적재**는 EventBridge 미배선(roadmap) — `make cloud-alarm`이 describe-alarms→monitor 다리.
- **상주 monitor**(systemd `--loop 300`)는 Tier1 + 하드코딩 신호(heartbeat) — EC2 띄우면 5분 내 자동 제안+알림. 특정 시나리오는 cloud-alarm/`--signals-file`.
- 정리: 캡처 후 `aws ec2 stop-instances` + `make cloud-alarm-clean`. DynamoDB/Vercel은 심사기간 유지(idle ~$0).
