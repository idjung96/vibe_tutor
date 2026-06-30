# Changelog

이 파일은 team-dev-harness(하니스 생성기)의 버전별 변경을 기록한다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전은 `HARNESS_VERSION`(호환성 계약)과 일치한다.

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
