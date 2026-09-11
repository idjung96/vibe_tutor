# Changelog

이 파일은 team-dev-harness(하니스 생성기)의 버전별 변경을 기록한다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전은 `HARNESS_VERSION`(호환성 계약)과 일치한다.

## [1.27.2] - 2026-09-11

Codex·Windows·기존 파일 보존 3축 리뷰에서 나온 결함 3건.

### Fixed
- **재설치가 대상 프로젝트의 실제 파일을 지우고 있었다.** `verify_hooks.sh` 가 `$TARGET` 에
  직접 쓰고 지웠고, `init.sh`/`init.ps1` 이 설치 끝에 이걸 자동 실행하므로 **재설치할 때마다**
  발생했다. 재현으로 확인한 피해:
  `tests/conftest.py`(pytest 프로젝트에 거의 항상 있다), `tests/calc_test.go`,
  `tests/calc.test.js`, `tests/calc_test.rs`, `tests/stage_9_test.py`(하니스 자신의 명명 규약과
  충돌), 그리고 **`dev-agent-team/OWNER_QUESTION.md`** — 미답변 질문이 사라져 C등급 정지
  상태가 통째로 유실됐다. append-only 테스트 보호를 내세우는 하니스가 자기 설치 과정에서
  테스트를 지우고 있었던 셈이다.
  이제 훅을 `mktemp -d` 샌드박스에 복사해 **거기서만** 돌린다. 대상 프로젝트는 한 번도
  건드리지 않는다. CRLF 검사(19번)만 설치된 실제 훅을 본다(`$REAL_H`).
- **`verify_hooks.sh` 20번이 Windows 설치를 중단시켰다.** 1.26.1에서 넣은 항목이 `ln -sf` 로
  가짜 PATH를 만드는데, Git Bash 에서 심볼릭 링크는 **복사**로 처리돼 `bash.exe` 가 DLL 을
  못 찾는다 → 항목 20 FAIL → `init.ps1` 이 `exit 1` 로 설치를 중단한다.
  심링크·PATH 재구성 없이 **실패하는 python 스텁을 PATH 앞에 놓는** 방식으로 바꿨다.
  검사 대상도 "python 부재"에서 "**추출 실패**"로 정확해졌다 — 실제로 막아야 할 상태다.
- **에이전트 구성을 바꿔 재설치하면 불필요한 `.bak` 이 생겼다.** `--agent all` →
  `--agent codex` → `--agent all` 순이면 manifest 에서 `CLAUDE.md` 항목이 빠져 다음 설치 때
  "기록 없음"으로 보였다. 이번에 렌더하지 않은 항목은 manifest 에 **이월**한다
  (`init.sh`/`init.ps1` 양쪽).

### Compatibility
- 설치기 동작만 바뀐다. 렌더 결과·파일 형식·역할 경계는 그대로다.
- Codex 경로는 이상이 없었다 — 단독 설치 시 역할 10 + 스킬 6 + 훅 + 상태 파일이 모두 깔리고
  `.claude`/`.opencode` 는 생기지 않으며, `.codex/hooks.json` 이 같은 훅을 `bash` 로 호출하고
  `AGENTS.md` 가 `PROJECT_RULES.md` 와 게이트를 지시한다.

## [1.27.1] - 2026-09-11

Windows를 실행하지 못하는 대신 하니스 쪽에서 검증하다가 나온 수정.

### Fixed
- **해시 도구가 없을 때의 경로를 명시적으로 만들었다.** `sha256_of` 는 `sha256sum`·`shasum` 이
  둘 다 없으면 빈 문자열을 낸다. 그 상태로 비교에 들어가면 `"" = ""` 가 참이 되어
  **파일이 조용히 갱신되지 않는 쪽으로 샐 수 있다.** 실측해 보니 빈 해시가 `manifest_get` 의
  필드 매칭까지 깨뜨려 결과적으로는 안전한 경로("백업 후 덮어쓰기")로 빠지고 있었지만,
  **우연에 기대는 구조**였다. 이제 해시가 비면 명시적으로 그 경로를 타고 안내를 낸다 —
  갱신은 살리고 편집은 `.bak` 으로 남긴다.

### Compatibility
- 동작이 바뀌는 환경은 해시 도구가 없는 시스템뿐이고, 그 경우에도 결과는 종전과 같다.
  `init.ps1` 은 `Get-FileHash` 가 항상 있어 해당 분기가 필요 없다.

## [1.27.0] - 2026-09-11

