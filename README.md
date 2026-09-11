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
./init.sh --profile large --agent codex ~/projects/my-app   # codex는 large 전용
./init.sh --profile small --agent claude,opencode ~/projects/my-app  # small은 codex 불가
./init.sh --agent claude,codex ~/projects/my-app     # 일부만
```

Windows (PowerShell):
```powershell
git clone <이 저장소>
cd team-dev-harness
.\init.ps1 -Target C:\projects\my-app
.\init.ps1 -Profile large -Agent codex -Target C:\projects\my-app   # codex는 large 전용
```
Windows 요구사항: PowerShell 5.1 이상, Git for Windows(Git Bash 포함 —
Claude Code Windows 버전의 요구사항이기도 하다). 두 설치 스크립트의
렌더링 결과는 동일하게 설계되어 있다.
파리티 확인(코드리뷰): opencode 미포함 설치에서 `init.sh`가 종료코드 1을 내던 단축평가 버그를
고쳤고, `init.ps1`은 안내를 `if (Has-Agent ...) { ... }` 문으로 처리해 종료코드가 전파되지 않으므로 동일 버그가 없다.

- **프로파일**(`--profile`/`-Profile`, 생략 시 자동): `ANTHROPIC_BASE_URL` 또는
  `OPENAI_BASE_URL`이 사내망(내부 IP, kims, litellm, localhost)을 가리키면 **small**,
  그 외(비어 있거나 외부)는 **large**.
- **에이전트**(`--agent`/`-Agent`, 생략 시 `all`): `claude`, `codex`, `opencode`를
  콤마로 조합하거나 `all`. 선택한 에이전트의 설정만 생성된다.
  단 **codex는 large 프로파일 전용**이다 — small에서 codex가 요청되면(`all` 포함) 에러로
  차단된다. small은 `--agent claude,opencode` 로 설치한다.

설치가 끝나면 프로젝트 폴더에서 코딩 에이전트(Claude Code / Codex / opencode)를
열고 `개발 시작` 이라고 입력한다. 초보자 안내는 생성된 `dev-agent-team/guides/OWNER_GUIDE.md` 참조.

## 프로젝트 고유 규칙 (`dev-agent-team/PROJECT_RULES.md`)

이 프로젝트에서만 통하는 규칙 — 사내 라이브러리 강제, DB 접근 경로, 도메인 용어, 금지 패턴 —
은 여기에 적는다. 설치 시 빈 뼈대가 만들어지고, **재설치해도 이 파일은 건드리지 않는다.**

> `AGENTS.md`·`CLAUDE.md`·역할 프롬프트에 직접 적으면 **다음 재설치 때 사라진다.**
> 하니스가 덮어쓰는 파일이기 때문이다. 고유 규칙은 반드시 이 파일에 적는다.

### 쓰는 법

```markdown
## 규칙
형식: - 대상(전체|역할명) · 규칙 한 줄 · 이유

