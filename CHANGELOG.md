# Changelog

이 파일은 team-dev-harness(하니스 생성기)의 버전별 변경을 기록한다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전은 `HARNESS_VERSION`(호환성 계약)과 일치한다.

## [1.38.1] — 상태 파일이 망가졌을 때 점수가 만점을 내던 것

전체 리뷰에서 비정상 입력을 넣어 보다 찾았다. 에이전트가 잘못 쓴 상태 파일은 현실적인 상황이다.

| 상황 | 지금(AS-IS) | 앞으로(TO-BE) |
|---|---|---|
| `PLAN.json` 이 깨진 JSON | `[trace] FAIL` 을 찍고도 `[score] trace=100 doc=100` — **검사가 죽었는데 만점** | `[score] ESCALATE — PLAN.json 을 읽을 수 없어 trace·doc 을 잴 수 없다. 점수를 믿지 마라.` |
| `stages` 가 리스트가 아님 | `AttributeError: 'str' object has no attribute 'get'` **크래시** | `[trace] FAIL (stages 는 객체의 리스트여야 한다)` + exit 0 |
| `stages` 원소가 dict 가 아님 | 같은 크래시 | 같은 판정, `--gate` 는 trace 로 차단 |
| 프로젝트 초기(PLAN 없음) | SKIP | 그대로 SKIP(변화 없음) |

원인은 `scan_trace` 가 조기 반환하면서 `COUNTS["trace"]` 를 남기지 않은 것이다. `_axis` 는
"못 잰 값(None)"을 만점으로 처리하는데(잴 수 없는 것으로 깎지 않는다는 원칙), **"아직 잴 게
없다"와 "재려다 실패했다"를 구분하지 않았다.** 앞은 만점이 맞고 뒤는 아니다.
`검사가 죽었는데 깨끗하다고 보고하는 것`은 이 저장소가 fail-closed 로 다뤄 온 실패 유형이다.

타입 검증은 `_read_plan` 한 곳에 두어 `_stage_of`·`_covers_rs` 양쪽이 함께 산다.

## [1.38.0] — 재시도 판정이 과하게 Owner 를 부르던 것

"팀이 스스로 검토하고 낮은 등급은 스스로 해결하며 계속 개발하는가"를 리뷰하다 찾았다.
자율 장치(A·B등급 자율 결정, selfcheck, reviewer·evaluator·security·critic·lead)는 갖춰져
있었지만, **점수 판정이 두 군데서 과하게 Owner 를 불렀다.**

### 1. size 가 근사치인데 재시도를 강제했다

`--gate` 는 size 를 "근사라서" 일부러 안 막는다. 그런데 `--score` 는 같은 size 를 전체
가중치로 채점해 기준 미달이면 재시도를 걸었다. 남의 코드를 인수한 프로젝트라면 이번 단계와
무관한 옛 함수 때문에 **매 단계 재시도가 돌고 결국 Owner 에게 올라간다.**

| | 지금(AS-IS) | 앞으로(TO-BE) |
|---|---|---|
| `--gate` 의 size | 안 막음(근사) | 그대로 |
| `--score` 의 size | 기준 미달 → RETRY 강제 | **권고 축** — 점수에 `*` 표시, 재시도 강제 안 함 |
| 레거시 함수 3개 | `최저축=85 … RETRY` | `size=85*` … `PASS` |

합계(total)에는 그대로 들어가므로 고치면 진전으로는 잡힌다. 최저축도 판정 축에서만 고른다 —
"최저축 85인데 PASS" 로 읽히면 무엇이 재시도를 부르는지 흐려진다.

### 2. escalate 가 새 결함의 첫 발견에도 걸렸다

조기 탈출은 "다시 시켰는데 안 오른다"는 뜻인데, 직전 점수와의 차이만 봐서 **정상이던
프로젝트에 결함이 처음 나타난 순간에도** 곧바로 C등급으로 올렸다. 고쳐 볼 기회가 없었다.

이제 직전이 이미 `retry`·`escalate` 였을 때만 escalate 한다. 실측 흐름:

```
정상 → PASS / 결함 첫 발견 → RETRY / 안 고침 → ESCALATE / 또 안 고침 → ESCALATE / 고침 → PASS
```

