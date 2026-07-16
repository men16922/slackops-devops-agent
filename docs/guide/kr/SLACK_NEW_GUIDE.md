# SLACK_NEW_GUIDE — 새 워크스페이스로 Slack App 이전

> 대상: operator(사람). 목적: Trial 만료된 기존 워크스페이스에서 **새 워크스페이스로 Slack App 이전**.
> 코드/EC2/AWS/대시보드는 그대로 두고, **Slack App 재생성 + 토큰/채널/승인자 값만 교체**한다.
> 관련: [SLACK_GUIDE.md](SLACK_GUIDE.md)(기본 운영) · manifest: `slack-app-manifest.yaml`.

## 0. 핵심 이해

Slack App 은 워크스페이스에 종속이라 **재사용 불가 → 새로 만든다.** 하지만 백엔드는 무변경이고,
바꿀 값은 딱 넷이다:

| 값 | 로컬(.env) | 클라우드(SSM) | 재발급 이유 |
| --- | --- | --- | --- |
| `SLACK_BOT_TOKEN` (`xoxb-`) | O | `/slackops/SLACK_BOT_TOKEN` | 새 App |
| `SLACK_APP_TOKEN` (`xapp-`) | O | `/slackops/SLACK_APP_TOKEN` | 새 App-Level Token |
| `SLACK_APPROVER_IDS` | O | `/slackops/SLACK_APPROVER_IDS` | 새 워크스페이스는 member ID 가 다름 |
| `SLACK_NOTIFY_CHANNEL` (`C…`) | O | `/slackops/SLACK_NOTIFY_CHANNEL` | 새 채널 ID |

> 대시보드(Vercel)의 GitHub OAuth(`AUTH_GITHUB_*`)와 PR write(GitHub App)는 **Slack 과 무관** — 건드리지 않는다.

## 0.1 Free 플랜 주의 (Canvas)

새 워크스페이스가 **Free** 면 Canvas 가 standalone 불가 → `channel_id` 필수(채널 탭형).
코드는 이미 `SLACK_NOTIFY_CHANNEL` 채널에 붙이도록 대응돼 있어 **추가 코드 변경 없음**.
데모 서사상 채널 탭형이 오히려 자연스럽다.

---

## 1. App 생성 — manifest 붙여넣기 (클릭 3곳)

CLI/Manifest API 는 이 1회성 이전에는 오히려 느리다(config token 부트스트랩 + App-Level Token 은
결국 UI). 가장 빠른 길:

1. 새 워크스페이스에서 https://api.slack.com/apps → **Create New App → From a manifest**
   → 워크스페이스 선택 → `docs/guide/kr/slack-app-manifest.yaml` 내용 붙여넣기 → Create.
   - manifest 가 `assistant_view` 를 거부하면 그 블록만 지우고 붙인 뒤, App 설정 UI 의
     **"Agents & AI Apps"** 를 수동으로 켠다(scope/event 는 유지).
2. **Install to Workspace** → OAuth 승인 → **Bot User OAuth Token** `xoxb-…` = `SLACK_BOT_TOKEN`.
3. **Basic Information → App-Level Tokens → Generate** → scope `connections:write` →
   `xapp-…` = `SLACK_APP_TOKEN`.

> manifest 가 자동 처리하는 것: slash `/devops`, Message Shortcut `review_slackops_job`,
> Socket Mode, interactivity(승인 버튼/Modal), DM 폴백/Assistant 이벤트, 필요한 bot scope 5종.

## 2. 채널 + 승인자 값 확보

- **알림 채널**: 채널 생성 → 봇 초대(`/invite @slackops`) → 채널 우클릭 "채널 세부정보"의
  하단 **Channel ID**(`C…`) = `SLACK_NOTIFY_CHANNEL`.
- **승인자**: 승인 가능 사용자의 프로필 → "member ID 복사"(`U…`) → 쉼표 목록 = `SLACK_APPROVER_IDS`.
  **비어 있으면 모든 승인 버튼이 거부된다**(fail-closed).

---

## 3. 값 교체

### 3.1 로컬(.env) — 로컬 데모/테스트용
`.env` 의 아래 4줄을 새 값으로 덮어쓴다(gitignore 됨, 커밋 금지).
```
SLACK_BOT_TOKEN=xoxb-...(새)
SLACK_APP_TOKEN=xapp-...(새)
SLACK_APPROVER_IDS=U...(새)
SLACK_NOTIFY_CHANNEL=C...(새)
```

### 3.2 클라우드(SSM) — EC2 런타임용
```sh
aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN     --type SecureString --overwrite --value 'xoxb-...'
aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN     --type SecureString --overwrite --value 'xapp-...'
aws ssm put-parameter --name /slackops/SLACK_APPROVER_IDS  --overwrite --value 'U...,U...'
aws ssm put-parameter --name /slackops/SLACK_NOTIFY_CHANNEL --overwrite --value 'C...'
```

### 3.3 EC2 반영
**기존 인스턴스는 부팅만으론 user-data 를 재실행하지 않는다.** SSM 세션에서 env 갱신 후 재시작:
```sh
aws ssm start-session --target "$INSTANCE_ID"
# /etc/slackops-devops-agent.env 의 SLACK_* 4줄 갱신 후
sudo systemctl restart slackops-devops-agent slackops-devops-agent-worker slackops-devops-agent-chat-agent
```
새로 만드는 EC2 는 user-data 가 자동으로 SSM 값을 읽으므로 이 단계 불필요.

---

## 4. e2e 검증

1. **로컬**: `.env` 갱신 후 로컬 앱 기동 → 새 워크스페이스에서 `/devops ping` → `pong`.
2. **Assistant/DM**: 봇에게 DM 또는 Assistant 스레드로 자연어 입력 → 스트리밍 응답.
3. **승인 게이트**: `/devops pr <설명>` → diff 게시 → **Approve** 버튼 → 승인자만 통과, 감사 기록 남음.
4. **Message Shortcut**: 작업 메시지의 "Review SlackOps job" 단축키 → Modal diff 승인/거부.
5. **Canvas**: 진단 후 알림 채널 탭에 포스트모템 Canvas 생성.
6. **클라우드**: EC2 재시작 후 `/devops ping` → `pong … on ip-…ec2.internal`.

| 증상 | 점검 |
| --- | --- |
| `/devops ping` 무응답 | 토큰 로드/Socket 연결 — `journalctl -u slackops-devops-agent -n 50`. SSM 이름·복호화 권한. |
| 승인 버튼 전부 거부 | `SLACK_APPROVER_IDS` 가 새 워크스페이스의 member ID 인지(구 ID 는 무효). |
| Shortcut 안 보임 | manifest 재확인 + App **재설치**(shortcut 은 설치 시 등록). |
| Assistant 패널 없음 | "Agents & AI Apps" 미활성 — App 설정에서 켜고 재설치. |
| Canvas 실패 | Free 플랜은 `channel_id` 필수 — `SLACK_NOTIFY_CHANNEL` 채널에 봇이 있는지. |

---

## 5. 마무리
- 구 워크스페이스 App 은 삭제하거나 그대로 방치(만료되면 자동 비활성).
- 이전 완료 후 `/checkpoint` 로 STATUS 의 Slack 관련 상태(워크스페이스/채널/승인자) 갱신.
