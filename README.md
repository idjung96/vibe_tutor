# team-dev-harness

요구사항을 입력하면 planner / tester / coder / checker 4개 에이전트가
Stage-Gate 방식으로 단계별 자동 개발을 수행하는 **AI 에이전트 개발팀 하니스**다.
Owner(사용자)는 시작 승인, C등급 질문 답변, 최종 인수 — 3개 지점에만 개입한다.

## 무엇을 위한 프로젝트인가

코딩 에이전트를 쓸 때 **변수 이름 등 코딩 규칙, 로깅 규칙, 테스트케이스 작성 규칙**
같은 좋은 개발 관행을 에이전트에게 주입하는 **skill-set**이다. 초보자는 규칙을 몰라도
일관된 품질을 얻고, 중급자 이상은 매번 같은 지시를 반복하지 않고 팀 표준을 강제할 수 있다.

여기서 제공하는 harness와 skill은 **codex, opencode, claude code** 같은 여러 코딩
에이전트가 사용한다 — 특정 에이전트에 종속되지 않는 것을 목표로 한다(에이전트별 차이는
"알려진 제약" 참조). 다만 이 저장소 자체의 정리·개발은 Claude Code로 계속 진행하므로,
**저장소 운영용으로는 Claude Code 전용 도구를 두어도 된다**(산출물의 비종속성과는 별개).

- 단일 소스(templates/) + 설치 시점 프로파일 렌더링 구조
- 소형 모델(온프레미스 LLM)과 대형 모델(Claude) 모두 지원
- 컴퓨터 초보자의 바이브코딩을 전제로 설계

## 설치

macOS / Linux:
```bash
git clone <이 저장소>
cd team-dev-harness
./init.sh ~/projects/my-app                          # 프로파일 자동, 에이전트 all
./init.sh --profile small --agent codex ~/projects/my-app
./init.sh --agent claude,codex ~/projects/my-app     # 일부만
```

Windows (PowerShell):
```powershell
git clone <이 저장소>
cd team-dev-harness
.\init.ps1 -Target C:\projects\my-app
.\init.ps1 -Profile small -Agent codex -Target C:\projects\my-app
```
Windows 요구사항: PowerShell 5.1 이상, Git for Windows(Git Bash 포함 —
Claude Code Windows 버전의 요구사항이기도 하다). 두 설치 스크립트의
렌더링 결과는 동일하게 설계되어 있다.

- **프로파일**(`--profile`/`-Profile`, 생략 시 자동): `ANTHROPIC_BASE_URL` 또는
  `OPENAI_BASE_URL`이 사내망(내부 IP, kims, litellm, localhost)을 가리키면 **small**,
  그 외(비어 있거나 외부)는 **large**.
- **에이전트**(`--agent`/`-Agent`, 생략 시 `all`): `claude`, `codex`, `opencode`를
  콤마로 조합하거나 `all`. 선택한 에이전트의 설정만 생성된다.

설치가 끝나면 프로젝트 폴더에서 코딩 에이전트(Claude Code / Codex / opencode)를
열고 `개발 시작` 이라고 입력한다. 초보자 안내는 생성된 `dev-agent-team/guides/OWNER_GUIDE.md` 참조.

## 저장소 구조

```
HARNESS_VERSION          # 버전 (호환성 계약 변경 시 올림)
init.sh                  # 설치 (macOS/Linux): 판별 → 렌더링 → hook 검증
init.ps1                 # 설치 (Windows): 동일 로직의 PowerShell 포팅
profiles/
  small.conf             # 온프레미스 LLM용 파라미터
  large.conf             # 외부 대형 모델용 파라미터
templates/
  AGENTS.md.tmpl         # 공통 헌법 (모든 에이전트가 읽음)
  CLAUDE.md.tmpl         # Claude 전용 오버레이 (@AGENTS.md import)
  settings.json.tmpl     # Claude 권한 allow/deny + hook 등록
  roles/                 # planner, tester, coder, checker, documenter (+large: lead, reviewer, critic, security) 본문 (단일 소스)
  skills/                # team-dev(절차), logging-rule, lib-research, code-convention, test-design
  hooks/                 # Owner 질문 정지, 테스트 보호 (→ dev-agent-team/hooks/)
  codex/                 # config.toml, hooks.json (Codex 오버레이)
  opencode/              # opencode.json, plugins/guard.js (opencode 오버레이)
  common/logger.py       # 공통 로거 (고정 포맷)
  common/selfcheck.py    # 선택적 자가점검 도구 (테스트 수집 + print 사용 점검)
  docs/                  # OWNER_GUIDE, DEBUG_GUIDE → 설치 시 dev-agent-team/guides/
  project/               # DECISIONS, TEST_LOG, libs INDEX → 설치 시 dev-agent-team/
samples/sample-task-todo # 표본 과제 (모델 전환 테스트용)
tests/verify_hooks.sh    # hook 실동작 검증 (init.sh가 자동 실행)
```

