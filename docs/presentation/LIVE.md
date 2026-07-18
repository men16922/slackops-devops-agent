# SlackOps LIVE 시연 시나리오

> 기준 슬라이드: `docs/presentation/SlackOps.pdf` Slide 16/18
> 목표 시간: 4분 30초, 최대 6분
> 실제 경로: Slack Assistant DM -> DynamoDB queue -> EC2 worker -> 승인 -> GitHub PR
> 안전 원칙: 진단은 read-only, 변경은 승인 전 실행 금지, PR은 merge하지 않는다.

## 시연에서 증명할 것

1. 자연어 요청이 고정된 읽기 경로의 진단으로 변환된다.
2. 변경 요청은 diff와 `awaiting_approval` 상태에서 멈춘다.
3. 승인자 allowlist와 plan binding 검증을 통과해야 실행된다.
4. 승인 후에는 LLM이 아니라 결정적 실행기가 실제 GitHub PR을 만든다.
5. PR 생성 뒤에도 branch protection 때문에 사람이 검토하고 merge해야 한다.

## 현재 저장소 기준 주의사항

- 작성 시점에는 `deploy/.instance-id`가 없다. `make cloud-start`나 `make cloud-status`는 바로 사용할 수 없다.
- 실제 리허설에서는 신규 EC2를 `make cloud-up`으로 준비하고, 시연이 끝나면 `make cloud-stop` 또는 `make cloud-down`으로 정리한다.
- Vercel/DynamoDB/SSM/GitHub App 설정은 유지돼 있지만, 발표 직전에는 실제 연결을 다시 확인한다.
- PR 시연은 `main`에 직접 쓰지 않는다. 에이전트가 만든 branch와 PR까지만 보여주고 merge하지 않는다.

---

# 1. 사전 준비

## D-1: 클라우드와 승인 경로 준비

### 1. 로컬 자격과 필수 설정 확인

값은 화면에 출력하지 않고 설정 여부만 확인한다.

```bash
set -a
source .env
set +a

make cloud-whoami

test -n "${SLACK_BOT_TOKEN:-}" && echo "SLACK_BOT_TOKEN=set"
test -n "${SLACK_APP_TOKEN:-}" && echo "SLACK_APP_TOKEN=set"
test -n "${SLACK_APPROVER_IDS:-}" && echo "SLACK_APPROVER_IDS=set"
test -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" && echo "CLAUDE_CODE_OAUTH_TOKEN=set"
```

루트 `.env`를 사용하는 경우 셸에 직접 값을 출력하지 않는다. Slack 승인자 목록은 SSM에 동기화한다.

```bash
make cloud-slack-approvers
```

### 2. EC2 신규 기동

현재 `deploy/.instance-id`가 없으므로 신규 기동한다.

```bash
make cloud-up
make cloud-status
```

부팅과 설치에는 수분이 걸릴 수 있다. 콘솔 로그에서 설치 완료를 확인한다.

```bash
make cloud-console
```

필요하면 SSM Session Manager로 접속해 네 유닛을 확인한다.

```bash
make cloud-ssm
```

EC2 세션 안에서:

```bash
systemctl is-active slackops-devops-agent
systemctl is-active slackops-devops-agent-worker
systemctl is-active slackops-devops-agent-chat-agent
systemctl is-active slackops-devops-agent-monitor
```

네 유닛이 모두 `active`가 아니면 라이브 경로를 사용하지 않고 아래의 복구 플랜 B로 전환한다.

### 3. 실제 연결 스모크

Slack에서 다음 두 항목만 확인한다.

```text
/devops ping
```

기대 결과:

```text
pong
```

그다음 Slack Assistant DM을 열어 다음 문장을 보낸다.

```text
What can you do?
```

기대 결과: `logs`, `diagnose`, `tf-review`, `pr` 범위와 사람 승인 절차를 안내한다.

### 4. GitHub 쓰기 경로 확인

- GitHub App이 대상 저장소 한 곳에만 설치됐는지 확인한다.
- App 권한은 `Contents: Read & write`, `Pull requests: Read & write`만 사용한다.
- `main` branch protection에서 PR review가 필수인지 확인한다.
- 기존 데모 PR과 branch는 닫혀 있어도 무방하다. 새 job은 별도 branch를 만든다.
- SSM의 PR write 4종이 존재하는지만 확인하고 값은 출력하지 않는다.