`retry` 만 보면 RETRY→ESCALATE→RETRY 로 진동해서 `escalate` 도 실패 시퀀스에 포함시켰다.

## [1.37.0] — 전체 리뷰에서 나온 3건

### 1. --gate 가 재시도 루프 뒤에 다시 돌지 않던 것

PR 시점 순서가 `checker FULL → --record-full-test → --gate(PASS) → documenter → --score →
RETRY(coder 수정) → checker SCOPED → merge` 였다. **게이트가 통과한 뒤에** documenter 와
재시도 루프가 소스를 바꿀 수 있는데 게이트를 다시 돌지 않았다. 실측으로 재현했다 —
게이트 PASS 직후 소스를 고치면 `[full-test] FAIL` 이 되지만 절차는 그 검사를 건너뛰었다.
`--gate` 가 "최종 코드 기준"이라고 적혀 있는데 더 이상 최종 코드가 아니었다.

merge 직전에 게이트를 한 번 더 돌린다. 통과해야 push·merge 로 간다.

(조용히 나쁜 merge 가 나가지는 않았다 — `--score` 의 test 축이 신선도를 보므로 75로 떨어져
RETRY→ESCALATE 로 갔다. 실제 피해는 잘못된 merge 가 아니라 **엉뚱한 진단으로 재시도를
낭비하고 Owner 에게 올라가는 것**이었다. 그게 2번이다.)

### 2. RETRY 처방이 test 축에 대해 틀렸던 것

"코드 축(test·rule·trace·size)은 coder에게" 라고 뭉쳐 두었다. 그런데 test 축이 낮은 이유는
대부분 **전체 실행 기록이 낡은 것**이고, 처방은 코드 수정이 아니라 checker FULL +
`--record-full-test` 다. 축마다 처방을 나눠 적었다 — test 는 coder 를 부르지 않는다.

### 3. guard.js 가 실동작 검증을 전혀 안 받던 것

`verify_hooks.sh` 21항목이 **전부 `.sh` 대상**이고 guard.js 언급이 0회였다. "세 경로 동기화"는
계약인데 JS 경로는 육안 대조뿐이었고, opencode 사용자에게는 guard.js 가 유일한 가드다.

22~24번을 추가했다. 같은 입력을 `.sh` 와 guard.js 양쪽에 넣어 판정이 갈리는지 대조하고
(4케이스), 미답변 Owner 질문 차단과 "답: 번호" 해제도 본다. node 가 없거나 opencode 를
설치하지 않았으면 SKIP 한다. **결함 주입으로 실제로 잡는지 확인했다** — guard.js 정규식에서
python 보호를 빼면 `불일치: tests/stage_1_test.py 기대=2 sh=2 js=0` 으로 FAIL,
질문 차단을 무력화하면 그 항목이 FAIL.

verify_hooks 는 이제 **24항목**이다(21은 .sh, 3은 guard.js).

## [1.36.0] — 헌법 동결을 보이게

v1.35.0 리뷰에서 확인만 하고 남겨 둔 건이다. Owner 가 `AGENTS.md` 를 고치면 conffile 이
편집을 지키려고 `.new` 를 남기는데, 그 대가로 **그 파일만 옛 버전에 묶인다.** 절차·역할·권한은
새 버전으로 갱신되므로 규칙이 서로 어긋난 채로 돈다.

| | 지금(AS-IS) | 앞으로(TO-BE) |
|---|---|---|
| 설치 알림 | "새 버전은 .new 입니다" 한 줄 | **v1.35.0 → v1.36.0** 처럼 두 버전을 숫자로, 해소 절차 2택 |
| 개발 중 | 아무 신호 없음 | `selfcheck` 가 `[constitution]` 줄로 매번 보고 |
| Owner 에게 묻기 | 없음 | team-dev **"시작할 때"** 절이 인터뷰·계획보다 먼저 3지선다로 묻는다 |
| 탐지 여부 | verify_hooks 21/21 PASS, --gate exit 0 — 아무것도 안 잡음 | 위 세 곳에서 보인다 |

**차단하지는 않는다.** 코드 결함이 아니라 설치 상태 문제고, 고칠 사람은 Owner 다. merge 를
막으면 Owner 가 자리를 비운 동안 팀 전체가 멈춘다(Go 프로젝트로 동결 상태에서 `--gate` exit 0
확인). 강제는 절차의 Owner 질문이 한다 — 이 저장소가 원래 쓰던 방식이다.