설치 결과(에이전트별):
- 공통: `AGENTS.md`(헌법), `dev-agent-team/`(작업/상태 + `dev-agent-team/hooks/` 가드 스크립트),
  `common/logger.py`, `tests/` `logs/`(제품 디렉터리).
- `claude`: `CLAUDE.md`, `.claude/`(settings·agents·skills).
- `codex`: `.codex/config.toml`·`.codex/hooks.json`, `.agents/skills/`(역할+절차 스킬).
- `opencode`: `opencode.json`, `.opencode/agents/`·`.opencode/plugins/guard.js`.

역할 본문(`roles/`)은 단일 소스이고, init이 에이전트별 frontmatter를 붙여
Claude=서브에이전트, Codex=`.agents/skills/`, opencode=서브에이전트로 렌더한다.

## 프로파일 차이 (이 12가지만 다르다)

| 항목 | small | large |
|---|---|---|
| RETRY_LIMIT | 3 | 5 |
| MAX_CHECKER_CALLS | 10 | 15 |
| tester 추가 탐색 | 없음 (체크리스트 4종만) | "보이면 더 쓴다" |
| coder 단계 밖 발견 → BACKLOG 보고 | 없음 | 있음 |
| coder 디버깅 절차 | 4단계 강제 | 로그 우선 1줄 |
| 영향 표 파일 수 산정 | 추정 | grep 실측 |
| 단계 시작 병렬 (tester ∥ lib-research) | 순차 | 병렬 |
| 코드·테스트 리뷰 (reviewer 역할) | 없음 | 있음 (PASS 후 merge 전) |
| 팀장 방향·백로그 그루밍 (lead 역할) | 없음 | 있음 (계획 전·단계 시작) |
| 결정 심의·합의 (critic 역할) | 없음 | 있음 (planner 결정 직후, 모호·고위험만 Owner) |
| 보안 점검 (security 역할) | 없음 | 있음 (PASS 후 merge 전, 심각하면 Owner) |
| 요구사항 충돌·누락 점검 (planner) | 없음 | 있음 (단계 나누기 전) |

## 호환성 계약 (프로파일과 무관하게 동일 — 변경 시 버전 올림)

1. 파일 위치/형식: AGENTS.md(공통 헌법), dev-agent-team/ 레이아웃, dev-agent-team/PLAN.json 스키마,
   dev-agent-team/DECISIONS.md / dev-agent-team/TEST_LOG.md / dev-agent-team/OWNER_QUESTION.md / dev-agent-team/libs/ 형식,
   커밋 메시지, 브랜치 이름
2. C등급 목록(요구사항 변경, 삭제, 비용, 외부 배포, 보안, GPL, 외부 데이터 약관·저작권)과
   정지 메커니즘 (dev-agent-team/OWNER_QUESTION.md → 가드레일 차단, "답: 번호"로 해제)
3. deny/차단 목록 (push, rm -rf, hard reset, python -c 우회 포함)
4. append-only 테스트 원칙 (가드레일로 강제)
5. 로그 형식 `[LEVEL] [모듈] 메시지 | key=value`
6. 5개 역할(planner/tester/coder/checker/documenter) 구조와 역할 경계
7. 공유 상태 파일은 메인 세션만 쓴다 (단일 작성자 원칙)

이 계약은 에이전트와 무관하게 동일하다. 가드레일 **강제 방식만** 에이전트별로
다르다(Claude=hook, Codex=hook.json, opencode=플러그인). 이 덕분에 **모델 전환과
에이전트 전환 인수인계**가 가능하다: small↔large, Claude↔Codex↔opencode 어느 쪽으로
넘겨도 상태가 전부 dev-agent-team/ 파일에 있으므로 무손실로 계속된다.