```bash
aws ssm get-parameters \
  --names \
    /slackops/PR_REPOSITORY \
    /slackops/GITHUB_APP_ID \
    /slackops/GITHUB_INSTALLATION_ID \
    /slackops/GITHUB_APP_PRIVATE_KEY_B64 \
  --query 'Parameters[].Name' \
  --output table
```

### 5. 대시보드 확인

- Vercel Production 대시보드에 GitHub OAuth로 로그인한다.
- Job Queue가 열리고 DynamoDB `LIVE` 표시가 보이는지 확인한다.
- 새 작업이 목록 최상단에 나타나는지 짧은 스모크로 확인한다.
- 발표 중에는 재로그인하지 않도록 세션을 유지한다.

## D-1: 화면 준비

다음 순서로 탭을 고정한다.

1. Slack Assistant DM
2. Vercel Job Queue
3. GitHub Pull Requests
4. 비상용 캡처: Slide 10, 11, 15의 원본 이미지 또는 PDF
5. 비상용 터미널: 저장소 루트

화면 준비 원칙:

- Slack 확대 125-150%
- 대시보드 확대 110-125%
- GitHub 확대 110-125%
- 알림 팝업과 개인 DM 미리보기 끄기
- 토큰, 계정 ID, SSM 값, `.env`, 터미널 history는 화면에 띄우지 않기
- Slack 입력 문장은 발표자 메모에 복사해 두기

## D-1: 리허설 통과 기준

- [ ] `/devops ping`이 10초 안에 응답한다.
- [ ] 자연어 diagnose 요청이 job으로 생성된다.
- [ ] PR 요청이 `awaiting_approval`에서 멈춘다.
- [ ] Review change Modal에서 diff를 볼 수 있다.
- [ ] 허용된 승인자가 `Approve and run`을 누를 수 있다.
- [ ] 실제 GitHub PR이 열리고 DONE으로 끝난다.
- [ ] PR은 자동 merge되지 않는다.
- [ ] 전체 흐름이 6분 이내다.
- [ ] PR 실패 시 사용할 완료 캡처가 준비돼 있다.

---

# 2. 발표 당일 프리플라이트

## T-60분

```bash
make cloud-status
make cloud-console
```

`deploy/.instance-id`가 없거나 instance가 사라졌다면 이 시점까지만 `make cloud-up`을 허용한다. 발표 직전에 신규 배포를 시작하지 않는다.

SSM 세션에서 worker와 Slack 앱의 최근 로그를 확인한다.

```bash
journalctl -u slackops-devops-agent -n 30 --no-pager
journalctl -u slackops-devops-agent-worker -n 30 --no-pager
```

로그에 토큰이나 민감 정보가 없는지 먼저 확인한 뒤 화면 공유를 시작한다.

## T-30분

- Slack `ping` 확인
- Vercel 로그인과 Job Queue 확인
- GitHub Pull Requests 탭 확인
- 발표자 Slack ID가 `SLACK_APPROVER_IDS`에 포함됐는지 확인
- 네트워크 유선/무선 상태 확인
- 화면 공유 대상이 전체 화면이 아닌 발표용 창인지 확인

## T-10분

- 테스트 메시지를 더 보내지 않는다.
- Slack DM 스크롤을 시연 시작 위치로 맞춘다.
- 대시보드 필터를 초기화한다.
- GitHub Pull Requests를 최신순으로 둔다.
- PDF는 Slide 16에 대기한다.

---

# 3. LIVE 본 시나리오

## 0:00-0:20 - 시연 목표 선언

Slide 16에서 말한다.

"지금부터 네 가지를 보겠습니다. 자연어 요청이 읽기 전용 진단으로 이어지는지, 변경 전에 diff에서 멈추는지, 승인한 계획만 실행되는지, 그리고 실제 PR이 생성되는지입니다."

Slack Assistant DM으로 전환한다.

## 0:20-1:30 - 자연어 진단

다음 문장을 보낸다.

```text
checkout-service is showing 5xx errors. Diagnose the cause using read-only evidence.
```

응답을 기다리며 말한다.

"이 요청은 바로 AWS CLI로 전달되지 않습니다. command router가 diagnose로 분류하고, fixed read adapter가 허용된 계정, 리전, 시간 범위와 로그 prefix 안에서만 증거를 가져옵니다. 모델의 tool allowlist는 0이고, 수집된 로그는 untrusted data로 격리됩니다."

