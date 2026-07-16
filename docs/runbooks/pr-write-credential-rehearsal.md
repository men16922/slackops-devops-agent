# Runbook — PR write credential 경로 실검증 (GitHub App)

> 대상: operator(사람). 목적: 코드에서 **유일하게 미검증**인 write credential 경로를
> 실 EC2에서 한 번 리허설한다. 코드는 완성됨(`src/app/write_credentials.py` +
> `src/app/worker.py`). 이 문서는 그 경로를 실제로 켜서 Done 4조건을 확인하는 절차다.
> 권위: docs/NEXT_PLAN.md("write credential 경로 실검증") · rationale: docs/DECISIONS.md D19–D23.

## 0. 배경 (왜 이 리허설이 필요한가)

에이전트는 **상시 push 권한을 갖지 않는다.** diagnose 경로는 write 자격이 아예 없고,
`pr` *prepare* 단계도 write credential 없이 돌아 push를 시도조차 못 한다. write 자격은
worker가 **승인된 plan hash가 실행 직전 workspace에 그대로 바인딩됨을 재검증한 직후**에만,
그 한 자식 프로세스의 환경에서만 발급되는 저장소·권한 고정 installation token(기본 10분)이다.
단계가 끝나면 즉시 회수하고, 만료가 백스톱이다.

코드 경로(`GitHubAppGrantIssuer`)는 로컬/CI에서만 검증됐다 — **실제 GitHub App이 없어서**
`_app_jwt()` → installation token 발급 → push/PR 왕복이 실물로 돈 적이 없다. 이 리허설이 그 공백을 닫는다.

## 1. 사전 요건

- 대상 저장소 1개(예: `men16922/slackops-devops-agent`).
- 그 저장소 admin 권한(GitHub App 설치 + branch protection 설정).
- SSM `put-parameter` + EC2 SSM Session Manager 접근이 되는 AWS 자격.
- 의존성: `pyjwt[crypto]`는 `pyproject.toml`에 있고 user-data의 `pip install -e .`가 설치한다
  (RS256 서명에 필요한 `cryptography` 포함). **별도 조치 불필요.**

## 2. 환경 변수 매핑 (참고)

worker는 `SLACKOPS_`-prefixed 환경변수를 읽고, user-data.sh가 `/slackops/<NAME>` SSM →
`SLACKOPS_<NAME>` 로 매핑한다. 넷 중 하나라도 비면 부팅이 아니라 **worker가 즉시 거부**한다
(`_require_approval_binding`, 부분 설정 = fail closed).

| SSM 파라미터 | EC2 env | 비고 |
| --- | --- | --- |
| `/slackops/PR_REPOSITORY` | `SLACKOPS_PR_REPOSITORY` | `owner/name` 형식 |
| `/slackops/GITHUB_APP_ID` | `SLACKOPS_GITHUB_APP_ID` | App ID(숫자) |
| `/slackops/GITHUB_INSTALLATION_ID` | `SLACKOPS_GITHUB_INSTALLATION_ID` | 설치 후 URL의 숫자 |
| `/slackops/GITHUB_APP_PRIVATE_KEY_B64` | `SLACKOPS_GITHUB_APP_PRIVATE_KEY_B64` | PEM의 base64(SecureString) |

## 3. 절차

### ① GitHub App 생성
github.com/settings/apps → **New GitHub App**
- **Repository permissions** — 딱 둘만:
  - **Contents = Read & write**
  - **Pull requests = Read & write**
  - 나머지 전부 *No access*. 특히 `administration` / `workflows` / `secrets` 금지.
- **Webhook**: Active 체크 해제(불필요).
- 생성 후 **App ID** 기록 → **Generate a private key** 로 `.pem` 다운로드.

### ② 대상 저장소 하나에만 설치
App → **Install App** → 계정 선택 → **Only select repositories** → 대상 repo 1개.
- 설치 후 URL `…/installations/<숫자>` 의 숫자가 **Installation ID**.

### ③ SSM 4종 저장
```sh
aws ssm put-parameter --name /slackops/PR_REPOSITORY --value 'men16922/slackops-devops-agent'
aws ssm put-parameter --name /slackops/GITHUB_APP_ID --value '<App ID>'
aws ssm put-parameter --name /slackops/GITHUB_INSTALLATION_ID --value '<Installation ID>'
# PEM 은 여러 줄이라 systemd EnvironmentFile 이 파싱 못 함 → base64(개행 없이).
aws ssm put-parameter --name /slackops/GITHUB_APP_PRIVATE_KEY_B64 --type SecureString \
  --value "$(base64 -w0 < slackops-agent.private-key.pem)"   # macOS: base64 -i slackops-agent.private-key.pem
```

### ④ 대상 repo branch protection
Settings → Branches → `main` → **Require a pull request before merging** 켜기.
→ 이 토큰으로도 자기 PR 을 self-merge 못 함을 확인하는 게 Done 기준의 일부다.

### ⑤ EC2 `pr` execute 1회 리허설
새 인스턴스는 user-data 가 자동 로드한다. **기존 인스턴스는 부팅만으론 user-data 를
재실행하지 않는다** → SSM 세션에서 env 갱신 후 worker 재시작:
```sh
aws ssm start-session --target "$INSTANCE_ID"
# /etc/slackops-devops-agent.env 에 SLACKOPS_* 4종 반영 후
sudo systemctl restart slackops-devops-agent-worker
```
그다음 Slack `/devops pr <설명>` → diff 게시 → 승인 버튼 → worker execute.

## 4. Done 판정 (4가지 모두 확인)

1. **승인 전 push 실패** — 자격 부재로 fail closed.
2. **승인 후 PR 열림** — installation token 으로 대상 repo 에 PR 생성.
3. **감사 기록에 `write_credentials_issued`** — 토큰 값은 미노출, `job_id`/`approval_hash`/
   `policy_version`/`repository`/`permissions` 만 남는다(`WriteGrant.audit_context`).
4. **self-merge 차단** — branch protection 이 에이전트 자신의 PR 머지를 막는다.

## 5. 트러블슈팅

| 증상 | 점검 |
| --- | --- |
| worker 가 write 자격 없이 거부 | SSM 4종 중 누락 확인(부분 설정 = fail closed). `journalctl -u slackops-devops-agent-worker`. |
| `could not mint a write credential` | App ID/Installation ID 불일치, 또는 App 이 대상 repo 에 미설치. |
| JWT/서명 오류 | `GITHUB_APP_PRIVATE_KEY_B64` 가 올바른 PEM 의 base64 인지(개행 유입 여부) 확인. |
| PR 은 열리는데 머지됨 | branch protection 미적용 — ④ 재확인. |
| `approval hash does not match` | 승인 후 workspace/diff 변경(TOCTOU) — 정상 거부. 승인 상태 그대로 재실행. |

## 6. 정리
리허설 직후 EC2 stop/terminate(상시 가동 금지 불변). SSM 파라미터는 다음 리허설을 위해
유지해도 무방(토큰 자체는 저장되지 않고, App 키만 root-only SecureString 으로 보관).
결과(감사 이벤트 payload)를 확보하면 `/checkpoint` 로 STATUS/PROGRESS_LOG 에
"write credential 경로 실검증 완료" 반영.