- 전체 · DB 접근은 반드시 common/dao 를 거친다 · 커넥션 풀을 한 곳에서 관리한다
- coder · 사내 auth-sdk 만 쓴다 · 외부 OAuth 는 보안팀 승인이 필요하다
- tester · 결제 테스트는 사내 스텁 서버만 쓴다 · 실제 PG로 호출하면 과금된다
- documenter · README에 사내 위키 링크를 넣지 않는다 · 외부 공개 저장소다
```

**대상**을 적는 이유는 메인 세션이 역할을 호출할 때 그 역할에 해당하는 규칙만 골라
넘기기 때문이다. `전체` 는 모든 역할에 전달된다. **이유**를 적어 두면 나중에 규칙이
낡았는지 판단할 수 있고, 에이전트가 규칙을 더 정확히 적용한다.

### 적으면 안 되는 것

이 파일은 헌법(`AGENTS.md`)을 **좁히는 방향으로만** 작동한다. 규칙을 더 엄하게 만들 수는
있어도 느슨하게 만들 수 없다.

| 적어도 되는 것 | 적으면 안 되는 것 (무시된다) |
|---|---|
| "함수는 25줄 이내" (헌법 40줄보다 엄함) | "함수 길이 제한 없음" |
| "외부 API 호출은 전부 C등급으로 올린다" | "보안 결정은 묻지 말고 진행" |
| "커밋 메시지에 티켓 번호를 붙인다" | "기존 테스트를 고쳐도 된다" |

안전장치(가드 훅, C등급 정지, append-only 테스트 원칙, 단일 작성자 원칙)는 이 파일로
무효화할 수 없다. 헌법과 충돌하면 **헌법이 이긴다**. 가드 훅은 파일 내용과 무관하게
독립적으로 동작하므로 실제로도 뚫리지 않는다.

`PROCESS.md`(large 전용)와는 방향이 반대다 — 그쪽은 Owner 승인을 거친 절차 개정이라
파라미터가 헌법보다 **우선**한다. 절차 자체를 바꾸려면 이 파일이 아니라 lead 회고를 통한다.

### 누가 읽나

Owner가 쓰고 에이전트는 읽기만 한다. 에이전트가 규칙을 추가하고 싶으면 `BACKLOG.md` 에
제안하고 Owner가 판단한다.

| 경로 | 방식 |
|---|---|
| Claude | `CLAUDE.md` 의 `@dev-agent-team/PROJECT_RULES.md` — 세션에 자동 주입 |
| opencode | `opencode.json` 의 `instructions` — 세션에 자동 주입 |
| Codex | import 메커니즘이 없어 `AGENTS.md` 지시(항상 지킨다 8번)로 읽는다 |
| 서브에이전트 (세 도구 공통) | 메인 세션이 역할 호출 시 해당 규칙을 넘긴다 |

## 업그레이드 (기존 프로젝트를 새 하니스 버전으로 갱신)

이미 하니스가 깔린 프로젝트는 **새 버전의 `init.sh`/`init.ps1`을 같은 대상 폴더에
다시 실행**하면 갱신된다. 별도 마이그레이션 도구는 없다 — 재실행이 곧 업그레이드다.
버전별 변경 내역은 [CHANGELOG.md](CHANGELOG.md) 참조.

```bash
# 1) 하니스 저장소를 최신으로
cd team-dev-harness && git pull

# 2) 현재 프로젝트의 버전 확인 (AGENTS.md 상단) → 저장소의 HARNESS_VERSION과 비교
grep '^HARNESS_VERSION' ~/projects/my-app/AGENTS.md
cat HARNESS_VERSION

