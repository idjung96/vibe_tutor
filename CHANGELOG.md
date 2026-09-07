# Changelog

이 파일은 team-dev-harness(하니스 생성기)의 버전별 변경을 기록한다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전은 `HARNESS_VERSION`(호환성 계약)과 일치한다.

## [1.19.0] - 2026-09-07

### Added
- **Owner 질문에 "지금 → 앞으로"(AS-IS/TO-BE) 표** — 기존 동작을 바꾸는 C등급 질문이면
  `dev-agent-team/OWNER_QUESTION.md` 맨 위, 선택지별 영향 표보다 **먼저** 온다.
  행 3개 고정(동작 / Owner가 보는 것 / 데이터·파일), 열은 `항목 | 지금 (AS-IS) | 1안 | 2안`.
  지금까지 Owner는 선택지들만 비교했지 **현재 어떻게 동작하는지**를 볼 수 없어서, 무엇을
  잃고 무엇을 얻는지 판단하기 어려웠다. 새로 만드는 기능이면 표 대신
  "신규 기능(바뀌는 동작 없음)" 한 줄을 적는다.
- `dev-agent-team/DECISIONS.md` 형식에 `- 변경: AS-IS → TO-BE` 줄. 기존 동작을 바꾼 결정만
  해당하며 신규는 생략한다. 나중에 기록을 읽을 때 "그 전에는 어땠는데?"가 남는다.
- `OWNER_GUIDE.md` "질문이 올 때"에 이 표를 먼저 보라는 안내 한 줄.

### Changed
- **영향 표는 그대로 둔다.** "지금 → 앞으로"(무엇이 달라지나 — 이해용)와 선택지별 영향 표
  (비용·되돌리기 — 판단용)는 목적이 달라 한 표로 합치지 않았다. 기존 5항목(기능·코드 변경·
  일정·테스트·되돌리기)과 마지막 "답:" 줄은 문구까지 유지된다.
- **표 재료를 내는 역할이 AS-IS/TO-BE를 함께 넘긴다(large 전용)** — planner가 현재 동작을
  추측하지 않도록. `lead`의 `IMPROVE`는 `대상 · AS-IS · TO-BE · 근거`, `critic`의
  `RECOMMEND`는 `추천안 · AS-IS → TO-BE` 형태가 됐다. **출력 필드 개수는 그대로**라
  메인 세션 파싱은 바뀌지 않는다.
- 표는 planner 한 곳에서만 만든다. `critic`의 `ALTERNATIVE`(→planner)와 `reviewer`의
  `FINDINGS`(→coder)는 Owner가 읽는 것이 아니라 건드리지 않았다.

### Compatibility
- `OWNER_QUESTION.md`·`DECISIONS.md` 형식이 호환성 계약이므로 `HARNESS_VERSION`을 1.19.0으로
  올린다. 표는 **추가**이고 기존 영향 표·"답: 번호" 정지 해제 메커니즘은 그대로라
  small↔large 무손실 핸드오프는 계속 성립한다.
- 이번 변경은 **양 프로파일 공통**이다(planner·DECISIONS·OWNER_GUIDE가 공통 산출물).
  large 전용은 lead·critic 출력 형식뿐이다.
- `init.sh`/`init.ps1`, 가드 훅, `verify_hooks.sh`(18항목)는 건드리지 않았다.

## [1.18.0] - 2026-09-07

### Added
- **단계 종료 회고 신설(large 전용, `12c`)** — 단계가 merge된 뒤 `lead`를 "단계 회고" 모드로
  매 단계 빠짐없이 호출한다. 지금까지 lead의 회고 절은 존재했지만 호출 시점이 단계 **시작**
  (7-0)뿐이라 사실상 사전 점검이었다. 메인 세션이 그 단계의 증거(CHECKER_CALLS, NEW_FAIL/
  REGRESSION 횟수, REVIEWER CHANGES 반복 횟수, SECURITY 결과, CRITIC REVISE/ESCALATE 횟수,
  신규 BACKLOG 건수)를 인라인으로 넘긴다 — 새 상태 파일은 만들지 않는다.