### Added
- **재설치가 `AGENTS.md`·`CLAUDE.md` 의 Owner 편집을 덮어쓰지 않는다 (dpkg conffile 방식).**
  설치 시 렌더 결과의 SHA-256을 `dev-agent-team/.harness-manifest` 에 기록하고, 재설치 때
  비교한다:

  | 상황 | 동작 |
  |---|---|
  | 해시 == 기록값 (안 건드림) | 조용히 갱신 — 업그레이드가 산다 |
  | 해시 != 기록값 (편집함) | 덮지 않고 `<파일>.new` + 알림 |
  | manifest 없음 (1.27.0 이전) | `<파일>.bak` 백업 후 갱신 + 안내 |

  **단순히 "덮어쓰지 않기"로 하지 않은 이유**: 이 둘은 헌법과 진입 문서라 안 덮으면 헌법
  갱신이 기존 프로젝트에 영원히 도달하지 않는다. 이번 세션만 해도 헌법에 규칙 8번이 늘고
  로그 규격·게이트가 들어갔다. "재실행이 곧 업그레이드다"가 깨진다.

### Changed
- **강제 장치는 예외 없이 덮어쓴다** — `.claude/settings.json`(deny 목록),
  `dev-agent-team/hooks/*.sh`, `guard.js`, `opencode.json`, `.codex/*`, 역할·스킬,
  `selfcheck.py`. 낡으면 안전 계약이 깨지므로 conffile 규칙을 쓰지 않는다. 이 구분을
  README에 명시했다.
- 편집 감지 알림에 "고유 규칙은 `PROJECT_RULES.md` 에 적으면 이 알림이 안 뜬다"를 넣어
  올바른 자리로 유도한다. `AGENTS.md` 를 계속 편집하면 헌법 갱신이 `.new` 로만 쌓여
  규칙이 낡은 채 고착되기 때문이다.

### Compatibility
- 파일 맵에 `dev-agent-team/.harness-manifest` 가 늘고 설치기 동작이 바뀌므로
  `HARNESS_VERSION` 을 1.27.0으로 올린다.
- `init.sh` 와 `init.ps1` 이 **같은 해시 문자열**을 내야 파리티가 성립한다 —
  `sha256sum`/`shasum -a 256` 과 `Get-FileHash -Algorithm SHA256` + `.ToLower()`.
  같은 파일에 대해 양쪽 결과가 바이트 단위로 일치함을 확인했다.
- manifest가 손상·삭제되면 "1.27.0 이전 프로젝트"로 취급되어 `.bak` 을 만들고 덮어쓴다.
  안전한 쪽이다.

## [1.26.1] - 2026-09-11

Windows 환경 리뷰에서 **가드가 무력화되는 경로 2개를 재현**해 고쳤다.

### Fixed
- **`.gitattributes` 신설 — CRLF로부터 가드 훅 보호.** Git for Windows 기본값
  (`core.autocrlf=true`)으로 이 저장소를 클론하면 `.sh` 가 CRLF가 되고, `init.ps1` 이 그대로
  대상 프로젝트에 복사해 **생성되는 모든 프로젝트로 전파**된다. 재현 결과 두 가드가 반대
  방향으로 깨진다 — `protect_tests.sh` 는 구문 오류(exit 2)로 **모든 Write/Edit/Bash를 막고**,
  `block_on_owner_question.sh` 는 exit 255로 크래시해 **C등급 정지가 강제되지 않는다**.
  CRLF 상태의 bash 스크립트를 정상 동작시킬 방법은 없으므로 예방(`.gitattributes`)과
  탐지(`verify_hooks` 19번)로 간다. `.ps1` 만 `eol=crlf`, 나머지는 `eol=lf`.
- **`protect_tests.sh` 를 fail-closed 로.** `python3 -c` 로 경로를 추출하는데 실패 시
  `[ -n "$FILES" ] || exit 0` 이라 **조용히 통과**했다. `python3` 만 없는 PATH에서 기존 테스트
  수정이 exit 0으로 허용되는 것을 재현했다. Windows에서 이건 예외가 아니라 기본값에 가깝다 —
  python.org 설치본은 `python.exe` 만 만들고 `python3.exe` 는 만들지 않는다.
  이제 `python3` → `python` 순으로 실행기를 찾고, **둘 다 없거나 추출기가 비정상 종료하면
  exit 2로 막는다.** "추출 성공 + 해당 없음"(정상 통과)과는 종료코드로 구분한다 — 섞으면
  CRLF `protect_tests` 처럼 모든 작업이 막힌다.
- 게이트 명령 두 곳(`team-dev` 12번, `coder` 자체 점검)에 `python3` 가 없으면 `python` 으로
  부르라는 단서를 병기했다. 1.25.2에서 `python3` 로 통일하면서 Windows 대안을
  `selfcheck.py` docstring에만 적어, **명령이 발행되는 자리에는 없었다.**

### Added
- `verify_hooks.sh` 18항목 → **20항목**.
  19번은 설치된 훅에 CR 바이트가 있는지(= CRLF 체크아웃 탐지), 20번은 `python3`·`python` 이
  없는 PATH에서 `protect_tests.sh` 가 **차단(2)** 하는지를 고정한다.