## 배포 전 검증 (관리자용)

1. `./init.sh --profile small /tmp/t1` 과 `--profile large /tmp/t2` 실행,
   hook 검증 6항목 전부 PASS 확인 (init.sh가 자동 수행).
2. samples/sample-task-todo 로 양 프로파일 실주행:
   - small: C등급 과잉 에스컬레이션, JSON 형식 파손율 관찰
   - large: 과소 에스컬레이션(애매한 요구를 스스로 해석), 범위 초과 관찰
3. 모델 전환 테스트: small로 3단계 진행 → 폴더를 large 환경으로 이동 →
   4단계부터 이어서 진행 → dev-agent-team/TEST_LOG.md 누적이 끊기지 않는지 확인.
4. 파일럿: 소형 사용자 2명 + Claude Code 사용자 2명.

## 알려진 제약

- **가드레일 강제력은 에이전트마다 다르다.** Claude는 hook(exit 2)으로 확실히 차단한다.
  Codex는 같은 exit 2 `hook.json`을 쓰지만 파일 편집(`apply_patch`)·MCP 호출 훅이
  불안정하고 Windows에서 미지원이다. opencode는 `.opencode/plugins/guard.js`로 차단한다
  (bun/node 필요). 강제가 불완전할 수 있으므로 AGENTS.md의 규칙을 병행하고, 기관 배포
  시 devcontainer/Docker로 프로젝트 디렉토리만 마운트하는 것을 권장한다.
- **Codex는 `.codex` 설정이 trusted 프로젝트에서만 적용된다.** 설치 후 안내대로
  `~/.codex/config.toml` 의 `[projects]` 에 프로젝트를 등록해야 한다.
- **Codex에는 서브에이전트가 없다.** 5개 역할은 `.agents/skills/` 스킬로 제공되며
  단일 에이전트가 순차로 수행한다(Claude·opencode는 서브에이전트로 위임).
- **온프레미스 연결은 에이전트별로 따로 설정**한다(Claude=`ANTHROPIC_BASE_URL`,
  Codex=`.codex/config.toml` `[model_providers]`, opencode=`provider`). 설치된 파일에
  주석 예시가 있다.
- Windows에서 hook 검증은 Git Bash를 사용한다. 없으면 검증을 건너뛰며 경고를 출력한다.
- 자세한 메커니즘과 출처는 위 "멀티 에이전트 지원 — 조사 결과와 참고 자료" 참조.

## 멀티 에이전트 지원 — 조사 결과와 참고 자료

산출물(harness/skill)은 **Claude Code, Codex CLI, opencode** 세 코딩 에이전트가
사용하는 것을 목표로 한다. 아래는 각 에이전트가 프로젝트에 규칙·스킬·서브에이전트·
가드레일을 주입하는 방식을 공식 문서 기준으로 조사한 결과다(2025–2026 기준).
**codex와 claude code는 반드시 커버**하고, opencode는 가능한 범위에서 커버한다.

### 메커니즘 비교

| 항목 | Claude Code | Codex CLI | opencode |
|---|---|---|---|
| 지시문 파일 | `CLAUDE.md` (AGENTS.md 직접 안 읽음 → `@AGENTS.md` import 또는 심볼릭으로 연결) | `AGENTS.md` (루트+중첩, `AGENTS.override.md` 우선) | `AGENTS.md` (`CLAUDE.md` 폴백) |
| 스킬 (SKILL.md) | `.claude/skills/<n>/SKILL.md` | `.agents/skills/<n>/SKILL.md` | `.opencode/skills/` (+`.claude/`·`.agents/` 호환) |
| 서브에이전트(별도 프로세스) | `.claude/agents/<n>.md` | **없음** (스킬/멀티에이전트로 대체) | `.opencode/agents/<n>.md` |
| 가드레일(훅) | `.claude/settings.json` hooks, **exit 2 차단** | `.codex/hooks.json`, **exit 2 차단** (단 `apply_patch`·MCP 불안정, Windows 미지원) | TS 플러그인 `tool.execute.before`에서 throw |
| 권한 | settings.json `allow/deny/ask` | config.toml `approval_policy`+`sandbox_mode` | opencode.json `permission` allow/ask/deny |
| 온프레미스 연결 | `ANTHROPIC_BASE_URL` | config.toml `[model_providers]` `base_url`, `wire_api="responses"` | `provider` `@ai-sdk/openai-compatible` `baseURL` |
| MCP | `.mcp.json` | config.toml `[mcp_servers]` | opencode.json `mcp` |