# 3) 처음 설치 때와 같은 프로파일·에이전트로 같은 폴더에 재실행
./init.sh --profile small --agent claude ~/projects/my-app
```
Windows는 `.\init.ps1 -Profile small -Agent claude -Target C:\projects\my-app` 로 동일하다.

**무엇이 덮어쓰이고 무엇이 보존되는가:**

| 갱신됨 (하니스 소유 — 새 버전으로 덮어씀) | 보존됨 (작업 상태 — 건드리지 않음) |
|---|---|
| `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json` | `dev-agent-team/REQUIREMENTS.md`, `PLAN.json`, `PLAN.md` |
| `.claude/agents/`, `.claude/skills/`(역할·스킬 본문) | `dev-agent-team/DECISIONS.md`, `TEST_LOG.md`, `OWNER_QUESTION.md` |
| `.codex/`, `opencode.json`, `.opencode/`(guard.js 포함) | `dev-agent-team/BACKLOG.md`, `DIRECTION.md`(large), `libs/`, `answered/` |
| `dev-agent-team/hooks/*.sh`, `selfcheck.py`, `guides/` | `tests/`(제품 테스트), `logs/` |
| `common/logger.py` | |

상태 파일은 `[ -f ] || cp` 로 보호되어 **있으면 그대로 둔다**. 따라서 개발 중인
프로젝트에 재실행해도 계획·결정·테스트 이력·백로그가 사라지지 않는다.

**주의:**
- **`AGENTS.md`·`CLAUDE.md` 는 손대지 않았을 때만 갱신된다.** 설치 시 해시를
  `dev-agent-team/.harness-manifest` 에 기록해 두고, 재설치 때 **Owner가 편집했으면 덮어쓰지
  않고** 새 버전을 `AGENTS.md.new` 로 두고 알린다(dpkg conffile 방식). manifest가 없는
  1.27.0 이전 프로젝트는 `.bak` 백업 후 갱신한다.
- **그래도 고유 규칙은 `dev-agent-team/PROJECT_RULES.md` 에 적는 것이 맞다.** `AGENTS.md` 를
  편집하면 이후 헌법 갱신이 `.new` 로만 쌓여 규칙이 낡은 채 고착된다. `PROJECT_RULES.md` 는
  애초에 덮어쓰기 대상이 아니라 이 문제가 없다.
- **강제 장치는 예외 없이 덮어쓴다** — `.claude/settings.json`(deny 목록), `dev-agent-team/hooks/*.sh`,
  `guard.js`, `opencode.json`, `.codex/*`, 역할·스킬, `selfcheck.py`. 낡으면 안전 계약이
  깨지므로 편집해도 원복된다.
- `common/logger.py` 는 **무조건 덮어쓴다**(고정 포맷 제품 로거 — Python 구현이자 로그 형식의
  참조 규격). 직접 손댄 경우 먼저 백업한다. 제품이 다른 언어면 1단계에서 `logging-rule` 의
  최소 구현으로 `common/logger.go|rs|js` 를 만든다.
- 1.22.0 이전에 만든 프로젝트의 `dev-agent-team/TEST_LOG.md` 는 표가 5열이다. 재설치하면
  init이 자동으로 **7열로 올리고** 기존 행의 새 두 칸을 `-` 로 채운다. 원본은
  `TEST_LOG.md.bak` 으로 남는다. 헤더를 손으로 고쳐 열 이름이 다르면 건드리지 않는다.
- 기존 `.git` 이 있으면 init은 **자동 커밋하지 않는다**. 재실행 후 `git diff` 로 변경을
  검토하고 직접 커밋한다(하니스 파일만 바뀌었는지 확인하는 안전장치이기도 하다).
- **처음과 같은 `--profile`·`--agent`** 로 실행한다. init은 *선택한* 역할·에이전트만
  쓰고 빠진 것을 지우지 않으므로, 예컨대 `all`→`claude` 로 바꾸면 이전 `.codex`/
  `.opencode` 파일이, large→small 로 바꾸면 `lead`/`reviewer`/`critic`/`security`
  역할 파일과 `DIRECTION.md` 가 **고아로 남는다**. 의도적으로 줄일 때는 해당 파일을 직접 지운다.
  (small↔large 전환은 상태가 전부 파일에 있어 무손실이다 — "호환성 계약" 절 참조.)
- 재실행 끝에 `verify_hooks.sh` 가 자동으로 돌아 가드레일 20/20 PASS를 확인한다. 실패 시
  종료 코드 1로 멈추므로, 그 상태로 쓰지 말고 점검한다.

## 저장소 구조

```
HARNESS_VERSION          # 버전 (호환성 계약 변경 시 올림)
CHANGELOG.md             # 버전별 변경 이력 (HARNESS_VERSION과 일치)
init.sh                  # 설치 (macOS/Linux): 판별 → 렌더링 → hook 검증
init.ps1                 # 설치 (Windows): 동일 로직의 PowerShell 포팅
profiles/
  small.conf             # 온프레미스 LLM용 파라미터
  large.conf             # 외부 대형 모델용 파라미터
templates/
  AGENTS.md.tmpl         # 공통 헌법 (모든 에이전트가 읽음)
  CLAUDE.md.tmpl         # Claude 전용 오버레이 (@AGENTS.md import)
  settings.json.tmpl     # Claude 권한 allow/deny + hook 등록
  roles/                 # planner, tester, coder, checker, documenter, designer(UI 단계) (+large: lead, reviewer, critic, security) 본문 (단일 소스)
  skills/                # team-dev(절차), logging-rule, lib-research, code-convention, test-design, ui-design
  hooks/                 # Owner 질문 정지, 테스트 보호 (→ dev-agent-team/hooks/)
  codex/                 # config.toml, hooks.json (Codex 오버레이)
  opencode/              # opencode.json, plugins/guard.js (opencode 오버레이)
  common/logger.py       # 제품용 공통 로거 (고정 포맷) → 설치 시 common/
  docs/                  # OWNER_GUIDE, DEBUG_GUIDE → 설치 시 dev-agent-team/guides/
  project/               # DECISIONS, TEST_LOG, BACKLOG, PROJECT_RULES, libs INDEX, selfcheck.py → 설치 시 dev-agent-team/
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

> Claude Code에서는 10개 역할 전부에 모델과 추론 강도를 명시적으로 고정한다 — 전략적 판단·고위험 역할(`planner`/`lead`/`reviewer`/`critic`/`security`)과 추론 부담이 큰 구현·설계 역할(`coder`/`tester`/`designer`)은 `model: opus`, 나머지 실행 역할(`checker`/`documenter`)은 `model: sonnet`. **`effort: high`는 10개 역할 전부에 동일하게 붙는다** — 역할별로 추론 강도를 낮추지 않는다는 Owner 방침이다(품질 우선, 비용·지연은 감수). codex/opencode는 frontmatter에 model 개념이 없어 세션 기본 모델을 그대로 쓴다. 다만 codex는 서브에이전트가 없어 역할별 지정은 못 해도, `.codex/config.toml`의 `model_reasoning_effort = "high"`로 세션 전체 추론을 강화한다(codex는 large 전용이라 항상 적용). claude가 역할별로, codex가 세션 전체로 추론 강도를 정하지만 결과적으로 둘 다 high로 수렴하는 대칭 구조다. (model/effort 지정은 Claude 전용 frontmatter라 상태 파일·small↔large 핸드오프 계약과 무관하다.)

## 역할 구성 (small vs large)

small은 6역할(공통 5 + UI 단계 designer), large는 10역할(+ large 전용 4)이다.
designer는 양 프로파일 공통이지만 UI/화면이 있는 단계에서만 호출된다(설계 명세만 산출, 코드는 coder).

| 역할 | 책임 | 도구 | small | large | 호출 시점 |
|---|---|---|:--:|:--:|---|
| planner | 단계 분해·B등급 결정·Owner 질문 (large: + 요구사항 충돌·누락 점검) | Read, Write | ✅ | ✅ | 계획·단계 시작 |
| tester | 테스트케이스 작성 (large: 추가 엣지 탐색) | Read, Write | ✅ | ✅ | 단계 |
| coder | 구현(테스트 통과) | Read, Write, Edit, Bash | ✅ | ✅ | 단계 |
| checker | `pytest` 전체 실행·PASS/FAIL 판정(객관 검증) | Bash, Read | ✅ | ✅ | 단계 |
| documenter | README·사용법 생성 | Read, Write, Edit, Bash | ✅ | ✅ | 종료 |
| designer | UI 설계 명세(토큰·컴포넌트·상태·접근성·반응형, 코드 아님) | Read, Write | ✅ | ✅ | UI 단계(7c) |
| lead | 방향·우선순위·백로그 그루밍·회고(팀장) | Read, Grep | ✕ | ✅ | 계획 전(4-0)·단계 시작(7-0)·단계 회고(12c)·최종 회고(17b) |
| critic | 결정 심의·반론·합의(모호·고위험만 Owner로) | Read, Grep | ✕ | ✅ | planner 결정 직후(7b) |
| reviewer | 코드·테스트 품질 리뷰 | Read, Grep | ✕ | ✅ | PASS 후 merge 전 |
| security | 보안 위험 점검(맥락 판단) | Read, Grep | ✕ | ✅ | PASS 후 merge 전 |

> `documenter`의 Bash는 **확인 전용**이다 — 진입점·의존성 조회와 `--version`/`--help` 같은
> 부작용 없는 호출로 README의 설치·실행 명령이 실제로 맞는지 확인하는 데만 쓴다. 파일 변경·
> 설치·커밋은 역할 본문에서 금지하고, tests/ 수정은 가드 훅이 기계적으로 막는다.

**설계 원칙**: 주관적 판정(리뷰·결정 심의 = lead·critic·reviewer·security)은 작은 모델의
과신·불안정 위험을 피해 **large 전용**. 객관적 검증(`checker`의 테스트 러너 실행 +
`dev-agent-team/selfcheck.py` 의 print·보안 스캔, R번호 추적성, 코드 규모 임계)은 **양쪽 공용**이며,
`selfcheck.py --gate` 로 **단계 merge 전 게이트**가 된다 — 결정적 4종(collect·print·trace·
full-test)은 병합을 막고, security·size는 후보·근사라 출력만 한다. 고위험·모호성은 양쪽 모두
Owner 합의(C등급 정지)를 유지한다.

> 보안: small은 `dev-agent-team/selfcheck.py`의 정규식 기반 보안 스캔(객관)으로 점검하고,
> large는 여기에 security 에이전트(맥락 판단)를 더한다.
> selfcheck는 제품 언어(python/go/rust/node)를 감지해 해당 소스만 스캔하며, 감지된 언어가
> 없으면 점검을 건너뛴다. 보안 스캔 외에 **R번호 추적성**(REQUIREMENTS→PLAN covers→테스트
> 이름→README의 끊어진 고리)과 **코드 규모 임계**(함수 40줄·인자 5개·중첩 3단계)도 본다 —
> 둘 다 판단이 없는 결정적 검사라 small에서도 reviewer 없이 쓸 수 있다.

## 프로파일 차이 (이 13가지만 다르다)

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
| 절차 자기개선 (lead 회고 → Owner 승인 → PROCESS.md) | 없음 | 있음 (단계 회고 12c·최종 회고 17b, 재발 신호 있을 때) |

## 호환성 계약 (프로파일과 무관하게 동일 — 변경 시 버전 올림)

1. 파일 위치/형식: AGENTS.md(공통 헌법), dev-agent-team/ 레이아웃, dev-agent-team/PLAN.json 스키마,
   dev-agent-team/DECISIONS.md / dev-agent-team/TEST_LOG.md / dev-agent-team/OWNER_QUESTION.md / dev-agent-team/libs/ 형식,
   TEST_LOG.md 는 7열 고정(단계·신규·누적·전체 결과·재시도·리뷰지적·커밋)이며 열 구성은
   양 프로파일 동일하다 — 리뷰 단계가 없는 프로파일은 리뷰지적을 `-`로 채운다,
   dev-agent-team/PROCESS.md 형식(P번호·append-only, large 전용), 커밋 메시지, 브랜치 이름.
   OWNER_QUESTION.md는 기존 동작을 바꾸는 질문일 때 선택지별 영향 표보다 먼저
   "지금 → 앞으로"(AS-IS/TO-BE, 행 3개: 동작·Owner가 보는 것·데이터·파일) 표를 둔다.
   DECISIONS.md에는 그런 결정일 때 `- 변경: AS-IS → TO-BE` 줄이 들어간다.
2. C등급 목록(요구사항 변경, 삭제, 비용, 외부 배포, 보안, GPL, 외부 데이터 약관·저작권)과
   정지 메커니즘 (dev-agent-team/OWNER_QUESTION.md → 가드레일 차단, "답: 번호"로 해제).
   단계 merge 전 `selfcheck.py --gate` 게이트(collect·print·trace·full-test 차단)도 절차 계약이다.
   Gate 0(요구사항 확인)과 Gate 1(계획 승인)은 **3지선다**다 — 1.진행 / 2.수정 / 3.지금은
   하지 않음. 3을 골라도 REQUIREMENTS.md·PLAN.json·PLAN.md는 지우지 않는다.
   Owner가 답하기 전에는 다음 단계로 넘어가지 않는다.
   테스트 실행 범위(구현 직후·merge 직전은 FULL, 그 사이 루프는 SCOPED)와
   `dev-agent-team/.last-full-test` 신선도 강제도 계약에 포함된다.
3. deny/차단 목록 (rm -rf, hard reset, git branch -D, python -c·node -e inline 실행 우회,
   curl·wget 포함). 일반 git push는 allow(작업 브랜치). **force push는 deny가 아니라 ask** —
   Owner가 그 자리에서 승인하면 에이전트가 실행한다. 규칙은 `deny → ask → allow` 순으로
   평가되므로 `git push` allow 보다 force용 ask가 우선한다. main 직접 push 금지는 AGENTS.md
   규칙으로 병행한다(규칙 문자열로는 브랜치를 가릴 수 없다).
4. append-only 테스트 원칙 (가드레일로 강제 — py/go/rs/js·ts 테스트 공통).
   Write/Edit·apply_patch뿐 아니라 **Bash 쓰기 명령**(`>` `>>`/tee/sed -i/mv/cp/rm/
   truncate/dd of=/patch)도 차단 대상이다. 읽기·실행은 통과시킨다.
5. 로그 형식 `[HH:MM:SS] [LEVEL] [모듈] 동작 | key=value` — `logs/app.log` 에 append하고
   표준출력에도 같은 줄을 낸다. 언어와 무관하게 동일하며 `logging-rule` 스킬이 정본이다.
6. 역할 구조와 역할 경계(공통 5 + designer(UI 단계) + large 전용 lead·reviewer·critic·security)
   및 designer 산출물 dev-agent-team/DESIGN.md 형식. lead는 방향·백로그 외에 회고·절차 개선제안(IMPROVE)도 낸다(large 전용).
   lead 호출 모드 3종(방향·단계 회고·최종 회고)과 호출 시점(4-0/7-0/12c/17b), BACKLOG "메모·주의"의
   출처 표기 형식(`- 설명 · 출처:stageN/역할`)도 계약에 포함된다.
7. 공유 상태 파일은 메인 세션만 쓴다 (단일 작성자 원칙; PROCESS.md 포함)

이 계약은 에이전트와 무관하게 동일하다. 가드레일 **강제 방식만** 에이전트별로
다르다(Claude=hook, Codex=hook.json, opencode=플러그인). 이 덕분에 **모델 전환과
에이전트 전환 인수인계**가 가능하다: small↔large, Claude↔Codex↔opencode 어느 쪽으로
넘겨도 상태가 전부 dev-agent-team/ 파일에 있으므로 무손실로 계속된다.

## 배포 전 검증 (관리자용)

1. `./init.sh --profile small --agent claude,opencode /tmp/t1` 과 `--profile large /tmp/t2` 실행,
   hook 검증 21항목 전부 PASS 확인 (init.sh가 자동 수행). small은 codex를 포함할 수 없다(에러).
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
  컨테이너로 돌릴 때는 **반드시 TTY를 붙인다** — `docker run -it -v "$PWD":/work -w /work ...`
  (devcontainer는 기본으로 붙는다). 승인을 물어보는 규칙(`ask`)이 있어서, TTY가 없으면
  그 질문이 뜰 곳이 없다.
- **Bash 경유 테스트 수정 차단은 휴리스틱이다.** `protect_tests.sh`/`guard.js`는 명령문에서
  쓰기 위치(`>` `>>`, `tee`, `sed -i`, `mv`, `cp`, `rm`, `truncate`, `dd of=`, `patch`)에 온
  경로만 골라 막는다. 읽기·실행(`cat`, `grep`, `pytest`)은 통과시켜야 하므로 셸을 완전히
  파싱하지 않으며, 변수 확장·명령 치환·here-doc 조합으로 우회할 수 있다. 샌드박스가 아니라
  과속방지턱으로 보고 AGENTS.md 규칙을 병행한다.
- **로그 형식은 언어 무관, 설치되는 로거 구현은 Python 것뿐이다.** 형식
  (`[HH:MM:SS] [LEVEL] [모듈] 동작 | key=value`)은 `logging-rule` 스킬에 명시돼 있고, 설치
  시점에는 제품 언어를 알 수 없어(0단계 인터뷰가 설치 후다) `common/logger.py` 만 깔린다.
  Go·Rust·JS·TS 프로젝트는 **1단계에서** `logging-rule` 의 의존성 없는 최소 구현을 복사해
  `common/logger.go|rs|js` 를 만든다. 그 전까지는 `logs/app.log` 가 없을 수 있다.
  `selfcheck.py` 의 print·보안 스캔은 네 언어를 모두 다루지만, **테스트 수집 확인은 Python
  전용**이라 다른 언어에서는 건너뛴다(테스트 실행은 `checker`가 제품 언어 러너로 매 단계 한다).
- **검사는 세 시점으로 나뉜다.** *commit 전*은 싼 결정적 검사만(테스트 커밋 전 `[collect]`,
  구현 커밋 전 `--gate` 조기 필터·checker SCOPED). *push 시*는 remote가 있을 때만 돌고 작업
  브랜치인지 확인한다. *PR 시*(main 합치기 직전, 단계당 1회)에 checker FULL·`--record-full-test`·
  `--gate` 4종·reviewer·security(large)가 모인다. main 합류 지점은 하나다 — remote가 있으면 PR,
  없으면 로컬 merge이고 **게이트 내용은 같아서** 오프라인·온프레미스에서도 절차가 그대로 돈다.
  정본은 team-dev 스킬의 "언제 무엇을 하나" 표다.
- **git push와 PR 생성은 `ask`다** — 에이전트가 승인을 받고 직접 실행한다. 브랜치 생성은 도구
  권한으로는 allow고, 승인은 Gate 1(계획 승인)이 계획째로 겸한다. 절차 필수라 도구 `ask`로
  두면 승인 창이 없는 headless 환경에서 1단계에서 멈추기 때문이다. 계획에 없는 브랜치는 C등급.
- **git push는 작업(stage/feature) 브랜치에 허용**한다(개발팀 브랜치 워크플로). 단 main 직접
  push는 금지하고 force push(`--force`/`-f`)는 **Owner 승인 후 허용**한다 — force는 가드 ask로
  물어보고, main 금지는 AGENTS.md 규칙으로 강제한다.
- **force push는 Owner 승인을 물어본다(ask).** 승인 프롬프트가 뜨지 않는 환경에서는 완화가
  아니라 구멍이 된다 — 특히 **opencode의 `ask`는 UI나 터미널이 없는 headless 컨테이너에서
  멈추거나 예측 불가하게 동작한다.** 세 겹으로 막아 둔다:
  1. **절차상 force push는 Owner가 요청할 때만 시도한다.** 에이전트가 스스로 판단해서 하지
     않으므로, Owner가 없는 headless 환경에서는 애초에 일어나지 않는다.
  2. **컨테이너는 TTY를 붙여 띄운다**(위 `docker run -it`). 승인 창이 뜰 곳을 만들어 준다.
  3. 그래도 승인이 안 되면 **하지 않고 Owner에게 보고**한다 — 이 절차는 force push 없이
     끝까지 돌기 때문에 진행이 막히지 않는다.
  `git -C . push --force` 같은 우회 형태는 규칙이 잡지 못한다(deny였을 때도 같았다) —
  가드 규칙은 샌드박스가 아니라 과속방지턱이다.
- **Windows에서는 줄 끝과 파이썬 이름이 문제가 된다.** Git for Windows 기본값
  (`core.autocrlf=true`)으로 클론하면 `.sh` 가 CRLF가 되어 가드 훅이 깨진다 —
  `block_on_owner_question.sh` 는 exit 255로 실행 실패하는데 그 값은 "차단"(exit 2)으로
  해석되지 않아 **Owner 질문 대기 중에도 에이전트가 그냥 진행한다**. 두 군데를 고정한다:
  이 저장소는 자체 `.gitattributes` 로, **생성되는 프로젝트는 설치되는 `.gitattributes`**
  로 막는다(Owner가 이미 쓰던 파일이면 덮지 않고 필요한 줄만 끝에 덧붙인다).
  `AGENTS.md`·`CLAUDE.md` 는 줄 끝을 고정하지 않는 대신 **conffile 해시를 CR 제거 후**
  계산한다 — 그러지 않으면 git이 바꾼 줄 끝을 Owner 편집으로 오인해 `.new` 만 쌓이고
  헌법이 영영 갱신되지 않는다. `protect_tests.sh` 는 `python3` → `python` 순으로
  실행기를 찾고, **둘 다 없거나 추출이 실패하면 통과시키지 않고 차단한다**(fail-closed).
  설치 시 `verify_hooks.sh` 19·20·21번이 이 세 상태를 탐지한다.
- **`PROJECT_RULES.md` 자동 주입은 Codex에서만 안 된다.** Claude는 `CLAUDE.md` 의 `@import`,
  opencode는 `opencode.json` 의 `instructions` 로 세션에 자동으로 들어간다. Codex에는 import
  메커니즘이 없어 `AGENTS.md` 지시(항상 지킨다 8번)에 의존한다. 서브에이전트에는 세 도구 모두
  메인 세션이 해당 규칙을 넘겨준다(team-dev 절차).
- **Codex는 `.codex` 설정이 trusted 프로젝트에서만 적용된다.** 설치 후 안내대로
  `~/.codex/config.toml` 의 `[projects]` 에 프로젝트를 등록해야 한다.
- **Codex에는 서브에이전트가 없다.** 역할(공통 5 + UI 단계 designer + large 전용 4)은
  `.agents/skills/` 스킬로 제공되며 단일 에이전트가 순차로 수행한다(Claude·opencode는 서브에이전트로 위임).
- **Codex는 large 프로파일 전용이다.** 외부 대형 추론 모델을 전제하므로 small(온프레미스)에서
  codex가 요청되면(`all` 포함) 설치가 에러로 중단된다. small은 `--agent claude,opencode` 로 설치한다.
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

### 강제력 비교 (실측 기준)

같은 규칙이라도 **자동 강제 정도**는 에이전트마다 다르다. 아래는 산출물을 설치해
확인한 결과다(✅ 확실히 강제 / ⚠️ 조건부·부분 / ❌ 미강제, 프롬프트 규율에만 의존).

| 강제 항목 | Claude Code | Codex CLI | opencode |
|---|---|---|---|
| C등급 Owner 질문 정지 | ✅ hook exit 2 | ✅ 파일 기반이라 발화 시 작동 | ✅ 플러그인 throw |
| 기존 테스트 보호(py/go/rs/js·ts) | ✅ exit 2 | ⚠️ apply_patch 인식하나 전용 훅 미발화 가능(셸 경유만 보장) | ✅ 플러그인 throw |
| 역할별 도구 격리(단일 작성자) | ✅ 서브에이전트 `tools` | ❌ 서브에이전트 없음 → 규율만 | ✅ 서브에이전트 `tools` |
| 명령 deny(rm -rf·hard reset·python -c·node -e 등; 일반 git push는 allow, force push는 ask) | ✅ settings.json allow/ask/deny | ⚠️ deny 목록 없음 → sandbox+approval(거친 경계) | ✅ opencode.json allow/ask/deny |
| 테스트 실행(pytest·go test·cargo test·npm test) | ✅ allow 등록(프롬프트 없음) | ✅ sandbox 안 자동 실행 | ✅ wildcard allow |
| 선행 조건 / 런타임 | 없음(bash) | trusted 등록 필요·apply_patch/MCP 훅 불안정 | bun/node 필요(없으면 플러그인 미로딩) |
| Windows | ✅ | ❌ 훅 미지원 | ✅ node 있으면 |

테스트는 언어 무관으로 동일 취급한다 — 세 에이전트 모두 pytest·go test·cargo test·npm test 를
프롬프트 없이 실행하고(Claude=allow 등록, Codex=sandbox 자동, opencode=wildcard), 기존 테스트
파일(py/go/rs/js·ts) 수정은 똑같이 차단된다. inline 임의코드(`python -c`·`node -e`)는 deny다.

요약: **opencode는 가드레일·역할 격리·deny 모두 Claude와 동등**하다(런타임만 추가 요구).
**Codex는 프로세스(5역할·헌법·정지 흐름)는 동일하나 자동 강제가 약해** — 테스트 보호가
훅 미발화 시 빠지고, 역할 도구 격리·명령 deny가 정밀하지 않다. 따라서 Codex/opencode에서는
AGENTS.md 규칙 병행과 컨테이너 격리를 권장한다(아래 "설계에 주는 함의" 참조).

### 설계에 주는 함의

- **AGENTS.md = 공통 헌법.** 셋 다 읽힌다. Claude Code만 `CLAUDE.md`에서 `@AGENTS.md`로
  끌어오거나 심볼릭으로 연결한다.
- **스킬은 `.agents/skills/` + `.claude/skills/` 두 곳**에 두면 셋 다 커버된다
  (`.agents/`=Codex 네이티브+opencode 호환, `.claude/`=Claude Code+opencode 호환).
- **5-에이전트(planner/tester/coder/checker/documenter) + UI 단계 designer + large 전용 lead·reviewer·critic·security**: Claude·opencode는
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