해소 경로도 실제로 돌려 확인했다: 직접 쓴 규칙을 `PROJECT_RULES.md` 로 옮기고
`mv AGENTS.md.new AGENTS.md` 한 뒤 **설치를 한 번 더** 실행하면 manifest 가 맞춰져
`[constitution] OK` 가 되고, 이후 업그레이드에서 오탐이 나지 않는다. 설치를 다시 돌리지
않으면 manifest 가 옛 해시로 남아 다음 업그레이드에서 다시 `.new` 가 뜬다 — 그래서 안내
문구에 "한 번 더 실행"을 명시했다.

## [1.35.0] — 리뷰에서 나온 3건 정정

개발 팀이 실제로 도는지, 업데이트가 기존 파일을 건드리는지 리뷰하다 찾은 것들이다.
업데이트 쪽은 정상이었다 — v1.27.2 → v1.34.1 업그레이드에서 상태 파일 13종(BACKLOG 포함)이
바이트 단위로 보존되고 삭제 0건, TEST_LOG 5→7열 마이그레이션도 정상이었다.

### 1. doc 축이 매 단계 실패하던 것 — documenter 를 단계마다

1.34.0 의 doc 축은 **완료 단계의 R번호가 README 에 있는지**를 매 단계 보는데, documenter 는
17번(종료)에만 돌았다. 그래서 1단계 PR 시점부터 `doc=80` 으로 반드시 RETRY 였다.

| | 지금(AS-IS) | 앞으로(TO-BE) |
|---|---|---|
| documenter | 17번(종료)에만 | **PR 시점마다** 그 단계 R번호만 + 17번 최종 정리 |
| 1단계 doc 축 | 80 (RETRY 확정) | 100 (PASS) |
| 문서 상태 | 개발이 다 끝날 때까지 없음 | 단계마다 따라옴 |

순서는 `--gate` 뒤, `--score` 앞이다. README 는 `.md` 라 `.last-full-test` 를 무효화하지
않으므로 test 축이 떨어지지 않는다(확인함). documenter 가 소스를 건드리면 신선도가 깨져
test 축이 떨어지는데, 그건 올바른 동작이라 절차에 그렇게 적었다.

### 2. 헌법의 공유 상태 파일 목록이 낡아 있던 것

규칙 6이 5종만 열거하고 있었다. 빠진 것: **SCORE.json**(1.34.0에서 추가하고 등재 안 함),
DIRECTION.md·PROCESS.md(large). 단일 작성자 원칙은 small↔large 무손실 인수인계의 근거라
목록이 곧 계약이다. 이제 전부 열거하고 large 전용은 블록으로 나눴다.

### 3. trace 와 doc 이 같은 데이터에서 다른 창을 쓰던 것

`--score` 에서 trace 는 현재 단계를 **제외**(`include_current=gate` → False)하고 doc 은
**포함**(`sid <= current`)했다. 둘 다 "방금 끝난 단계" 시점에 도는데 기준이 달랐다.
trace 도 `gate or score` 로 맞췄다.

### 리뷰에서 확인만 하고 고치지 않은 것

Owner 가 `AGENTS.md` 를 고치면 conffile 이 `.new` 로 두므로 **헌법이 그 버전에 동결된다.**
편집은 보존되지만 절차만 새 버전이 되어 어긋난다(실측: push 규칙 상충, evaluator 헌법 0회
vs 절차 5회). 이 드리프트를 탐지하는 장치가 없고(verify_hooks 21/21 PASS, --gate exit 0),
알림도 몇 버전 뒤처졌는지 말하지 않는다. 별건으로 다룬다.

## [1.34.1] — 역할 목록에서 evaluator 누락 정정

1.34.0 에서 evaluator 역할을 추가하면서 **역할을 나열하는 문서 7군데를 갱신하지 않았다.**
init 의 매핑은 전부 맞았고(파리티 검증 10/10 PASS) 실제 emit 도 정상이라 동작은 문제가
없었지만, 문서만 읽으면 large 전용 역할이 4종으로 보였다.