### 설계에 주는 함의

- **AGENTS.md = 공통 헌법.** 셋 다 읽힌다. Claude Code만 `CLAUDE.md`에서 `@AGENTS.md`로
  끌어오거나 심볼릭으로 연결한다.
- **스킬은 `.agents/skills/` + `.claude/skills/` 두 곳**에 두면 셋 다 커버된다
  (`.agents/`=Codex 네이티브+opencode 호환, `.claude/`=Claude Code+opencode 호환).
- **5-에이전트(planner/tester/coder/checker/documenter) + large 전용 lead·reviewer·critic·security**: Claude·opencode는
  서브에이전트로 둘 수 있으나, **Codex는 별도 서브에이전트 프로세스가 없다** → team-dev 스킬이
  "단일 에이전트가 역할을 순차 수행"하도록 기술해야 한다.
- **가드레일(C등급 정지·테스트 보호)**: Claude=shell hook, Codex=동일 `exit 2` `hook.json`
  (단 파일편집 훅 불안정), opencode=JS 플러그인. Codex/opencode에서는 일부만 강제되므로
  **프롬프트 규칙을 반드시 병행**한다.
- **small/large 판별**: 온프레미스면 small, 그 외 large. 온프레미스 신호는
  Claude=`ANTHROPIC_BASE_URL`, Codex/opencode=`OPENAI_BASE_URL` 등 내부망 주소다.

### 참고 자료 (출처)

**Claude Code** (공식: code.claude.com)
- [Memory & CLAUDE.md](https://code.claude.com/docs/en/memory) — CLAUDE.md 위치·로드 순서, AGENTS.md 연결, import 문법
- [Skills](https://code.claude.com/docs/en/skills) — `.claude/skills/<n>/SKILL.md` 형식·프론트매터
- [Sub-agents](https://code.claude.com/docs/en/sub-agents) — `.claude/agents/<n>.md` 프론트매터·위임
- [Hooks](https://code.claude.com/docs/en/hooks) — 이벤트 종류, exit 2 차단 규약, matcher
- [Settings](https://code.claude.com/docs/en/settings) — permissions allow/deny/ask, MCP 제어

**Codex CLI** (공식: developers.openai.com/codex)
- [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) — 탐색 순서·중첩·override·바이트 상한
- [Agent Skills](https://developers.openai.com/codex/skills) — `.agents/skills/` 경로, SKILL.md, `agents/openai.yaml`
- [Hooks](https://developers.openai.com/codex/hooks) — `.codex/hooks.json`, 이벤트, exit 2 — 그리고 한계: [apply_patch 훅 미발화 #16732](https://github.com/openai/codex/issues/16732)
- [Configuration Reference](https://developers.openai.com/codex/config-reference) · [Advanced Config](https://developers.openai.com/codex/config-advanced) — `[model_providers]`(온프레미스), 프로파일
- [Agent approvals & security](https://developers.openai.com/codex/agent-approvals-security) — approval_policy, sandbox_mode
- [MCP](https://developers.openai.com/codex/mcp) — `[mcp_servers]`

**opencode** (공식: opencode.ai/docs)
- [Rules](https://opencode.ai/docs/rules/) — AGENTS.md 해석, CLAUDE.md 폴백, `instructions`
- [Config](https://opencode.ai/docs/config/) — opencode.json 스키마·8단계 병합
- [Agents](https://opencode.ai/docs/agents/) — `.opencode/agents/<n>.md`, mode(primary/subagent)
- [Skills](https://opencode.ai/docs/skills/) — `.opencode/skills/`, `.claude/`·`.agents/` 호환
- [Plugins](https://opencode.ai/docs/plugins/) — `tool.execute.before` 등 훅으로 가드레일
- [Permissions](https://opencode.ai/docs/permissions/) — bash 패턴 allow/ask/deny
- [Providers](https://opencode.ai/docs/providers/) — `@ai-sdk/openai-compatible` baseURL(온프레미스)
- [MCP servers](https://opencode.ai/docs/mcp-servers/)