### Compatibility
- 가드 동작이 fail-open → fail-closed 로 바뀌므로 `HARNESS_VERSION` 을 1.26.1로 올린다.
- `guard.js` 는 Node 내장 로직이라 이 문제가 없다 — 세 경로 동기화 규약상 동작이 갈리는
  부분이 아님을 주석에 남겼다.
- 정상 환경(파이썬 있음)의 기존 18항목은 그대로다. 특히 `pytest tests/x_test.py > /tmp/o`
  (실행·리다이렉션)와 `cat tests/x_test.py`(조회)는 여전히 허용된다 — 여기서 막히면 checker가
  죽는다.

## [1.26.0] - 2026-09-10

### Added
- **`dev-agent-team/PROJECT_RULES.md` — Owner가 쓰는 프로젝트 고유 규칙 파일.**
  재설치 동작을 실측해 보니 작업 산출물(REQUIREMENTS·PLAN·DECISIONS·BACKLOG·TEST_LOG·
  제품 코드·git 이력)은 전부 보존되지만 `AGENTS.md`·`CLAUDE.md`·역할 프롬프트는 **무조건
  덮어써진다.** 그런데 Owner가 프로젝트 고유 규칙(사내 라이브러리 강제, DB 접근 경로, 도메인
  용어)을 적을 자리가 그 덮어써지는 파일뿐이었다. `PROCESS.md` 는 large 전용이고 절차 개정
  (P번호·append-only·Owner 승인) 전용이라 도메인 규칙을 넣을 곳이 아니다.
  `DECISIONS.md`·`BACKLOG.md` 와 같은 `[ -f ] ||` 패턴이라 **한 번만 만들어지고 이후 건드리지
  않는다.**
- 헌법 "항상 지킨다" **8번** 신설 — 이 파일이 있으면 따르되, **헌법을 좁히는 방향으로만**
  작동한다. 규칙을 더 엄하게 만들 수는 있어도 느슨하게 만들 수 없고, 안전장치(가드레일·
  C등급 정지·append-only 테스트·단일 작성자 원칙)는 무효화하지 못한다. 헌법과 충돌하면
  헌법이 이긴다. **`PROCESS.md` 와는 방향이 반대**라는 점을 함께 적었다 — 그쪽은 Owner 승인을
  거친 절차 개정이라 파라미터가 헌법보다 우선한다.

### Changed
- 세 에이전트에 세 겹으로 건다 — Claude는 `CLAUDE.md` 의 `@dev-agent-team/PROJECT_RULES.md`
  import, opencode는 `opencode.json` 의 `instructions` 배열, codex는 import 메커니즘이 없어
  `AGENTS.md` 지시에 의존한다.
- **서브에이전트에는 메인 세션이 전달한다** — `PROCESS.md` 가 이미 쓰는 방식을 그대로 따라
  team-dev 공통 머리말에 "역할을 호출할 때 그 역할 대상(또는 전체) 규칙을 함께 전달한다"를
  넣었다. 서브에이전트가 프로젝트 CLAUDE.md를 상속하는지에 의존하지 않는 경로다.

### Compatibility
- 파일 맵과 헌법 규칙이 늘어나므로 `HARNESS_VERSION` 을 1.26.0으로 올린다.
- **기존 프로젝트도 재설치하면 파일이 생긴다**(없을 때만 생성). 이미 있으면 그대로 둔다.
- 역할 본문 10종, 가드 훅, `verify_hooks.sh`(18항목), `selfcheck.py` 는 건드리지 않았다.
  `dev-agent-team/` 은 selfcheck의 `SKIP_DIRS` 라 새 파일이 스캔에 잡히지 않는다.

## [1.25.2] - 2026-09-07

전체 리뷰에서 나온 정합성 결함 3건.

### Fixed
- **`selfcheck.py` 호출이 `python` 과 `python3` 로 갈렸다.** `coder` 자체 점검은 `python`,
  team-dev 절차 12번은 `python3` 을 썼다. 1.25.0에서 게이트가 필수가 되면서 이게 문제가 된다 —
  `python` 이 없는 환경(Python 3만 설치된 macOS·Linux)에서 coder 쪽 지시만 실패한다.
  `python3` 으로 통일하고, Windows에 `python3` 가 없으면 `python` 으로 부르라는 단서를
  selfcheck 사용법에 한 줄 남겼다.
- **`selfcheck: allow-print` 예외가 `logging-rule` 스킬에 없었다.** 1.25.0에서 예외를
  만들면서 `AGENTS.md` 4번 규칙에만 적었는데, print 규칙을 찾는 coder가 실제로 읽는 곳은
  `logging-rule` 이다. "print를 쓰지 않는다" 옆에 예외와 그 한계(로그 대용 금지)를 적었다.