- `templates/skills/team-dev/SKILL.md.tmpl` 머리말 역할 소개에 evaluator 추가(렌더 대상)
- `CLAUDE.md`: 역할 본문 단일 소스 "10개" → "11개", emit 대상 목록, 호환성 계약의 역할 경계,
  단일 작성자 원칙의 subagent 목록
- `README.md`: 역할 경계 2곳
- `CLAUDE.md` 차이 목록에 evaluator 가 **두 번** 들어가 있던 것 정정(14종 선언과 어긋났다)
- `CLAUDE.md` 검사 시점 항목 끝에 치환 흔적으로 남은 "와" 제거

## [1.34.0] — 산출물 평가와 재시도 판단

지금까지 재시도는 checker 의 PASS/FAIL 이진값과 RETRY_LIMIT 만 보고 정했다. 그래서
**명백히 막혔어도 제한 횟수를 끝까지 태웠다.** 나아지고 있는지를 잴 방법이 없었기 때문이다.
carve-harness 의 verify-loop(축별 0~100, 기준 95, 미달이면 격차를 주고 재생성)를 이 저장소의
설계 원칙(*주관 판정은 large 전용, 객관 검증은 양 프로파일 공용*)에 맞춰 두 층으로 들여왔다.

| | 지금(AS-IS) | 앞으로(TO-BE) |
|---|---|---|
| 재시도 판단 | checker PASS/FAIL + RETRY_LIMIT | 축별 점수와 **직전 대비 변화** |
| 막혔을 때 | 제한 횟수를 다 쓸 때까지 반복 | 합계가 안 오르면 즉시 C등급(Owner) |
| 문서 평가 | 없음(개발이 다 끝난 뒤 README 유무만) | `doc` 축 — 끝난 단계의 R번호가 README 에 있는가 |
| "테스트 안 돌리고 done" | `--gate` 의 full-test 가 merge 때 막음 | 그대로 + `test` 축 **상한 75** 로 점수에서도 불가능 |

- **층 A(양 프로파일, LLM 없음)**: `selfcheck.py --score` → `dev-agent-team/SCORE.json`.
  test·rule·trace·doc·size 각 0~100. 전부 기존 스캔이 이미 재던 값에서 나온다 — 새 분석이 아니다.
- **층 B(large 전용)**: `evaluator` 역할 신설. 요구사항 충족도(match·contract·doc)와 GAP 만 본다.
  품질은 reviewer, 결정은 critic — 보는 것이 겹치지 않게 역할 본문에서 선을 그었다.
- **점수는 아무것도 막지 않는다.** 막는 것은 `--gate` 의 결정적 4종 그대로다. 점수가 정하는
  것은 재시도 여부뿐이다(pass / retry / escalate).
- **진전은 최저축이 아니라 축 합계로 본다.** 구현 중 발견한 것이다 — 최저축으로 재면
  최저가 아닌 축을 고쳤을 때 변화가 0으로 보여 **개선 중인데도 escalate** 했다.
- 추세는 `SCORE.json` 의 `history` 에 누적한다. TEST_LOG 에 열을 더하면 옛 프로젝트
  마이그레이션(awk·PowerShell 양쪽)을 또 불러야 해서, 같은 것을 마이그레이션 없이 얻는 쪽을 골랐다.

golden-set / pass@k 는 들이지 않았다 — 같은 케이스를 k회 반복 실행하는 게 전제인데
우리 절차는 단계당 1패스라 비용이 맞지 않는다.

기존 역할 10종·가드 훅 2종·`guard.js`·권한 파일·TEST_LOG 는 불변.

## [1.33.0] — 검사를 생애주기 시점으로 나눔 + push·PR 승인

검사가 한 곳에 몰려 있었다. 12번 하나에 `--gate` 2회, checker FULL 2회, reviewer, security 가
전부 들어 있고, **테스트 커밋(9번) 전에는 아무 검사도 돌지 않았다** — 수집조차 안 되는 테스트로
구현을 시작하고, 구현이 다 끝난 뒤에야 `collect` 로 발견했다.

| 검사 | 지금(AS-IS) | 앞으로(TO-BE) |
|---|---|---|
| `selfcheck` collect | merge 직전에만 | **테스트 커밋 전(9번)** + PR 시 |
| `--gate` 조기 필터·checker SCOPED | 12번 뭉텅이 안 | **commit 전**으로 명시 |
| checker FULL·`--gate` 4종·reviewer·security | 12번 뭉텅이 안 | **PR 시**(main 합치기 직전, 단계당 1회) |
| push·PR | 절차에 아예 없음 | **신설** — remote 있을 때만. 없으면 지금처럼 로컬 merge |