job이 보이면 다음 세 항목만 짚는다.

1. `diagnose` command
2. 근거 또는 데이터 부족 상태
3. trace/job ID와 비용/토큰 footer

실데이터가 없거나 일부 adapter가 실패해도 실패를 숨기지 않는다.

"증거가 없으면 원인을 만들어내지 않고, 어떤 데이터 소스가 비어 있거나 실패했는지 남깁니다. 이 실패도 감사와 텔레메트리에 기록됩니다."

1분 10초 안에 최종 상태가 오지 않으면 복구 플랜 A로 전환한다.

## 1:30-2:30 - 변경 요청과 승인 전 정지

다음 문장을 보낸다.

```text
Please queue a PR job: in src/app/claude_runner.py change DEFAULT_TIMEOUT_S from 600 to 750. Config-only change. Do not merge it. Queue it for human approval.
```

말한다.

"이번 요청은 코드 변경입니다. 에이전트는 바로 push하지 않습니다. 먼저 변경안을 준비하고 diff를 만든 뒤 `awaiting_approval` 상태에서 멈춥니다. 이 시점에는 GitHub write token이 없습니다."

승인 카드가 나타나면 다음만 보여준다.

- target file: `src/app/claude_runner.py`
- diff: `600 -> 750`
- status: `awaiting_approval`
- `Review diff`, `Approve`, `Reject`

결과가 다르거나 diff가 불필요하게 넓으면 승인하지 않는다. 복구 플랜 A로 전환한다.

## 2:30-3:20 - Review change Modal과 승인

`Review diff`를 눌러 Modal을 연다.

말한다.

"승인은 '이 작업을 알아서 해도 된다'는 허가가 아닙니다. 지금 보이는 diff, 실행 계획, tool chain, workspace를 hash로 묶습니다."

diff가 정확한지 눈으로 확인한 뒤 `Approve and run`을 누른다.

말한다.

"승인자 allowlist를 먼저 확인합니다. worker는 실행 직전에 plan hash를 다시 계산하고, 한 글자라도 달라졌으면 `plan_binding_rejected`로 멈춥니다. 일치할 때만 대상 저장소에 제한된 GitHub App token을 짧게 발급합니다."

## 3:20-4:10 - 실제 PR 확인

GitHub Pull Requests 탭으로 전환해 새 PR을 연다.

확인할 항목:

1. SlackOps bot이 만든 새 PR
2. 변경 파일 1개
3. `DEFAULT_TIMEOUT_S 600 -> 750`
4. branch protection과 merge 대기 상태

말한다.

"LLM이 직접 push한 것이 아닙니다. 승인 이후에는 결정적 실행기가 branch와 PR을 만들었습니다. 토큰은 해당 저장소의 contents와 pull requests 범위로 제한되고 작업 뒤 회수됩니다. 그리고 이 PR은 자동 merge되지 않습니다. 최종 변경 권한은 사람에게 남습니다."

## 4:10-4:30 - 대시보드와 슬라이드 복귀

시간이 허용되면 Vercel Job Queue에서 DONE 상태를 5초만 보여준다.

짚을 항목:

- source
- DONE status
- audit timeline
- cost/tokens

PDF Slide 17로 돌아가며 말한다.

"방금 보신 핵심은 AI가 PR을 만들었다는 기능이 아닙니다. 읽기 단계에는 쓰기 권한이 없었고, 변경 단계에는 사람이 승인한 diff와 실행 계획이 그대로 묶였다는 점입니다."

---

# 4. 복구 플랜

## 플랜 A - 클라우드 응답 지연 또는 한 단계 실패

사용 조건:

- diagnose가 70초 안에 끝나지 않음
- Slack 승인 카드가 늦음
- PR 생성에 40초 이상 걸림
- 한 adapter가 실데이터를 반환하지 못함

행동:

1. 실패를 숨기지 않고 현재 상태를 한 문장으로 설명한다.
2. 이미 준비한 Slide 10 또는 11 캡처로 전환한다.
3. 완료된 실제 PR 캡처에서 승인 전/후 경계를 설명한다.
4. 30초 안에 Slide 17로 복귀한다.

멘트:

"실환경 응답이 지연되고 있어 준비한 실제 검증 화면으로 전환하겠습니다. 이 화면은 같은 경로에서 승인 전 `awaiting_approval`, 승인 후 실제 PR 생성까지 확인한 결과입니다."

