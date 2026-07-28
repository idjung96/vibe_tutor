# Changelog

이 파일은 team-dev-harness(하니스 생성기)의 버전별 변경을 기록한다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전은 `HARNESS_VERSION`(호환성 계약)과 일치한다.

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