- **프로젝트 최종 회고 신설(large 전용, `17b`)** — documenter(17)와 결과 보고(18) 사이에
  lead를 "최종 회고" 모드로 부른다. 기존 번호를 밀지 않도록 `7b`/`12c`와 같은 접미 번호를 썼다. TEST_LOG 전체·BACKLOG 두 섹션·DECISIONS·
  PROCESS와 12c에서 쌓인 `[절차개선]` 항목을 함께 본다.
- **lead 호출 모드 3종** — 방향(4-0·7-0) / 단계 회고(12c) / 최종 회고(17b). 메인 세션이
  모드를 알려주고, 해당 없는 출력 항목은 "없음"으로 둔다. **출력 형식 5필드
  (DIRECTION/PRIORITIES/GROOMING/IMPROVE/ESCALATE)는 그대로**라 파싱은 바뀌지 않는다.

### Changed
- **reviewer·security 지적이 lead에게 흐른다** — 지금까지 FINDINGS는 coder에게만 가고 고치면
  사라져서(RETRY_LIMIT 초과분만 BACKLOG에 남았다) "매 단계 같은 유형이 반복된다"는 신호가
  lead의 회고 입력에 도달하지 못했다. 이제 **고친 지적도** 유형을 `BACKLOG.md` "메모·주의"에
  `- 설명 · 출처:stageN/역할` 형식으로 남긴다. 처리 대상이 아니라 재발 신호용 기록이다.
- **lead 회고 신호 3개 → 5개** — reviewer FINDINGS가 여러 단계에 걸쳐 같은 유형으로 반복,
  security RISK 반복을 추가했다.
- **단계 회고의 IMPROVE는 즉시 Owner를 멈춰 세우지 않는다** — BACKLOG "할 일"에
  `[절차개선]` 표시로 쌓아두고, 다음 단계 시작(7-0)이나 최종 회고(17b)에서 **한 번에 하나만**
  C등급으로 올린다. 매 단계 Owner 개입이 생기는 것을 막기 위해서다. 방향 차원 ESCALATE는
  기존대로 즉시 14번으로 간다.
- `templates/project/BACKLOG.md`의 "메모·주의" 섹션에 형식 줄을 추가했다. 이 섹션은 이제
  의도적으로 누적된다 — 오래된 항목 정리는 lead가 그루밍에서 제안할 수 있다.

### Compatibility
- 역할 경계(lead 호출 모드·시점)와 BACKLOG "메모·주의" 형식이 바뀌므로 `HARNESS_VERSION`을
  1.18.0으로 올린다. team-dev 절차의 기존 번호는 그대로다(신설분은 12c·17b). PLAN.json 스키마·
  DECISIONS/TEST_LOG/OWNER_QUESTION/PROCESS 형식·small↔large 핸드오프 계약은 그대로다.
- **small 프로파일은 절차가 그대로다.** 회고 관련 추가는 전부 `{{#IF_LARGE}}` 안에 있다.
  small 렌더 결과에서 1.17.0과 다른 것은 버전 문자열과 BACKLOG "메모·주의" 형식 줄뿐이다.
- `init.sh`/`init.ps1`, 가드 훅(`protect_tests.sh`/`guard.js`), `verify_hooks.sh`(18항목)는
  건드리지 않았다.

## [1.17.0] - 2026-09-04

### Added
- **`documenter`에 확인 전용 Bash 부여** — `tools`가 `Read, Write, Edit` → `Read, Write, Edit, Bash`
  (opencode는 `bash: true`). documenter는 "설치/실행 명령이 실제 진입점과 일치하는가"를 자체
  점검 항목으로 요구하면서도 실행 수단이 없어 파일을 읽고 추정할 수밖에 없었다. 이제 진입점·
  의존성 조회와 `--version`/`--help` 같은 부작용 없는 호출로 직접 확인한다. 파일 변경·패키지
  설치·git 쓰기·서버 기동은 역할 본문(`templates/roles/documenter.md.tmpl`)에서 금지한다.