- **저장소 `CLAUDE.md` 의 절 제목이 본문과 어긋나 있었다** — 제목은 "프로파일은 단 7가지만
  다르다"인데 본문은 "차이 13종"을 13개 나열한다. v1.2.0(`dcc3cae`)부터 있던 오류로,
  `README.md` 는 이미 "이 13가지만 다르다"로 맞아 있었다. 제목을 13가지로 고쳤다.

### Compatibility
- 렌더 결과의 문구만 바뀐다. 파일 형식·역할 경계·절차 구조는 그대로다.

## [1.25.1] - 2026-09-07

### Fixed
- **`init.ps1` 의 TEST_LOG 마이그레이션이 줄 끝을 CRLF로 바꿨다.** `[System.IO.File]::WriteAllLines`
  는 Windows에서 `Environment.NewLine`(CRLF)을 쓰는데, 이 파일의 다른 렌더링(`Render-String`)과
  `init.sh` 의 awk 출력은 모두 **LF** 다. Owner의 TEST_LOG 전체 줄 끝이 뒤집혀 `init.sh` 와
  결과가 달라졌다. `WriteAllText($f, ($out -join "\`n") + "\`n", $Utf8NoBom)` 으로 바꿔
  파일 관행과 `init.sh` 에 맞췄다.

  pwsh가 없어 런타임 검증을 못 하므로, PowerShell 시맨틱(`-split '\|'` 인덱스,
  `.ToCharArray()` 파이프 계수, `-match`/`-replace`, `-join`)을 그대로 옮긴 시뮬레이터로
  `init.sh` 결과와 **바이트 단위 대조**했다 — 정상 표 / 빈 표 / 공백 없는 헤더 / 정렬
  콜론(`:---`) / 이미 7열 / 헤더 없음 6가지 입력에서 모두 동일.
- 같은 대조로 `Claude-Tools` 의 10개 역할 매핑이 `claude_tools` 와 전부 일치함을 확인했다
  (1.20.0에서 넣은 `planner` 의 `Grep` 포함).

### Compatibility
- 렌더 결과와 파일 형식 계약은 바뀌지 않는다. Windows 설치기에서만 동작이 달라진다.

## [1.25.0] - 2026-09-07

### Added
- **`selfcheck.py --gate` — 단계 merge 전 게이트.** 1.20~1.21에서 언어 무관 스캔과 R번호
  추적성·코드 규모 검사를 갖췄지만 절차상 위치는 `coder` 체크리스트의 "(선택) … 봐도 된다"
  한 줄이라 아무도 안 돌려도 단계가 통과했다. 특히 **R번호 추적성은 이것 말고 확인할 주체가
  없다** — planner는 covers만, tester는 자기 테스트 이름만, documenter는 README만 본다.
  이제 12번 `- PASS:` 맨 앞에서 반드시 돌고, FAIL이면 coder가 고치고 checker를 다시 부른다
  (`RETRY_LIMIT` 초과 시 C등급). **양 프로파일 공통**이다 — 판단이 0이라 large에서도 안전하고
  reviewer가 놓치는 구조적 문제를 잡는다.
- **`selfcheck: allow-print` 예외.** print를 차단으로 올리면 표준출력이 제품 기능인 CLI
  도구를 막아버린다. 사용자에게 보여주는 출력은 로그가 아니므로 그 줄에 이 주석이 있으면
  print 검사에서 뺀다. 주석이 필요하니 grep으로 전수 확인되고 large에서는 reviewer가 본다.

### Changed
- **차단은 결정적 3종만이다** — `collect`(문법·임포트 오류) / `print`(logging-rule 위반, 정확)
  / `trace`(R번호 구조, 진행도 인식). `security` 와 `size` 는 검사하고 출력하되 **exit code에
  반영하지 않는다** — security는 스스로 "후보 — 사람이 확인한다"라고 밝히고 있고(rust `unsafe`,
  JS `innerHTML`), 비-Python size는 근사라 거짓 차단이 난다. 그 지적은 BACKLOG "메모·주의"에
  `· 출처:stageN/selfcheck` 로 남긴다.
- **게이트에서는 방금 끝난 단계도 완료로 본다.** `scan_trace(include_current=True)`.
  게이트가 도는 12번 시점에는 `current_stage` 가 아직 안 올라가서, 그대로 두면 이번 단계의
  R에 테스트가 없어도 다음 단계까지 안 잡힌다.
- **기본 모드(플래그 없음)는 지금과 동일하다** — 5종 전부를 exit code에 반영한다. 회귀 없음.
- `coder` 자체 점검이 "(선택) … 봐도 된다" → "`--gate` 를 돌려 `[gate] PASS` 인지 확인했는가"로
  바뀐다. 고치는 지점을 앞으로 당겨 왕복을 줄인다.
