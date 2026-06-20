# 데모 스크립트 (한글 가이드)

> **샷 리스트 정본은 영어** — [../en/DEMO_SCRIPT.md](../en/DEMO_SCRIPT.md)(화면 자막 영어). 이 문서는 한글 진행 가이드.
> 전략·로컬/클라우드 분리 = `docs/submission/PRESENTATION.md` Appendix C.

## 준비
```sh
export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"
make demo        # web(8930) + DynamoDB Local + chat_agent + worker
```

## 흐름(3분, 가능하면 연속 take)
1. **문제(0:20)** — 온콜 토일. 자막 "AI가 제안·알림, 사람이 경계".
2. **트리거(0:20, 클라우드)** — `aws cloudwatch set-alarm-state … ALARM` + 자막 "임계치 대신 손으로 당김(파이프라인 시연)".
3. **감지+알림(0:40)** — 상주 모니터 제안 → **Slack ping + 🔔 벨** 점등.
4. **거버넌스(1:05)** — Detections 토글 ON → **Scan now** → detect 작업 등장 → (클라우드)실 findings.
5. **사람 게이트(1:35)** — 제안 열기 → rationale+diff → ✅ Approve → 재승인 "이미 처리됨"(낙관적 락).
6. **실행+증명(2:00)** — worker 실행 → DONE → (클라우드)write 시도 "denied by security policy".
7. **계측+감사(2:20)** — 비용/토큰 + Audit 타임라인.
8. **마무리(2:40)** — 보안 불변 오버레이(Socket Mode·IAM Profile·격리·L0/L1) + DB 한 문장.

## 클라우드 캡처 필수 4컷(EC2 1회 가동 ~$1 후 stop)
① 실 CloudWatch diagnose ② 실 스캔 findings(IAM/Config) ③ write-denied ④ alarm→제안.
나머지(채팅·제안·벨·승인·락·실행·계측·Detections 토글/Scan-now)는 **로컬 `make demo`**. Slack ping 도 로컬 가능(Socket Mode 아웃바운드).