싼 검사를 앞으로 **당긴 것**이지 뒤를 덜어낸 게 아니다. PR 시점 게이트는 collect·print·trace·
full-test 4종을 그대로 막는다. main 합류 지점은 하나이고 PR/로컬 merge 양쪽의 게이트 내용이
같아서, 오프라인·온프레미스(small)에서 절차가 그대로 돈다.

- team-dev 스킬에 **"언제 무엇을 하나" 시점별 표**를 정본으로 신설. AGENTS.md 규칙 9를 시점 기준으로 재작성.
- **`git push` 전체와 `gh pr` 을 `ask`** 로. `settings.json` allow 에서 `git push` 를 빼고
  (`ask` 가 `allow` 를 이기므로 동작은 같지만 목록이 모순돼 보였다) `opencode.json` 도 맞췄다.
- **브랜치 생성은 도구 allow 로 두고 Gate 1 이 일괄 승인을 겸한다.** 브랜치 생성은 매 단계
  필요한 절차 필수 행위라, force push 와 달리 도구 `ask` 로 두면 승인 창이 없는 headless
  환경에서 1단계에서 절차가 멈춘다. Gate 1 은 어차피 Owner 가 답하는 지점이라 새로 막히는
  곳이 생기지 않는다. 계획에 없는 브랜치는 C등급.

역할 본문 10종·가드 훅 2종·`guard.js`·`selfcheck.py` 는 불변.

## [1.32.0] — Windows 클론 경로로 새던 가드 구멍

설치 시점은 보호되고 있었지만 **설치 이후 Windows 에서 클론하는 경로**가 무방비였다.
생성된 프로젝트를 커밋한 뒤 Git for Windows 기본값(`core.autocrlf=true`)으로 클론하면:

| | 지금(AS-IS) | 앞으로(TO-BE) |
|---|---|---|
| `dev-agent-team/hooks/*.sh` | CRLF 가 되어 `block_on_owner_question.sh` 가 exit 255. 그 값은 차단(exit 2)으로 해석되지 않아 **Owner 질문 대기 중에도 에이전트가 진행** | 설치되는 `.gitattributes` 가 LF 로 고정 → 클론해도 CRLF 가 되지 않음 |
| `AGENTS.md`·`CLAUDE.md` | CRLF 가 되어 conffile 해시 불일치 → Owner 가 손댄 적 없는데 "직접 수정" 오탐 + `.new`. **이후 하네스 업데이트가 헌법에 영영 반영되지 않음** | 해시를 CR 제거 후 계산 → 줄끝 변화는 무시, 진짜 편집은 그대로 보존 |
| 검증 | `verify_hooks` 19번이 *이미 CRLF 가 된 상태*만 탐지(설치 때만 돎) | 21번이 *예방 장치가 깔렸는지*를 함께 확인 |

- `templates/project/gitattributes` 신설 → 설치 시 대상 프로젝트의 `.gitattributes` 로.
  Owner 가 이미 쓰던 파일이면 **덮지 않고** `team-dev-harness-eol-guard` 블록만 끝에 덧붙인다(멱등).
- `sha256_of`(init.sh)·`Sha256Of`(init.ps1) 이 CR 을 지우고 해시한다. LF 파일은 해시가
  그대로라 **기존 manifest 와 호환**되고, 이미 CRLF 로 망가진 프로젝트는 재설치 때 복구된다.
- 탐지 패턴을 ASCII 센티널로 뒀다 — PowerShell 5.1 의 `Select-String` 이 BOM 없는 UTF-8 의
  한글을 못 읽어 매 설치마다 중복 추가될 수 있었다.
- `verify_hooks.sh` 21항목으로. 19번 주석의 사실 오류(조용한 통과 → exit 255 실행 실패) 정정.

역할 본문·권한 파일(`settings.json`·`opencode.json`)·가드 훅 로직·`selfcheck.py` 는 불변.

## [1.31.0] - 2026-09-11

앞선 보고에서 남겨둔 두 가지를 고치되, 문서 경고가 아니라 **요구사항을 만족하는 방안**을 넣었다.