- **가드 훅이 Bash 명령문까지 검사** — `protect_tests.sh`와 `guard.js`가 명령문에서 **쓰기
  위치에 온 경로만** 추출해 기존 테스트 수정을 차단한다: `>` `>>` 리다이렉션 대상, `tee`/`mv`/
  `rm`/`truncate`/`patch`의 비플래그 인자, `cp`의 목적지, in-place 플래그가 있을 때의 `sed`,
  `dd of=`. `.claude/settings.json`의 matcher도 `Write|Edit` → `Write|Edit|Bash`.
  읽기·실행(`cat`/`grep`/`pytest`)은 통과시킨다 — 여기서 막으면 checker가 죽는다.
- `tests/verify_hooks.sh` 14항목 → **18항목**. 15·16은 Bash 우회 차단, 17·18은 checker
  오탐 방지 회귀(실행+리다이렉션, 조회)를 고정한다.

### Changed
- **`mv`는 원본도 차단 대상이다** — `mv tests/old_test.py tests/new_test.py` 같은 rename도
  막힌다. 원본을 옮기면 기존 테스트가 사라지므로 append-only 원칙상 의도한 동작이다.

### Compatibility
- 호환성 계약 4번(append-only 테스트 원칙)의 **강제 범위**가 넓어지고 역할 경계(documenter
  도구)가 바뀌므로 `HARNESS_VERSION`을 1.17.0으로 올린다. 상태 파일 형식·small↔large
  핸드오프 계약은 그대로다.
- 셸 파싱은 휴리스틱이다. 변수 확장·명령 치환·here-doc 조합으로 우회 가능하며, 샌드박스가
  아니라 과속방지턱이다(README "알려진 제약" 참조).

## [1.16.0] - 2026-07-29

### Changed
- **fable 역할 전부 opus로 환원 + designer도 opus로 승격**(Claude 전용) — `planner`/`lead`/
  `reviewer`/`critic`/`security`의 `model: fable`을 `model: opus`로 되돌리고, `designer`도
  `sonnet` → `opus`로 올린다. 결과적으로 `checker`/`documenter`만 `model: sonnet`이고
  나머지 8역할이 `model: opus`다.
- **`effort: high`를 전 역할 공통으로 고정** — 1.14.0에서 도입한 역할별 차등(`low`/`medium`,
  구현 역할은 미지정=세션 상속)을 없앤다. `role_effort()`/`Role-Effort()`는 이제 역할과 무관하게
  항상 `high`를 반환하며, 10개 역할 모두 frontmatter에 `effort: high`가 붙는다. 품질 우선
  방침(비용·지연은 감수)에 따른 Owner 결정. `init.sh`·`init.ps1`을 함께 갱신.

### Compatibility
- model/effort per-role 지정은 **Claude 전용 frontmatter**라 호환성 계약 항목이 아니다 — 상태 파일
  레이아웃·PLAN.json 스키마·small↔large 무손실 핸드오프가 모두 불변. codex는 skill이라 모델
  미지정(`model_reasoning_effort="high"` 유지), opencode도 세션 기본 모델을 쓴다(둘 다 불변).
  가시성 위해 `HARNESS_VERSION` 1.15.0 → 1.16.0(minor). 가드 3경로·verify_hooks(14)·로그 형식 불변.

## [1.15.0] - 2026-07-26

### Changed
- **coder·tester를 sonnet → opus로 승격**(Claude 전용) — 구현+디버깅이 얽힌 `coder`와
  요구사항→테스트케이스 설계를 하는 `tester`에서 sonnet의 산출물 품질이 부족하다는 Owner 관찰에
  따라 `model: opus`로 올린다. effort는 미지정 유지(=세션 상속). 나머지 구현·실행 역할
  (`checker`/`documenter`/`designer`)은 `model: sonnet` 유지 — 추론 부담이 낮아 승격 효과가
  과함. 판단 역할(`planner`/`lead`/`reviewer`/`security`=fable+low, `critic`=fable+medium)은
  1.14.0 그대로. `init.sh`의 `role_model()`·`init.ps1`의 `Role-Model()`을 함께 갱신.