## 플랜 B - EC2 또는 Slack 앱 장애

사용 조건:

- 네 systemd 유닛 중 하나가 inactive
- Socket Mode 연결 실패
- worker가 DynamoDB를 소비하지 못함

발표 전에만 로컬 real-Claude 경로를 준비할 수 있다.

```bash
make demo-all
```

이 경로는 Slack, 로컬 DynamoDB, chat agent, worker를 함께 띄운다. 단, 로컬 PR execute는 GitHub write 인증 환경이 없으면 실패할 수 있으므로 진단과 승인 대기까지만 라이브로 보여주고 PR 결과는 실검증 캡처로 전환한다.

## 플랜 C - 네트워크 또는 Claude 장애

오프라인 재현 콘솔을 사용한다.

```bash
make demo-assistant-mock
```

이 경로는 실제 클라우드 증명이 아니라 화면 흐름을 재현하는 fallback이다. 반드시 다음과 같이 밝힌다.

"현재는 오프라인 재현으로 인터랙션 흐름만 보여드리고 있습니다. 실제 EC2 보안 경계와 GitHub App PR 경로는 앞의 캡처와 Slide 15의 검증 결과입니다."

## 즉시 중단 조건

다음 상황에서는 승인 버튼을 누르지 않는다.

- diff가 `src/app/claude_runner.py` 한 파일을 벗어남
- `DEFAULT_TIMEOUT_S 600 -> 750` 이외 변경이 포함됨
- 대상 repository가 예상 값과 다름
- 승인자가 allowlist에 없다는 경고가 나타남
- plan hash mismatch 또는 capability drift 경고가 나타남
- 토큰이나 자격 증명이 화면에 노출됨

중단 멘트:

"예상한 승인 범위를 벗어났기 때문에 실행하지 않겠습니다. 이 중단 자체가 지금 설명드린 안전 경계의 동작입니다. 준비한 검증 결과로 이어가겠습니다."

---

# 5. 시연 후 정리

## 발표 직후

1. 생성된 PR을 merge하지 않는다.
2. PR을 닫고 에이전트가 만든 원격 branch를 삭제한다.
3. Job detail에서 DONE/FAILED와 audit 이벤트를 보관한다.
4. CloudWatch와 GitHub App 로그에 비정상 토큰 또는 권한 오류가 없는지 확인한다.

## 비용 정리

재사용할 인스턴스라면 stop한다.

```bash
make cloud-stop
```

완전히 정리할 인스턴스라면 terminate한다.

```bash
make cloud-down
```

`cloud-down`은 EC2와 `deploy/.instance-id`만 정리한다. DynamoDB, IAM, Vercel, SSM, GitHub App은 별도 운영 자산이므로 자동 삭제되지 않는다.

## 증거 보관

- Slack 진단 결과와 approval card
- Review change Modal의 diff
- GitHub PR URL과 변경 파일
- Job detail의 audit timeline
- `write_credentials_issued` 이벤트의 비민감 메타데이터
- PR close와 branch 삭제 결과
- EC2 stop/terminate 상태

토큰 값, SSM SecureString 값, 계정 비밀, private key는 캡처하거나 문서에 붙이지 않는다.

---

# 6. 한 장짜리 큐시트

| 시간 | 화면 | 행동 | 핵심 멘트 |
| ---: | --- | --- | --- |
| 0:00 | Slide 16 | 목표 선언 | 읽기, 승인, plan binding, PR을 보겠다 |
| 0:20 | Slack | diagnose 문장 전송 | fixed adapter, tools=0, untrusted data |
| 1:30 | Slack | PR 문장 전송 | 승인 전 write token 0 |
| 2:30 | Modal | diff 검토 후 승인 | 승인 대상과 plan hash를 묶는다 |
| 3:20 | GitHub | 새 PR 확인 | 결정적 실행기, 단기 token, no self-merge |
| 4:10 | Dashboard | DONE/audit 5초 확인 | 성공과 실패를 같은 job으로 추적 |
| 4:30 | Slide 17 | 결론 복귀 | 기능이 아니라 통제 가능한 행동이 핵심 |

## 복사할 입력 문장

```text
checkout-service is showing 5xx errors. Diagnose the cause using read-only evidence.
```

```text
Please queue a PR job: in src/app/claude_runner.py change DEFAULT_TIMEOUT_S from 600 to 750. Config-only change. Do not merge it. Queue it for human approval.
```