### Fixed
- **1.29.0이 만든 모순을 해소했다.** `AGENTS.md` 규칙 5는 "force push는 Owner 승인 후에만"으로
  고쳤는데 team-dev 금지 절은 여전히 **"force push는 하지 않는다"** 였다. 절차와 헌법이
  어긋나 있어서, 에이전트가 승인 프롬프트를 받고도 스스로 물러서게 돼 있었다.

### Changed
- **`ask` 가 실제로 동작하도록 세 겹을 뒀다.** opencode 의 `ask` 는 UI·터미널이 없는 headless
  컨테이너에서 멈출 수 있는데, 지금까지는 "알려진 제약"에 경고만 있었다. 핵심 사실은
  **force push 가 절차의 어느 경로에서도 필요하지 않다**는 것이다(`templates/` 전체에서
  force 는 금지 문장에만 나온다). 그래서 hang 을 감내하는 대신 **일어날 상황 자체를 없앤다**:
  1. 절차 — force push 는 **Owner 가 명시적으로 요청할 때만** 시도한다. 에이전트가 스스로
     판단해서 하지 않으므로 Owner 가 없는 headless 환경에서는 애초에 발생하지 않는다.
  2. 실행 환경 — 컨테이너 권장 문구에 **TTY 연결**을 구체 명령으로 적었다
     (`docker run -it -v "$PWD":/work -w /work ...`; devcontainer 는 기본 제공).
  3. 그래도 막히면 — 하지 않고 **Owner 에게 보고**한다. 절차 필수가 아니라 진행이 안 멈춘다.
- **Gate 0(요구사항 확인)도 Gate 1 과 같은 3지선다가 됐다.** `"맞나요? 1.네 2.수정"` 에는
  not-go 가 없었고 2번 경로도 절차에 없었다 — Gate 1 에서 고친 것과 같은 빈틈이다.
  - 1 → 계획으로(4번)
  - 2 → 무엇이 틀렸는지·빠졌는지 듣고 1번으로 돌아가 다시 묻고 REQUIREMENTS 갱신 후 3번으로
  - 3 → 멈춘다. **`REQUIREMENTS.md` 는 지우지 않는다** — 그것마저 지우면 Owner 가 처음부터
    다시 답해야 한다. 다시 "개발 시작"이라고 하면 3번부터 이어간다.
  - "Owner 가 답하기 전에는 4번으로 넘어가지 않는다"를 명시.
- `OWNER_GUIDE.md` 의 "시작할 때" 에 요구사항 확인 3선택지 안내를 넣었다.

### Compatibility
- 게이트 형식은 정지 메커니즘의 일부라 `HARNESS_VERSION` 을 1.31.0으로 올린다.
- **권한 설정은 건드리지 않았다** — 1.29.0의 `ask` 구성(`settings.json`·`opencode.json`)은
  그대로 두고 **사용 규칙만 좁혔다**.
- "Owner 가 요청할 때만"은 프롬프트 규칙이라 기계적 강제는 아니다. 다만 어겨도 `ask` 가 한 겹
  더 있고, headless 라면 거기서 멈출 뿐 잘못된 push 는 나가지 않는다 — 실패 방향이 안전하다.
- `init.sh`/`init.ps1`, 가드 훅, `selfcheck.py`, 역할 본문은 건드리지 않았다.

## [1.30.0] - 2026-09-11

### Changed
- **Gate 1(계획 승인)에 실제 not-go 를 넣었다.** Owner 지시 — "PLAN을 수립한 후 PLAN.md를
  Owner에게 보여주고 go/not-go 를 결정할 수 있도록 한다."
  **보여주는 것 자체는 이미 있었다**(5번이 `PLAN.md` 를 보여주고 승인을 받는다). 빈틈은 둘이었다:
  1. 선택지가 `1. 네, 시작` / `2. 수정하고 싶다` 뿐이라 **"지금은 하지 않겠다"를 고를 수 없었다.**
  2. `1을 받으면 진행한다` 만 있고 **2번을 고르면 뭘 하는지 절차에 없었다** — 에이전트가
     알아서 하게 되어 있었다.

  이제 3지선다이고 각 경로를 끝까지 적는다:
  - 1 → 6번으로 진행
  - 2 → 무엇을 고칠지 듣고 4번(planner 호출)으로 돌아갔다가 다시 5번
  - 3 → 시작하지 않고 멈춘다. **`PLAN.json`·`PLAN.md` 는 지우지 않는다** — not-go 가 작업
    폐기가 되면 Owner 가 고르기 어려워진다. 다시 "개발 시작"이라고 하면 5번부터 이어간다.

  "Owner가 답하기 전에는 6번으로 넘어가지 않는다"를 명시했다.