### Compatibility
- model per-role 지정은 **Claude 전용 frontmatter**라 호환성 계약 항목이 아니다 — 상태 파일
  레이아웃·PLAN.json 스키마·small↔large 무손실 핸드오프가 모두 불변. codex는 skill이라 모델
  미지정, opencode도 세션 기본 모델을 쓴다(둘 다 불변). 가시성 위해 `HARNESS_VERSION`
  1.14.0 → 1.15.0(minor). 가드 3경로·verify_hooks(14)·로그 형식 불변.

## [1.14.0] - 2026-07-10

### Changed
- **판단 역할을 opus → fable + effort:low로 재조정**(Claude 전용) — `planner`/`lead`/
  `reviewer`/`security`의 `model: opus`를 `model: fable` + `effort: low`로 바꾼다. 상위 세대인
  fable을 낮은 추론 강도로 돌리는 편이 옛 opus를 높은 강도로 돌리는 것보다 빠르고 저렴하면서
  판단 품질이 낫다는 Owner 라우팅 원칙(판단→fable). `critic`은 이미 fable이었고 되돌리기 비용이
  가장 커서 `effort: medium`으로 한 단계 높인다. 구현·실행 역할(coder/checker/documenter/
  tester/designer)은 `model: sonnet` 유지(effort 미지정=세션 상속). `init.sh`의 `role_effort()`·
  `init.ps1`의 `Role-Effort()`가 새로 emit하며, `effort` frontmatter는 Claude Code v2.1.198+ 지원.

### Compatibility
- model/effort per-role 지정은 **Claude 전용 frontmatter**라 호환성 계약 항목이 아니다 —
  상태 파일 레이아웃·PLAN.json 스키마·small↔large 무손실 핸드오프가 모두 불변. codex는 자체
  모델을 `model_reasoning_effort="high"`로 쓰고(fable 아님), opencode는 세션 기본 모델을 쓴다(불변).
  가시성 위해 `HARNESS_VERSION` 1.13.0 → 1.14.0(minor). 가드 3경로·verify_hooks(14)·로그 형식 불변.

## [1.13.0] - 2026-07-08

### Changed
- **git push를 allow로 재분류** — 개발팀이 stage/feature 브랜치에 자주 push하는 워크플로에 맞춰
  일반 `git push`를 허용한다. Claude `settings.json`은 deny에서 `git push:*`를 빼고 allow로 옮기며,
  opencode `opencode.json`은 `git push*` deny를 제거(기본 allow). AGENTS.md·team-dev 금지 규칙도
  "작업 브랜치 push 허용, main 직접 push·force push 금지"로 갱신.

### Security
- **force push는 계속 차단** — `git push --force`/`-f`/`--force-with-lease`(+ opencode는 인자 순서
  회피 `git push*--force*`)를 양쪽 가드의 deny에 명시. main 직접 push 금지는 패턴으로 구분이
  어려워 AGENTS.md 규칙으로 병행 강제(하니스의 "강제 불완전 → 규칙 병행" 원칙).

### Compatibility
- deny/차단 목록은 **호환성 계약** 항목이라 `HARNESS_VERSION` 1.12.0 → 1.13.0. push 금지 해제는
  안전 계약의 실질 변화라 minor. codex는 deny 목록 없이 `approval_policy`로 원격 경계를 다루므로
  변경 없음(push는 승인 프롬프트로 통과). verify_hooks(14항목)·protect_tests·guard.js는 불변.

## [1.12.0] - 2026-07-07

### Added
- **팀 절차 자기개선 루프**(large 전용) — lead가 단계 시작(7-0) 그루밍에서 재발 신호
  (BACKLOG 반복·같은 단계 NEW_FAIL/REGRESSION 반복·RETRY_LIMIT/MAX_CHECKER_CALLS 도달)를
  보면 IMPROVE 개선안을 낸다. 절차 변경은 C등급으로 Owner 승인 → `dev-agent-team/PROCESS.md`에
  append-only(P번호) 누적. 역할은 자기 대상(+전체) 개정을 따르고, 유효 파라미터(RETRY_LIMIT 등)는
  헌법 기본값보다 PROCESS.md를 우선. 정적 역할 md는 불변(오버레이 방식). lead 미emit인 small은 자동 제외.