- **`TEST_LOG` 의 `리뷰지적` 열은 건드리지 않는다.** 그 열은 reviewer·security **역할**의
  지적 수이고 selfcheck 지적은 BACKLOG "메모·주의"로만 간다. small에서 `-` 로 남는 규칙이
  유지된다.

### Compatibility
- 절차에 게이트가 생기고 역할 본문(coder)이 바뀌므로 `HARNESS_VERSION` 을 1.25.0으로 올린다.
  README·CLAUDE.md의 정지 메커니즘 계약에도 이 게이트를 넣었다.
- 게이트 재시도 루프는 checker를 다시 부르므로 `MAX_CHECKER_CALLS` 에 함께 잡힌다(기존
  reviewer 루프와 같은 회계). 한도에 닿으면 C등급으로 Owner에게 간다 — 무한 루프는 없다.
- `init.sh`/`init.ps1`, 가드 훅, `verify_hooks.sh`(18항목), 나머지 역할 본문은 건드리지 않았다.

## [1.24.0] - 2026-09-07

### Added
- **기존 프로젝트의 `TEST_LOG.md` 를 재설치 때 5열 → 7열로 자동 갱신한다.**
  1.22.0에서 `재시도`·`리뷰지적` 열이 생겼지만 init은 기존 상태 파일을 덮지 않으므로
  (`init.sh:145` / `init.ps1`) 옛 프로젝트는 재설치해도 5열로 남았다. 그 상태에서 메인 세션이
  새 절차대로 7열 행을 쓰면 헤더와 데이터의 열 수가 어긋나 표가 깨진다.
  1.22.0에서 "손으로 추가하거나 그대로 두면 된다"고 적었던 것을 **철회한다** — Owner가
  손댈 일이 아니다.

  변환은 마지막 칸(커밋) 앞에 두 칸을 끼우는 것이다. 헤더는 열 이름으로, 구분선은 `---` 로,
  데이터 행은 `-` 로 채우고 새 열 설명을 헤더 앞에 넣는다.

### Changed
- 설치기가 대상 폴더의 상태 파일을 고치는 것은 처음이라, 안전장치를 세 겹으로 뒀다:
  (a) 옛 5열 헤더가 정확히 있고 `재시도` 가 아직 없을 때만 실행(멱등),
  (b) `|` 로 시작하고 파이프가 **정확히 6개**인 줄만 변환 — 사람이 표 아래 적은 메모나
  이미 7열인 행은 손대지 않는다, (c) 원본을 `TEST_LOG.md.bak` 으로 백업.
  헤더를 손으로 고쳐 열 이름이 다르면 아무것도 하지 않는다(추측해서 고치는 것이 더 위험하다).
- **범용 마이그레이션 프레임워크는 만들지 않았다.** 필요한 변환이 하나뿐이라 일반화하면 쓰지
  않는 구조가 남는다. 모든 프로젝트가 7열로 올라간 뒤에는 이 함수를 지워도 되도록 주석을 남겼다.

### Compatibility
- 파일 형식 계약 자체는 1.22.0에서 이미 바뀌었고 이번엔 설치기 동작이 바뀐다.
  대상 폴더의 상태 파일을 고치는 첫 사례라 이력을 남기려 `HARNESS_VERSION` 을 1.24.0으로 올린다.
- `templates/**`, 가드 훅, `verify_hooks.sh`(18항목), `selfcheck.py`, 역할 본문은 건드리지
  않았다 — **렌더 결과는 1.23.0과 동일하다.**
- `init.ps1` 은 `init.sh` 와 동일 규칙으로 구현했고, 이 파일의 관행대로 BOM 없는 UTF-8
  (`$Utf8NoBom`)로 쓴다. pwsh가 없어 런타임 검증은 못 했고 코드리뷰로 대조했다.

## [1.23.0] - 2026-09-07

1.20.0에서 문서로만 명시하고 넘어간 "로깅 헬퍼는 Python 전용" 제약을 해소한다.

### Added
- **로그 한 줄 규격을 글로 명시했다** — `logging-rule` 스킬에
  `[HH:MM:SS] [LEVEL] [모듈] 동작 | key=value` 형식, `logs/app.log` append + 표준출력,
  LEVEL 3종을 적었다. 지금까지 이 형식은 **`common/logger.py` 의 Formatter 코드 안에만**
  있었다. `CLAUDE.md`·`README.md` 의 호환성 계약에 "로그 형식"이 항목으로 들어 있으면서도
  정작 형식 자체는 어디에도 적혀 있지 않아, 비-Python 프로젝트의 coder는 추측할 수밖에
  없었고 그러면 `checker` 의 `LOG:` 필드와 `DEBUG_GUIDE` 가 함께 무너진다.