- `OWNER_GUIDE.md` 의 "시작할 때" 안내도 세 선택지로 바꿨다. Owner 가 읽는 유일한 문서라
  여기에 없으면 선택지가 있는 줄 모른다.

### Compatibility
- 게이트 형식은 정지 메커니즘의 일부라 `HARNESS_VERSION` 을 1.30.0으로 올린다.
- 양 프로파일 동일하다. 역할 본문·가드 훅·`selfcheck.py`·설치기는 건드리지 않았다.
- **Gate 0(요구사항 확인)에는 같은 빈틈이 남아 있다** — `"맞나요? 1.네 2.수정"` 으로 중단
  선택지가 없다. Owner 지시가 PLAN 에 관한 것이라 이번엔 Gate 1 만 고쳤다.

## [1.29.0] - 2026-09-11

### Changed
- **force push 를 `deny` 에서 `ask` 로 옮겼다.** 지금까지는 막히면 끝이라, 정말 필요한
  순간(작업 브랜치 정리, rebase 후 `--force-with-lease`)에 **Owner 가 터미널로 나가 직접
  실행**해야 했다. 이제 그 자리에서 승인을 물어보고 에이전트가 실행한다.
  - `.claude/settings.json` — `ask` 배열 신설, `deny` 에서 force push 3개 제거.
    `allow` 의 `Bash(git push:*)` 는 그대로 둔다. Claude Code 의 평가 순서가
    **deny → ask → allow** 이고 "a matching ask rule prompts even when a more specific
    allow rule also matches the same call" 이라, 넓은 allow 가 있어도 force 용 ask 가 이긴다.
  - `opencode.json` — force push 4패턴(`git push*--force*` 포괄 포함)을 `"ask"` 로.
  - `AGENTS.md` 규칙 5 — "force push 는 하지 않는다" → "**Owner 승인을 받은 뒤에만** 한다".
    프롬프트 규칙과 권한 설정이 어긋나면 에이전트가 승인 프롬프트를 받고도 스스로 물러선다.
- **나머지 deny 는 그대로다** — `rm -rf`·`rm -r`·`git reset --hard`·`git branch -D`·
  `python -c`·`python3 -c`·`node -e`·`node --eval`·`curl`·`wget`.
- **main 직접 push 는 이번 범위가 아니다.** 규칙 문자열로는 `git push`(업스트림 생략)나
  `git push origin HEAD` 의 대상 브랜치를 가릴 수 없어 부분적 강제밖에 안 된다.
  지금처럼 AGENTS.md 프롬프트 규칙으로 남긴다.
- Codex 는 바뀌지 않는다 — `.codex/config.toml` 에 deny 목록 자체가 없고 sandbox+approval 로 간다.

### Compatibility
- deny 목록은 호환성 계약이고 이번이 **완화**라 `HARNESS_VERSION` 을 1.29.0으로 올린다.
- **완화의 근거는 "Owner 가 그 자리에서 승인한다"는 것이다.** 승인 프롬프트가 뜨지 않는
  환경에서는 완화가 아니라 구멍이 된다 — 특히 **opencode 의 `ask` 는 UI·터미널이 없는
  headless 컨테이너에서 멈추거나 예측 불가하게 동작한다.** 이 저장소가 컨테이너 실행을
  권장하므로 "알려진 제약"에 명시했다.
- `git -C . push --force` 같은 우회 형태는 규칙이 잡지 못한다(deny였을 때도 같았다).
  가드 규칙은 샌드박스가 아니라 과속방지턱이라는 기존 서술과 일관된다.

## [1.28.0] - 2026-09-11

Owner 지적: "코드를 조금만 고쳐도 테스트를 전부 실행하는 것은 과도하다."