### Changed
- **codex를 large 프로파일 전용으로 고정** — small(온프레미스)에서 codex가 요청되면
  (`--agent all` 포함) init이 프로파일 확정 직후 에러로 중단한다(`init.sh`/`init.ps1` 양쪽 가드).
  codex가 large 전용이 되어 `.codex/config.toml`에 `model_reasoning_effort = "high"`를 무조건
  포함(세션 추론 강화)하고, on-prem(small) 예시는 커스텀 provider로 일반화.
- **테스트 레이어 언어 일반화** — tester/coder/checker/reviewer의 `pytest`·`stage_{n}_test.py`
  하드코딩을 제품 언어의 테스트 관례·러너(pytest / go test / cargo test / npm test)로 일반화한다
  (가드 정규식 호환 파일명만 예시로). checker가 AGENTS.md "테스트 실행 언어 무관" 선언과 정합.
  `common/logger.py`는 Python 유지(제품 코드 언어중립화는 별도 과제).
- **테스트 설계 강화** — tester·test-design에 done_check(수용 기준) 각 항목 정상 케이스 커버리지
  강제, 테스트 간 독립성(실행 순서 무관), 준비-실행-검증(AAA) 본문 골격 규칙 추가.
- **SQL_ID 규칙 추가** — DB/DAO를 쓰는 제품에서 DB 로그↔코드 추적을 위해 code-convention
  (이름 체계 `모듈.엔티티.동작`·DAO/매퍼 자동 파생·유일성)과 logging-rule(SQL 주석 `/* sqlid=... */`
  주입·앱로그에 sqlid+trace_id 동시 기록·동적 trace_id는 캐시 파편화 탓에 세션 속성으로)에
  조건부 섹션을 추가. DB 없는 제품엔 무영향.

### Compatibility
- 새 상태 파일 `dev-agent-team/PROCESS.md`(P번호·append-only, large 전용)가 **호환성 계약**에
  추가되어 `HARNESS_VERSION` 1.11.1 → 1.12.0 (minor). codex 프로파일 게이팅·테스트 문구 일반화·
  SQL_ID 규칙은 새 파일/포맷/가드 변경이 없어 독립 상향이 불필요하며 1.12.0에 함께 실린다.
  가드 3경로(.sh 2개 + guard.js)와 verify_hooks(14항목), 로그 형식(key=value)은 불변.

## [1.11.1] - 2026-06-30

### Changed
- lib-research 스킬을 언어 일반화 — 파이썬 전용(`requirements.txt`/`pip install`)에서
  node(`package.json`)·go(`go.mod`)·rust(`Cargo.toml`) 매니페스트와 npm/pkg.go.dev/crates.io
  레지스트리까지 다루도록 변경. (직전 v1.10.0 다국어 테스트 일반화와 짝.)

### Fixed
- team-dev 절차에 "lib-research는 메인 세션이 직접 수행하는 절차이며 전용 서브에이전트
  (researcher 등)는 없다 — coder/tester/designer는 'lib-research 필요: {이름}'만 보고한다"를
  명시. 에이전트가 존재하지 않는 `researcher` 서브에이전트를 호출하던 오류 방지.

### Compatibility
- libs/{이름}.md 필드 구조·역할셋은 불변(계약 위반 아님). 절차·예시 명령 변경 정합을 위해
  `HARNESS_VERSION` 1.11.0 → 1.11.1 (patch).

## [1.11.0] - 2026-06-30

### Added
- **designer 역할**(UI 설계 담당) 추가 — 양 프로파일(small/large) 공통. UI/화면이 있는 단계에서만
  호출하며, 코드는 만들지 않고 `dev-agent-team/DESIGN.md`(설계 명세)만 산출한다(spec-only).
  명세대로의 구현은 coder가 한다(단일 작성자·TDD·단계게이트 유지).