- **`## 공통 로거 만들기 (1단계)`** 절 — go/rust/node의 **의존성 없는 최소 구현**을 실었다.
  설치 시점에는 제품 언어를 알 수 없어(0단계 인터뷰가 설치 후다) 파일로 깔 수 없으므로,
  1단계 "기반 만들기"에서 coder가 복사해 `common/logger.go|rs|js` 를 만든다.
  외부 로거(log/slog·tracing·pino)를 쓰려면 `lib-research` 를 거친 뒤 같은 규격을 내게 한다.

### Changed
- **절차에서 Python 전제를 걷어냈다** — `planner` 의 1단계 정의가
  "common/logger.py 동작 확인" → "제품 언어의 공통 로거(common/logger.*) 생성·동작 확인",
  `coder` 자체 점검이 "common/logger.py 의 logger만 썼는가" → "print 계열(print /
  fmt.Print / println! / console.log) 없이 공통 로거만 썼는가".
- `AGENTS.md` 4번 규칙과 파일 맵(`logs/app.log`)에 언어 무관 형식을 명시했다.
- **`README.md` 의 로그 형식 계약이 실제와 달랐다** — `[LEVEL] [모듈] 메시지 | key=value` 로
  적혀 있어 **시각이 빠져 있었다**. 실제 구현대로 고쳤다.
- `DEBUG_GUIDE.md` 에 로그 한 줄의 각 칸이 무엇인지 보여주는 예시를 넣었다(Owner용).
- "알려진 제약"의 로깅 항목을 해소된 내용으로 교체했다 — 형식은 언어 무관이고, 설치되는
  구현만 Python이며, 다른 언어는 1단계에서 만든다는 사실로. (테스트 수집 확인이 Python
  전용이라는 부분은 유지.)

### Compatibility
- 로그 형식이 호환성 계약이고 역할 본문(planner 1단계·coder 자체 점검)이 바뀌므로
  `HARNESS_VERSION`을 1.23.0으로 올린다.
- **`common/logger.py` 는 바꾸지 않았다.** 지금 형식이 곧 계약이라 고치면 기존 Python
  프로젝트의 로그가 달라진다. 계속 무조건 설치되며, 역할이 "Python 구현이자 참조 규격"으로
  재정의됐을 뿐이다.
- Python의 `logging` 은 `WARNING` 으로 찍는데 `checker` 가 접두사로 찾으므로 그대로 두고,
  다른 언어는 `WARN` 으로 적도록 규격에 못박았다.
- `init.sh`/`init.ps1`, 가드 훅, `verify_hooks.sh`(18항목), `selfcheck.py`, `TEST_LOG` 형식은
  건드리지 않았다.

## [1.22.0] - 2026-09-07

### Added
- **단계 지표를 `TEST_LOG.md`에 누적한다** — 표에 `재시도`·`리뷰지적` 두 열을 더했다.
  1.18.0에서 만든 단계 회고(12c)는 그 단계의 수치를 lead에게 **인라인으로** 넘기고 버려서,
  최종 회고(17b)가 "3단계부터 재시도가 급증했다" 같은 **추세**를 볼 수 없었다. 업계 하니스가
  관측하는 code churn rate·task resolution rate에 해당하는 자리가 비어 있던 셈이다.
  새 파일도 새 절차 단계도 만들지 않고, 12번의 기존 TEST_LOG 갱신에 두 값을 얹었다.
- `lead` 회고 신호 5개 → **6개**. "TEST_LOG의 재시도 또는 리뷰지적이 단계가 갈수록 늘어난다"를
  추가했다. 17b 최종 회고의 입력에도 이 두 열의 추세를 명시했다.

### Changed
- `TEST_LOG.md` 템플릿에 형식 설명을 붙였다(`DECISIONS.md`·`BACKLOG.md` 관행과 맞춤).
  지금까지 표 머리만 있고 각 열이 무엇인지 적혀 있지 않았다.
- 12c의 인라인 증거 블록은 **그대로 둔다.** CRITIC REVISE 횟수·신규 BACKLOG 건수는 TEST_LOG에
  남기지 않는 값이라 인라인 전달이 계속 필요하다. TEST_LOG는 추세용 2개만 영속화한다.

### Compatibility
- `TEST_LOG.md` 형식은 small↔large 무손실 핸드오프 계약의 일부라 `HARNESS_VERSION`을
  1.22.0으로 올린다. **열 구성은 양 프로파일 동일하다**(7열 고정) — 프로파일마다 열 수가
  다르면 핸드오프가 깨지기 때문이다.
- **small에서 리뷰 관련 처리는 하지 않는다.** small에는 reviewer·security가 없으므로 small로
  렌더된 절차는 리뷰 지적을 모으라고 지시하지 않고, 리뷰지적 칸을 `-`로 두라고만 한다.
  리뷰 지적 수집 지시는 `{{#IF_LARGE}}` 안에만 있다.