### Context
`checker` 는 "항상 전체를 실행한다"였고 루프 재호출 지점이 4곳(게이트·reviewer·security·
NEW_FAIL/REGRESSION), 한도가 단계당 15회(large)·10회(small)였다. 단계 5~7개면 전체 스위트를
100회 가까이 돈다. 테스트는 append-only라 뒤로 갈수록 무거워진다.
토큰 비용은 checker 출력 형식이 고정이라 이미 통제돼 있었고, 실제로 커지는 것은 **벽시계
시간**이었다.

### Added
- **테스트 실행 범위를 위치로 가른다.** "기능 추가냐 버그 수정이냐"는 주관 판단이라 쓰지
  않는다 — 작은 모델이 오분류하면 회귀 검사가 통째로 빠진다. 대신:

  | 시점 | 범위 |
  |---|---|
  | 11번 구현 직후 | **FULL** — 회귀를 잡기 가장 좋은 지점. NEW_FAIL/REGRESSION 분류가 살아 있어야 coder가 올바로 고친다 |
  | 루프 재검사 (최대 13회) | **SCOPED** — 이번 단계 파일 + 직전 FAILED가 가리킨 파일 |
  | merge 직전 | **FULL** 1회 |

  **그룹핑은 이미 하니스에 있었다.** `tester` 가 강제하는 파일명(`stage_N_test.py`)과 테스트
  이름의 R번호가 네 러너 모두에서 네이티브로 선택 가능하다(`pytest tests/stage_3_test.py`,
  `go test -run TestR3`, `cargo test r3_`, `jest <파일>`). 플러그인도 import 그래프 분석도
  새 규약도 필요 없었다 — 안 쓰고 있었을 뿐이다.
- **`selfcheck.py --record-full-test` 와 게이트 차단 4종째(full-test).**
  프롬프트로 "전체를 돌려라"라고 적는 것만으로는 강제가 안 된다. FULL 통과 후 소스+tests
  트리 해시를 `dev-agent-team/.last-full-test` 에 기록하고, 게이트가 현재 해시와 대조해
  다르면 merge를 막는다. selfcheck가 해시를 스스로 계산하므로 기록자와 검증자가 같은
  코드다(`.harness-manifest` 와 같은 방식). reviewer·security 지적으로 코드가 바뀌면
  자동으로 다시 FULL을 요구한다 — 실제로 막아야 할 경우다.

### Changed
- `checker` 규칙 1이 모드 기반이 됐다. 모드를 안 주면 **FULL**(안전한 기본값)이고,
  러너가 선택을 지원하지 않으면 **FULL로 폴백**한다(Owner 지침: 그룹핑 수단이 없으면 전체를
  돌려도 된다). 출력에 `MODE:`·`ELAPSED:` 를 더했다.
- SCOPED에서는 이전 단계 파일을 안 돌리므로 REGRESSION이 안 나올 수 있다는 단서를 달았다 —
  "안 돌린 것을 통과로 보고하지 않는다".
- 게이트가 단계당 두 번 돈다. 앞은 싼 조기 필터(print·trace를 리뷰 앞에서 거른다),
  뒤는 최종 권위(최종 코드 + 전체 실행 신선도). 둘 다 정규식 스캔이라 비용이 무시할 수준이다.

### Compatibility
- **초기 상태는 막지 않는다** — `PLAN.json` 이 없으면 신선도 검사를 SKIP한다(`scan_trace` 와
  같은 방식). 갓 설치한 트리에서 `--gate` 가 exit 0 인 것을 확인했다.
- **기본 모드(플래그 없음)는 신선도를 보지 않는다.** 개발 중 아무 때나 돌리는 용도라
  항상 걸리면 쓸모가 없다.
- `dev-agent-team/.last-full-test` 가 파일 맵과 호환성 계약에 늘어 `HARNESS_VERSION` 을
  1.28.0으로 올린다. 양 프로파일 공통이다(판단이 0이다).
- **감수하는 것**: 루프 중간에 생긴 회귀는 merge 직전 FULL에서야 드러나 왕복이 한 번 늘 수
  있다. 대신 13회의 전체 실행을 아낀다. 11번을 FULL로 둔 것이 가장 흔한 회귀를 즉시 잡는다.
- `init.sh`/`init.ps1`, 가드 훅, `verify_hooks.sh`(20항목)는 건드리지 않았다.

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