- **ui-design 스킬** 추가(디자인 토큰·컴포넌트·상태·접근성 WCAG·반응형 모바일 퍼스트). emit_skills 5 → 6.
- 세 에이전트 모두에 designer 깔림 — Claude `.claude/agents/designer.md`(tools: Read, Write),
  Codex `.agents/skills/designer/SKILL.md`, opencode `.opencode/agents/designer.md`(write only).

### Changed
- team-dev 절차에 공통 **7c 단계** 추가: UI 단계면 designer 호출 → DESIGN.md → tester·coder가 참조.
- AGENTS.md "5개 역할" → "역할"(5 공통 + designer + large 전용 4), 파일 맵에 DESIGN.md, 스킬에 ui-design.
- planner: UI/화면 포함 단계를 PLAN.md에 "(designer 필요)"로 표시.

### Compatibility
- 역할 경계·스킬셋·파일 레이아웃(DESIGN.md)은 **호환성 계약** 항목이라 `HARNESS_VERSION` 1.10.0 → 1.11.0.
  가드 3경로(.sh 2개 + guard.js)와 verify_hooks(14항목)는 불변.

## [1.10.0] - 2026-06-29

### Added
- go/rust/node 테스트를 파이썬과 **동일하게** 취급. 세 에이전트(claude/codex/opencode) 모두
  `go test`·`cargo test`·`npm test` 를 Owner 프롬프트 없이 실행한다.
  - Claude: `settings.json` allow에 `go`/`cargo`/`npm`/`npx`/`node`/`pnpm`/`yarn` 추가.
  - codex(sandbox 자동)·opencode(wildcard allow)는 기존에 이미 허용.
- `verify_hooks.sh` 검증 항목 8 → 14 (go/rust/node 테스트 보호 차단·허용 + 비-테스트 회귀).

### Changed
- 기존 테스트 파일 보호(`protect_tests.sh`·`guard.js`)를 단일 정규식으로 동기화해
  언어 일반화: `tests/` 밑 `*_test.py`/`test_*.py`/`*_test.go`/`*_test.rs`/`test_*.rs`/
  `*.test.{js,jsx,ts,tsx,mjs,cjs}`/`*.spec.{...}` 기존 파일 수정 차단, 새 파일·`conftest.py` 등은 허용.

### Security
- inline 임의코드 실행 차단을 node로 확장: `node -e`/`node --eval` deny 추가
  (`python -c`와 동일 사유; Claude·opencode 양쪽 deny 목록).

### Fixed
- `init.sh`: opencode 미포함 설치(`--agent codex` 등)에서 마지막 안내 줄의 `&&` 단축평가가
  종료코드 1을 내던 선행 버그 수정(`if has_agent ...; then ... fi`). `init.ps1`은 `if` 문
  구조라 동일 버그 없음(코드리뷰 확인).

### Compatibility
- deny 목록과 테스트 보호는 **호환성 계약** 항목이라 `HARNESS_VERSION` 을 1.9.2 → 1.10.0 으로 올림.
  small↔large, Claude↔Codex↔opencode 무손실 전환 계약은 유지.

## [1.9.2]
- opencode deny에 `python -c` / `python3 -c` 추가.

## [1.9.1]
- `protect_tests` 훅이 codex `apply_patch` 페이로드도 인식.

## [1.9.0]
- large 전용 critic(결정 심의·합의) + security(보안 점검) 역할 추가, planner 요구사항 충돌·누락 점검, 시뮬레이션 갭 보강.

## [1.7.0]
- large 전용 lead(팀장) 역할 + 방향 프로세스(DIRECTION.md) 추가.

## [1.6.0]
- 협업 백로그(BACKLOG.md) 추가, NOTES 흡수.

## [1.5.0]
- large 전용 reviewer(코드·테스트 리뷰) 역할 추가.

## [1.4.0]
- documenter 역할 추가 + 각 역할 강화.

## [1.3.0]
- `team/` → `dev-agent-team/` 디렉터리 개명.

## [1.2.0]
- `team/` 분리 + 멀티 에이전트(claude/codex/opencode) 지원.

## [1.1.2]
- AI 에이전트 개발팀 하니스 초기 버전.