- **기존 프로젝트의 TEST_LOG는 5열이다.** `init.sh`는 기존 상태 파일을 덮지 않으므로 재설치해도
  옛 표가 유지된다. 헤더 2열을 손으로 추가하거나 그대로 5열로 둬도 된다 — 표시가 어긋날 뿐
  기능에는 영향이 없다.
- `init.sh`/`init.ps1`, 나머지 역할 본문, 가드 훅, `verify_hooks.sh`(18항목), `selfcheck.py`는
  건드리지 않았다.

## [1.21.0] - 2026-09-07

외부 하네스(GitHub Spec Kit, BMAD) 조사와 다중 에이전트 실패 원인 분석에서 나온 반영이다.
실세션 20,574건 분석 기준 실패 원인 1위는 **명세 실패 42%** — "어떤 에이전트도 상위 산출물을
외부 진실 소스와 대조하지 않아 오류가 여러 핸드오프를 살아서 통과한다".

### Added
- **R번호 추적성 검사(`scan_trace`)** — Spec Kit의 `/speckit.analyze`·`/speckit.converge`에
  해당한다. `REQUIREMENTS.md` → `PLAN.json` covers → 테스트 이름 → `README.md` 사슬을 대조한다.
  지금까지 각 역할은 **자기 산출물 안에서만** R번호를 확인해서(planner=covers, tester=테스트
  이름, documenter=README) 끊어진 고리는 아무도 보지 못했다.
  **진행 상황을 안다** — `current_stage` 기준으로 이미 끝났어야 하는 것만 실패로 본다:
  (a) 어느 covers에도 없는 R, (b) REQUIREMENTS에 없는 유령 R, (c) 완료된 단계인데 테스트 0건,
  (d) 전 단계 종료 후 README에 없는 R. 진행 중·미래 단계는 정보로만 표시하고,
  `REQUIREMENTS.md`/`PLAN.json`이 없으면 `SKIP`(프로젝트 초기).
- **코드 규모 임계 검사(`scan_size`)** — `code-convention`의 함수 40줄·인자 5개·중첩 3단계를
  기계적으로 확인한다. 지금까지 이 기준은 `reviewer`의 주관 판정이었고 reviewer는 large
  전용이라, **small에는 확인 주체가 아예 없었다.** python은 표준 `ast`로 정확히, go/rust/node는
  들여쓰기 기반으로 근사한다(gofmt·rustfmt·prettier가 들여쓰기를 강제해 중괄호를 파싱하지
  않아도 안정적이다). 출력에 근사임을 밝힌다.

### Changed
- **pytest exit 5(no tests collected)를 수집 오류로 보지 않는다** — 아직 테스트를 만들지 않은
  초기 상태에서 `[collect] FAIL`이 뜨던 거짓 실패를 없앴다.
- selfcheck 자신이 `scan_size` 기준을 어기고 있어 리팩터했다(`scan_trace`·`_brace_sizes` 등).
  기준을 강제하는 도구가 그 기준을 어기면 안 된다.
- **`_py_depth`가 `elif`를 새 중첩 단계로 세던 버그를 고쳤다** — AST에서 `elif`는 `orelse` 안의
  `If`라, `if/elif/elif`가 3단계로 계산됐다. 보기에는 같은 단계이므로 깊이를 늘리지 않는다.
- **에이전트 오버레이 폴더를 제품 코드로 스캔하던 문제를 고쳤다** — 갓 설치한 트리에서
  `.opencode/plugins/guard.js` 때문에 제품 언어가 `node`로 오판되고 guard.js가 스캔됐다.
  `SKIP_DIRS`에 `.claude`·`.opencode`·`.codex`·`.agents` 추가.
- **JS 위험 호출 패턴에서 `\.exec\(` 를 뺐다** — `RegExp.prototype.exec` 와 구분되지 않아
  `re.exec(s)` 같은 정상 코드를 셸 실행으로 오탐했다. `execSync`/`execFileSync`/`spawnSync`,
  `child_process.exec*`, `require("child_process")` 로 좁혔다.
- R번호 인식 정규식을 실제 명명 규약에 맞췄다 — `\bR\d+\b`는 `test_r1_x`의 `_r1`을 못 잡는다
  (`_`가 단어 문자라 경계가 없다). 구분자 뒤(`test_r1`, `fn r1_`, `"r1 "`)와 Go 캐멀케이스
  (`TestR1_Save`)를 받되 `user1`·`Router1` 같은 우연한 일치는 배제한다.

### Compatibility
- selfcheck의 검사 범위가 헌법·README 계약 문구에 있어 `HARNESS_VERSION`을 1.21.0으로 올린다.
- **절차는 바뀌지 않았다.** selfcheck는 지금처럼 coder 체크리스트의 "(선택)"으로 남는다.
  `init.sh`/`init.ps1`, 역할 본문, team-dev 절차, 가드 훅, `verify_hooks.sh`(18항목)는
  건드리지 않았다.
