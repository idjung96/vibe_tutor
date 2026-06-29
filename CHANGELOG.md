# Changelog

이 파일은 team-dev-harness(하니스 생성기)의 버전별 변경을 기록한다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전은 `HARNESS_VERSION`(호환성 계약)과 일치한다.

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