- 양 프로파일이 같은 파일을 받는다 — 두 검사 모두 판단이 0이라 small에서도 안전하다.

## [1.20.0] - 2026-09-07

### Added
- **`selfcheck.py`가 제품 언어를 감지한다** — 루트 마커 파일 우선(`requirements.txt`/
  `pyproject.toml`/`setup.py`/`Pipfile`, `go.mod`, `Cargo.toml`, `package.json`), 없으면
  소스 확장자 존재를 약한 근거로 쓴다. 감지된 언어가 없으면 세 검사를 모두 건너뛰고
  **0으로 종료**한다.
- **print·보안 스캔이 python/go/rust/node를 모두 다룬다.**
  print 계열: `print(` / `fmt.Print*`·`println(` / `println!`·`print!`·`eprintln!`·`dbg!` /
  `console.log|debug|info|warn|error|trace`.
  위험 호출: (python 기존) + go `exec.Command("sh"…)`·`unsafe.Pointer` /
  rust `unsafe {`·`Command::new("sh"…)` / node `eval(`·`new Function(`·`execSync(`·
  `innerHTML =`·`dangerouslySetInnerHTML`. 주석 스킵도 언어별(`#`, `//`, `/*`, `*`)로 맞췄다.
- `planner`에 **Grep** 부여(`Read, Write` → `Read, Write, Grep`, 양 프로파일).

### Changed
- **`selfcheck.py`는 Python 전용이었다.** 세 검사가 모두 `rglob("*.py")`와 pytest에
  묶여 있어, 비-Python 프로젝트에서 **거짓 실패 1개**(`[collect] FAIL` — pytest 미설치이거나
  수집 0건이면 항상)와 **거짓 통과 2개**(print·보안 스캔이 파일을 아예 안 읽음)를 냈다.
  하니스의 나머지(`checker`의 언어별 러너, `tester`의 파일명 규약, `protect_tests` TEST_RE)는
  언어 무관인데 selfcheck만 어긋나 있었다.
- **테스트 수집 확인은 Python 전용으로 남긴다** — 다른 언어는 `[collect] SKIP`으로 건너뛰고
  실패로 치지 않는다. `go build`/`cargo check`는 느리고 네트워크·빌드 산출물을 만들어
  selfcheck의 "읽기 전용·결정적" 성격을 깨기 때문이다. 테스트 실행은 어차피 `checker`가
  제품 언어 러너로 매 단계 전체 수행한다.
- `SKIP_DIRS`에 `node_modules`·`target`·`vendor`·`dist`·`build`·`.next`·`coverage` 추가.
  .js/.ts 스캔을 시작하면 `node_modules`가 폭발하므로 필수다.
- 보안 스캔 출력에 "후보 — 사람이 확인한다"를 명시. rust `unsafe`, JS `innerHTML =`는
  정당한 사용도 많아 거짓 양성이 나올 수 있다.
- **planner의 Grep 부재는 기존 결함이었다** — large planner에는 1.19.0 이전부터
  "파일 개수는 grep으로 실제 사용처를 세어 적는다"는 지시가 있는데 도구가 없었고,
  1.19.0의 "AS-IS 칸은 코드에서 확인한다"도 탐색 수단이 없었다. 도구 매핑은 프로파일
  공통이라(프로파일 차이는 `profiles/*.conf`와 `{{#IF_*}}` 두 경로로만 만든다) 양쪽에 적용했다.
- 문서를 사실과 맞췄다 — `AGENTS.md`의 logger·selfcheck 항목에 언어 범위 명시,
  `logging-rule` 스킬에 예시가 Python이며 타 언어는 표준 로거(log/slog·tracing·pino)를
  같은 규칙으로 쓴다는 안내, `README.md` 설계 원칙 문구 조정,
  **"알려진 제약"에 `common/logger.py`·`logging-rule`이 Python 전용이라는 항목 추가**.

### Compatibility
- 역할 경계(planner 도구)가 바뀌고 selfcheck의 검사 범위가 헌법·README 계약 문구에
  적혀 있으므로 `HARNESS_VERSION`을 1.20.0으로 올린다.
- **large의 절차·역할 본문·게이트는 바뀌지 않는다.** large에 닿는 변경은 공용 도구
  `selfcheck.py`의 버그 수정과 planner frontmatter 한 줄, 문서 문구뿐이다.
- `common/logger.py`, 가드 훅, `verify_hooks.sh`(18항목)는 건드리지 않았다.
- selfcheck를 small의 필수 게이트로 올리는 건은 보류했다. 지금처럼 coder 체크리스트의
  "(선택)"으로 남는다.

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
