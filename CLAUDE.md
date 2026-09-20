# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 이 저장소의 정체

이것은 앱이 아니라 **하니스 생성기(harness generator)** 다. `templates/` 의 단일 소스를
`init.sh` / `init.ps1` 이 설치 시점에 **프로파일(small/large) × 대상 에이전트(claude/codex/
opencode)** 로 렌더링하여 **대상 프로젝트 폴더**에 헌법·역할·skill·가드레일을 깔아준다.
설치된 결과물은 요구사항을 입력하면 planner / tester / coder / checker / documenter 5개 역할이
Stage-Gate 방식으로 자동 개발하는 팀이다.

**목적**: 코딩 에이전트에 변수 이름 등 코딩 규칙·로깅 규칙·테스트케이스 작성 규칙 같은
개발 관행을 주입하는 **skill-set**이다. 사용자는 초보자와 중급자 이상 모두를 대상으로 한다.

**산출물의 비종속성 (중요)**: 여기서 제공하는 harness/skill(= `templates/` 의 결과물)은
**codex, opencode, claude code** 등 여러 코딩 에이전트가 사용한다. 공통 헌법은 `AGENTS.md`,
가드레일은 에이전트별 방식으로 깔린다(Claude=hook, Codex=hook.json, opencode=plugin).
각 에이전트 메커니즘과 출처는 README "멀티 에이전트 지원" 절에 정리돼 있다. 단, **이 저장소
자체의 정리·개발은 Claude Code로 진행**하므로 *저장소 운영용* Claude Code 전용 도구는
두어도 된다. "산출물(다중 에이전트용)"과 "저장소 운영 도구(Claude Code 전용 가능)"를
구분할 것.

**핵심 구분 — 두 종류의 파일을 혼동하지 말 것:**
- 루트 파일(`init.sh`, `init.ps1`, `tests/`, `README.md`, 이 `CLAUDE.md`) = **설치기 본체**. 직접 동작한다.
- `templates/**` = **렌더링 입력**. 절대 그 자리에서 실행되지 않는다. 편집하면 *앞으로 생성될
  프로젝트*가 바뀐다. 특히 `templates/CLAUDE.md.tmpl` 은 설치된 프로젝트의 CLAUDE.md가 되는
  것이지 이 파일이 아니다.

## 명령어

```bash
# 설치(렌더링) — 저장소 안에는 설치 불가, 반드시 외부 대상 폴더 지정
./init.sh --profile large --agent all /tmp/t1              # large: claude+codex+opencode
./init.sh --profile large --agent codex /tmp/t2            # codex는 large 전용
./init.sh --profile small --agent claude,opencode /tmp/t3  # small(온프레미스): codex 불가
./init.sh ~/projects/my-app                     # 신규면 자동 판별. **재설치면 기존 프로파일·에이전트를 유지**한다

# 저장소 전체 검증 — 고치고 나면 이것 하나만 돌리면 된다
./tests/run_all.sh                    # 설치 3종 + 격리 + 파리티 + 단위 테스트 + 재설치

# 설치 검증 (init.sh가 설치 끝에 자동 실행; 단독 실행도 가능)
./tests/verify_install.sh /tmp/t1     # 구성·파일·설정·헌법 동결 + 가드 훅 실동작까지
./tests/verify_hooks.sh /tmp/t1       # 가드 훅만: 30항목(샌드박스를 git 저장소로 만들어 돈다)

# init.sh ↔ init.ps1 파리티 검증 (pwsh 없이 코드리뷰를 자동화한 것)
python3 tests/verify_parity.py            # 매핑·역할목록·스킬·템플릿
python3 tests/verify_parity.py /tmp/t1    # + 역할 렌더 결과를 바이트 비교

# 역할 호출에 붙일 PROCESS 개정만 뽑는다 (전문을 주지 않는다)
python3 dev-agent-team/selfcheck.py --process-active coder
python3 dev-agent-team/selfcheck.py --process-stats      # 얼마나 쌓였나 · 통합이 필요한가
python3 dev-agent-team/selfcheck.py --direction-head     # DIRECTION 은 마지막 절만
python3 dev-agent-team/selfcheck.py --ledger DECISIONS.md  # 예산 안에서 최근 것부터
python3 dev-agent-team/selfcheck.py --ledger-archive DECISIONS.md --keep 10  # 파일을 줄인다
python3 dev-agent-team/selfcheck.py --ledger-stats         # 누적 문서 크기 · 큰 절 · 묵은 백로그
python3 dev-agent-team/selfcheck.py --migrate-check         # 기존 내용이 새 규약과 어긋나는 곳
python3 dev-agent-team/selfcheck.py --process-check         # PROCESS 를 어떻게 줄일지

# 회고가 필요한 단계인지 기계로 판정 (12c 가 매번 이걸 먼저 돌린다)
python3 dev-agent-team/selfcheck.py --retro-check

# 회고용 TEST_LOG 요약 (17b 가 전체 대신 이걸 쓴다)
python3 dev-agent-team/selfcheck.py --log-summary   # 추세 + 최근 10단계

# 헌법 동결 해소 — 한 명령으로 (Owner 규칙 이관 + 새 헌법 채택 + manifest 정정)
./init.sh --accept-constitution /tmp/t1

# selfcheck 판정 로직 테스트 (권고 축·조기 탈출·진동 방지·plan_broken)
python3 tests/test_selfcheck.py           # 169항목. selfcheck.py 를 고치면 반드시 돌린다

# 절차 무결성 (플래그·역할·단계 번호·고아 단계) — 절차를 고치면 반드시 돌린다
python3 tests/test_procedure.py /tmp/t1   # 6항목. 인자 없으면 임시로 설치해서 본다

# 설치기 동작 테스트 (재설치가 구성·상태를 안 바꾸는지, --accept-constitution)
python3 tests/test_install.py             # 116항목(기존 프로젝트·마이그레이션·헌법 동결 안내·프로파일 강등). init.sh 를 고치면 반드시 돌린다

# Windows 동등물 (init.sh와 동일 렌더링 — pwsh 없으면 코드리뷰로 파리티 확인)
.\init.ps1 -Profile large -Agent all -Target C:\projects\my-app
```

변경 후 검증 루틴: **`./tests/run_all.sh` 하나로 끝난다**(FAIL 0 이어야 한다). 그 안에서
large·small·codex 단독 설치와 설치 검증, 단일 에이전트 격리, small+codex 거부,
파리티(양 프로파일 렌더 대조), `test_selfcheck.py`, `test_install.py`, 플래그 없는 재설치가
구성을 유지하는지까지 돈다. 개별 스크립트는 위 "명령어" 절 참조 — 좁혀서 볼 때만 쓴다.

## 렌더링 메커니즘 (init.sh `render()`)

1. **블록 마커**: `{{#IF_SMALL}}`/`{{#IF_LARGE}}` … `{{/IF_SMALL}}`/`{{/IF_LARGE}}`.
   awk가 처리하므로 **마커는 반드시 한 줄을 통째로 차지**해야 한다(앞뒤 공백·텍스트 금지).
2. **변수 치환**: `{{PROFILE_LABEL}}`, `{{RETRY_LIMIT}}`, `{{MAX_CHECKER_CALLS}}`,
   `{{HARNESS_VERSION}}`. 값은 `profiles/{small,large}.conf` 와 `HARNESS_VERSION` 에서 온다.
   새 변수를 추가하면 `init.sh` 와 `init.ps1` 의 sed/치환 목록 **양쪽 모두** 갱신해야 한다.

`.tmpl` 파일은 렌더링되고, `templates/hooks/*`(→`dev-agent-team/hooks/`)·`templates/common/logger.py`·
`templates/docs/*`·`templates/project/*`·`templates/codex/hooks.json`·
`templates/opencode/plugins/guard.js` 는 그대로 복사된다(`init.sh` §4–7 참조).

3. **역할 본문 단일 소스**: `templates/roles/<role>.md.tmpl` 10개(planner/tester/coder/checker/documenter/designer, +lead/reviewer/critic/security)가 단일 소스다. designer는 양 프로파일 공통(UI 단계에서만 호출)이고, lead·reviewer·critic·security는 large 프로파일에서만 emit된다(`init.sh`/`init.ps1`의 `$ROLES`/`$Roles`). init이
   에이전트별 frontmatter를 붙여 렌더한다 — Claude=`.claude/agents/<role>.md`(name/description/
   tools), Codex=`.agents/skills/<role>/SKILL.md`(name/description), opencode=
   `.opencode/agents/<role>.md`(description/mode/tools). frontmatter 매핑(설명·tools)은
   `init.sh`/`init.ps1` 의 `role_desc`/`claude_tools`/`opencode_tools` 에 있고 **양쪽 모두**
   고쳐야 한다. 빠뜨렸는지는 `python3 tests/verify_parity.py` 가 잡는다 — 역할을 추가하면
   매핑이 5군데라 손으로 대조하면 반드시 빠뜨린다.

## 에이전트 오버레이 (어디에 무엇이 깔리나)

- **공통**: `AGENTS.md`(헌법), `dev-agent-team/`(+`dev-agent-team/hooks/` 가드 스크립트), `common/`, `tests/` `logs/`.
- **claude**: `CLAUDE.md`(@AGENTS.md), `.claude/settings.json`·`agents/`·`skills/`.
- **codex**: `.codex/config.toml`(large 전용이라 `model_reasoning_effort="high"` 무조건 포함)·`.codex/hooks.json`(→`dev-agent-team/hooks` 재사용), `.agents/skills/`.
  **codex는 large 프로파일 전용**이다 — small에서 codex가 요청되면(`all` 포함) init이 프로파일 확정 직후 에러로 중단한다(`init.sh`/`init.ps1` 양쪽 가드).
- **opencode**: `opencode.json`, `.opencode/agents/`·`.opencode/plugins/guard.js`,
  스킬은 `.agents/skills/`(호환 경로)로 보장.

스킬 6종(team-dev/logging-rule/lib-research/code-convention/test-design/ui-design)은 claude면 `.claude/skills/`,
codex/opencode면 `.agents/skills/` 로 렌더된다(`emit_skills`).

## 프로파일은 이 13가지만 다르다

`profiles/*.conf`(RETRY_LIMIT, MAX_CHECKER_CALLS)와 `.tmpl` 안의 `{{#IF_*}}` 블록으로만
차이를 만든다. 새 차이를 도입할 때도 이 두 경로만 쓴다 — 별도 분기 파일을 만들지 말 것.
차이 13종: RETRY_LIMIT, MAX_CHECKER_CALLS, tester 추가 탐색, coder 단계 밖 발견→BACKLOG 보고(large만),
coder 디버깅 절차, 영향 표 산정 방식, 단계 시작 병렬성, reviewer 역할(large 전용 코드·테스트 리뷰),
lead 역할(large 전용 팀장 방향·백로그 그루밍, DIRECTION.md; 회고 모드 2종(단계 12c·최종 17b)과 절차 자기개선 제안 IMPROVE),
critic 역할(large 전용 결정 심의·합의; 명확하면 자율, 모호·고위험은 Owner),
security 역할(large 전용 보안 점검), planner 요구사항 충돌·누락 점검(large만),
절차 자기개선(large 전용 lead 회고→[절차개선] BACKLOG 누적→7-0/17b에서 Owner 승인→PROCESS.md 오버레이). (BACKLOG.md 파일 자체는 양 프로파일 공통.)

## 생성된 프로젝트의 디렉터리 규약

에이전트 작업/상태 파일은 모두 **`dev-agent-team/`** 아래에 둔다(REQUIREMENTS, PLAN.json/PLAN.md,
DECISIONS, TEST_LOG, OWNER_QUESTION, BACKLOG, PROJECT_RULES, DIRECTION(large), PROCESS(large), DESIGN(UI 단계), `dev-agent-team/libs/`, `dev-agent-team/answered/`, `dev-agent-team/guides/`).
**에이전트가 실행하는 코드·스크립트도 `dev-agent-team/` 안에 둔다** — 가드 훅(`dev-agent-team/hooks/*.sh`),
자가점검 도구(`dev-agent-team/selfcheck.py`). generic depth-1 폴더에 두면 제품 폴더와 헷갈리므로 금지.
`tests/` `logs/` `common/` 은 **제품 디렉터리**(만들고 있는 프로그램의 것 — pytest 표준 위치,
앱 런타임 로그, 제품 공통 코드 `common/logger.py`)라 이름이 겹쳐도 그대로 둔다. 경로를 옮기면 호환성
계약이 바뀌므로 `HARNESS_VERSION` 을 올린다(team/ 도입 v1.2.0 → `dev-agent-team/` 개명 v1.3.0 →
selfcheck를 `common/`에서 `dev-agent-team/`로 v1.9.0).

## 호환성 계약 — 변경 시 `HARNESS_VERSION` 을 올릴 것

프로파일과 무관하게 동일해야 하는 것들이다. 이 계약 덕에 small↔large **무손실 모델 전환
인수인계**가 성립한다(상태가 전부 파일에 있음). 계약을 바꾸면 README "호환성 계약" 절과
`HARNESS_VERSION` 을 함께 갱신한다.

### 상태 파일의 위치와 형식
- `dev-agent-team/` 레이아웃, `dev-agent-team/PLAN.json` 스키마, `dev-agent-team/DECISIONS.md`
  — `PLAN.json` 의 `current_stage` 는 **merge 때마다 메인 세션이 올린다**(마지막 단계 뒤에는
  마지막 id + 1 = "다 끝났다"). selfcheck 의 `trace`·`doc` 축과 이어하기 판정이 이 값을 쓴다.
- `dev-agent-team/TEST_LOG.md` — 7열 고정(단계·신규·누적·전체 결과·재시도·리뷰지적·커밋).
  열 구성은 양 프로파일 동일.
- `dev-agent-team/OWNER_QUESTION.md` 형식 — 기존 동작을 바꾸는 질문이면 영향 표 앞에
  "지금 → 앞으로" AS-IS/TO-BE 표. DECISIONS에는 `- 변경:` 줄.
- `dev-agent-team/PROCESS.md` 형식 — P번호·append-only, large 전용.
- `dev-agent-team/PROJECT_RULES.md` — Owner가 쓰는 프로젝트 고유 규칙, 재설치해도 보존.
  헌법을 좁히는 방향으로만 작동하고 안전장치는 무효화 못 한다.
  Claude=@import, opencode=instructions, codex=헌법 지시.
- `dev-agent-team/.last-full-test` — 소스+tests 트리 해시. FULL 실행 뒤 코드가 바뀌면 게이트가 막는다.
- 커밋 메시지, 브랜치명.

### 재설치 규칙 (conffile)
- `dev-agent-team/.harness-manifest` 는 `AGENTS.md`·`CLAUDE.md` 의 설치 시 해시다. 재설치 때
  Owner 편집 여부를 가려, 편집했으면 덮지 않고 `.new` 로 둔다. 강제 장치(훅·권한·역할·스킬)는
  이 규칙을 쓰지 않고 무조건 덮어쓴다.
- **버전을 담는 파일만 나이를 잰다.** `CLAUDE.md` 는 `@AGENTS.md` 를 import 하는 얇은 파일이라
  `HARNESS_VERSION` 줄이 없다. 새 버전을 *설치기 버전*으로 잡으면 "옛 파일에 버전이 없다"가 늘
  참이 되어 갓 설치한 프로젝트를 고쳐도 "아주 오래된 헌법" 경고가 뜬다. 새 버전은 **이번에
  렌더한 그 파일(`.new`)** 에서 읽는다 — 나이를 잴 근거가 없으면 재지 않는다.
  **담지 않는 것과 못 읽은 것은 다르다**(`v?` 로 뭉뚱그리지 말 것).
- **manifest 에 적는 것은 "이번에 설치한 것"의 해시다.** Owner 편집을 보존한 경우에는
  아무것도 설치하지 않았으므로 **기록을 그대로 둔다**. 여기에 현재 파일(=편집본) 해시를
  적었더니 다음 설치에서 `CURHASH == RECORDED` 가 되어 "Owner 가 안 건드림" 으로 보였고
  **편집본이 백업도 없이 덮였다** — 동결이 딱 한 번의 설치만 버텼다. 실제 Owner 프로젝트의
  157줄짜리 헌법이 재설치 두 번 만에 사라졌다.
- 해시는 **CR 을 지우고** 계산한다 — Windows 에서 git 이 줄끝을 바꾼 것을 Owner 편집으로
  오인하면 헌법이 영영 갱신되지 않는다.
- **`.new` 가 남아 있으면 그 파일만 옛 버전에 묶인 '헌법 동결' 상태다** — 절차·역할·권한은
  새 버전이라 규칙이 어긋난다. **설치 중 사람이 있으면 그 자리에서 3지선다로 묻는다**(1.채택 / 2.그대로 / 3.나중에).
  기본 채택은 하지 않는다 — 이관 판정이 어림짐작이라 사람 판단이 필요한 줄이 남고, 새 헌법과
  충돌하는 옛 줄이 되살아날 수 있다. 사람이 없으면(headless·CI) 묻지 않고 보존한다. 1번을
  고르면 `--accept-constitution` 으로 설치를 한 번 더 돌린다(그래야 manifest 가 맞는다).
  그 밖에 세 곳에서 보인다: 설치 시 두 버전을 숫자로 안내,
  `selfcheck` 의 `[constitution]` 줄(차단은 안 한다), team-dev "시작할 때" 절이 Owner 에게
  3지선다로 묻는다. 해소는 `./init.sh --accept-constitution <대상>` 한 명령이다 — Owner 가
  직접 넣은 줄을 `PROJECT_RULES.md` 로 옮기고, `.new` 를 본파일로 올린 뒤(이전 내용은
  `.owner-backup`), 그대로 설치를 계속해 manifest 까지 맞춘다. 설치 알림은 마이너 버전 차이가
  5단계 이상이면 "정상 동작하지 않는다"고 강하게 말한다.
  이관할 줄은 **`selfcheck.py --owner-lines <파일>` 이 준다**(기계용). 설치기가
  `--constitution-diff`(사람용)를 긁어 옮기던 때는 그 출력이 20줄에서 끊기고 "… 외 N줄" 을
  붙이며 파일도 안 가려서, 157줄짜리 헌법에서 **97줄이 조용히 사라지고** 생략 표시가 규칙으로
  옮겨지고 다른 파일 줄까지 딸려 가 중복됐다. 안내는 "옮겼습니다" 였다.
  Owner 줄인지 하네스 옛 문장인지는 **어절 겹침 어림짐작**이라 양쪽으로 틀린다 — 진짜 Owner
  규칙이 걸러지기도 하고(`repos/ 에는 push 하지 않는다`), 전부 옮기면 새 헌법과 충돌하는 옛
  줄이 되살아나기도 한다(`Stage-Gate 는 쓰지 않는다`). 그래서 **활성화하지 않되 버리지도
  않는다**: `--owner-lines` 는 확실한 것만, `--owner-lines-skipped` 는 애매한 것을 내고
  설치기가 **양쪽 다 보고**한다. 고르는 것은 Owner 몫이다.
  업데이트 **범위**는 `selfcheck.py --constitution-diff` 가 낸다 —
  바뀐 규칙 번호·새로 생긴 규칙·Owner 가 직접 넣은 줄을 **두 파일을 직접 비교해** 뽑는다
  (버전별 메타데이터를 손으로 들고 있지 않는다. 그런 표는 반드시 낡는다). 해소는 Owner 규칙을 `PROJECT_RULES.md` 로 옮기고 `.new` 를 본파일로
  옮긴 뒤 **설치를 한 번 더** 돌리는 것이다(그래야 manifest 가 맞는다).
- **프로파일을 낮추면 옛 역할을 치운다.** 역할·스킬·훅은 무조건 덮어쓰는 강제 장치인데
  덮어쓰기만 있고 치우기가 없어, large→small 재설치 후에도 lead·reviewer·critic·security
  가 남았다. 남은 `lead.md` 는 **재설치 프로파일 추론과 설치 검증이 둘 다 보는
  흔적**이라, 한 번 남으면 영영 large 로 되돌아오고 검증도 못 잡는다(흔적으로 판정한 대가).
  지우는 대상은 **알려진 역할 이름 11개뿐**(폐지한 evaluator 포함 — 남겨야 옛 설치본에서
  치운다) — Owner 가 직접 넣은 에이전트는 건드리지 않는다.
- **헌법 동결은 설치 실패가 아니다.** 설치기가 Owner 편집을 지키려고 일부러 남긴 상태이므로
  `verify_install.sh` 에서 WARN 이다. 막는 일은 merge 게이트(`constitution`)가 fail-closed 로
  한다. 설치 검증이 실패하면 init 은 **걸린 항목을 그대로 옮긴다** — 예전엔 무엇이 걸렸든
  "hook 검증 실패" 라고만 해서, 가드 훅이 26/26 통과한 설치에도 "안전장치가 동작하지 않을 수
  있습니다" 가 나갔다.
- `.gitattributes` — 가드 훅 `*.sh` 의 줄끝을 대상 프로젝트의 git 에서도 LF 로 고정한다.
  없으면 Windows 클론 시 `block_on_owner_question` 이 exit 255 로 실패해 정지 메커니즘이
  무력화된다. Owner 가 이미 쓰던 파일이면 덮지 않고 `team-dev-harness-eol-guard` 블록만 덧붙인다.

### 검사 시점 3분할 (team-dev "언제 무엇을 하나"가 정본)
- **commit 전** — 테스트 커밋 전 `[collect]`, 구현 커밋 전 `--gate` 조기 필터·checker SCOPED.
- **push 시** — remote 있을 때만, 작업 브랜치 확인.
- **PR 시** — main 합치기 직전 단계당 1회: checker FULL·`--record-full-test`·`--gate` 4종·
  documenter(그 단계 R번호)·`--score`, large면 reviewer·security.
- 구현 직후 11번도 FULL 이다. main 합류 지점은 하나 — remote 있으면 PR, 없으면 로컬 merge이고
  게이트 내용은 같다.

### 이어하기(진입점 판정)
- "개발 시작"은 신규·재개·업데이트 후 모두 같은 말이다. team-dev "어디서부터 할지 정한다"가
  **파일만 보고** 진입점을 고른다: REQUIREMENTS 없음→1번 / PLAN 없음→3번 /
  PLAN 있고 진행 흔적 있음→**6번(현재 단계)** / 진행 흔적 없음→5번(Gate 1).
  진행 흔적 = `current_stage` ≥ 2 또는 TEST_LOG 에 단계 행 존재.
- **PLAN 과 TEST_LOG 가 어긋나면 C등급**이다(스스로 고르지 않는다). 어느 쪽이 맞는지는
  Owner만 안다 — 추측해 고치면 진행한 단계를 덮거나 끝난 단계를 다시 한다.
- **있는 것을 다시 만들지 않는다** — 계획이 있으면 planner를 다시 부르지 않는다.
  Owner가 명시적으로 요청하면 그건 기존 결정 변경이라 C등급이다.
- 업데이트로 절차가 바뀌어도 **새 절차로 이어간다**. 지난 검사를 소급하지 않되 merge 게이트는
  새 기준으로 돈다.

### 정지 메커니즘
- C등급 목록과 정지 메커니즘. 단계 merge 전 `selfcheck.py --gate` 가 collect·print·trace·full-test 를 차단한다.
- **읽지 못한 소스가 있으면 게이트가 막는다**(`read`). 조용히 건너뛰면 그 파일의 print
  위반이 사라져 "0건" 으로 보고된다 — CP949 한글 소스·권한 없는 파일에서 실제로 그랬다.
- **가드 스크립트가 없으면 게이트가 막는다**(`guards`). 훅은 실행에 실패해도 도구를 막지
  않으므로, 파일이 지워지면 안전장치가 **조용히** 죽는다. 설치 검증은 설치 때만 도니
  그 사이를 게이트가 본다(`hooks/*.sh` 2종 + opencode 설치본이면 `guard.js`).
- **헌법 동결도 게이트가 막는다**(`constitution`). 버전이 뒤처진 경우만이고, 같은 버전에서
  Owner 가 편집만 한 경우는 막지 않는다. 그 상태의 팀은 옛 헌법 + 새 절차로 도는 것이라
  틀리게 간다 — 코드는 계속 쓸 수 있고 막히는 건 merge 뿐이다.
- Gate 0 요구사항 확인·Gate 1 계획 승인은 3지선다(1.진행 / 2.수정 / 3.중단(산출물 보존)).
  답하기 전 다음 단계로 넘어가지 않음.

### 산출물 점수 (`selfcheck.py --score` → `dev-agent-team/SCORE.json`)
- 축은 test·rule·trace·doc·size 각 0~100, 기준 95.
- **아무것도 막지 않는다** — 막는 것은 `--gate` 다. 정하는 것은 재시도 여부뿐이다: pass / retry / escalate.
- escalate 는 **직전이 이미 retry·escalate 였을 때만** 난다 — 새 결함을 처음 발견한 것과
  고쳐도 안 낫는 것을 구분해야 한다(아니면 결함이 보일 때마다 곧바로 Owner 에게 올라간다).
- size 는 근사치라 **재시도를 강제하지 않는 권고 축**이다(`--gate` 가 안 막는 것과 같은 이유).
  최저축은 판정 축에서만 고른다.
- test 축은 FULL 실행 기록이 없으면 상한 75라 테스트를 실제로 돌리지 않으면 기준에 닿을 수 없다.
- 진전 판정은 최저축이 아니라 **축 합계**로 본다 — 최저가 아닌 축을 고쳐도 개선이 보이게.
- doc 축은 완료 단계의 R번호가 README 에 있는지 보므로 **documenter 가 단계마다 돌아야 채워진다**
  (PR 시점, `--score` 앞. README 는 .md 라 `.last-full-test` 를 무효화하지 않는다).
- trace 와 doc 은 같은 창(현재 단계 포함)으로 채점한다.
- 추세는 `SCORE.json` 의 history 에 누적한다(TEST_LOG 는 7열 그대로).

### 회고를 언제 도는가 (`selfcheck.py --retro-check`, large 전용)
- **단계마다 도는 것은 기계 판정이고, LLM 회고는 걸렸을 때만 돈다.** 매 단계 lead 를 부르면
  대부분 "없음" 이 나온다 — 역할 문서 자신이 신호 없으면 제안하지 말라고 적어 두었다.
- **판정을 lead 에게 맡기지 않는다.** 신호의 원인 중 하나가 lead 자신의 결정(방향·단계
  초점)이라 그 경우 lead 가 가장 못 본다. 판정까지 맡기면 **사각지대가 트리거를 먹는다.**
  회고가 돌면 `critic` 이 "원인이 방향·초점 선정인가"(CAUSE)를 따로 판정한다 — 자기 결정은
  자기가 판정하지 않는다.
- 문턱: **재시도 ≥ 3** 또는 **리뷰지적 2단계 연속 증가**. 상수는 `selfcheck.py` 상단
  (`RETRO_RETRY`·`RETRO_RISES`).
- **절대값으로 걸지 마라.** "리뷰지적 3건 이상" 으로 걸었더니 실제 프로젝트 8단계 중
  8단계에서 걸렸다 — 그 프로젝트는 단계당 리뷰지적 9~41건이 정상이다. 회고가 찾는 것은
  "숫자가 크다" 가 아니라 **얼마나 헤맸나** 다.
- **파일 수는 문턱이 아니다.** 실측에서 가장 나빴던 단계(재시도 5회·리뷰지적 41건·절차개선
  10건)가 제품코드 **3개**로 가장 작았다. 넓은 변경이 순조로울 수 있고 좁은 변경이 가장 많이
  헤맬 수 있다. 파일 수는 회고가 돌 때 **맥락으로만** 준다.
- 재시도·리뷰지적 칸이 비어 추세를 못 재면 **YES** 다. 기록이 없는 것을 "문제 없음" 으로
  바꾸지 않는다(원칙 1). 실제 프로젝트 110행 중 102행이 `-` 였다 — 7열 도입 전 단계들이다.
- 17b 최종 회고는 조건 없이 돈다(1회라 싸다). 거기서 **채택된 P-번호가 실제로 그 신호를
  줄였는지**도 본다 — 효과 없으면 폐기 제안. 개선을 쌓기만 하지 않는다.

### 누적 문서를 역할에 줄 때 (`--ledger` · `--process-active` · `--direction-head`)
- **분할 축은 "활성 / 아카이브" 하나다.** 브랜치별로 나누지 않는다 — 단계 브랜치는 main 에
  합쳐져 사라지고, "상태가 전부 파일에 있다"는 전제(무손실 모델 전환)가 깨진다.
  모듈·파일 단위도 축이 못 된다 — 결정은 대개 교차 관심사다.
- **주입에는 줄 예산이 있다**(`LEDGER_BUDGET`, 기본 400). 제목을 전부 주면 결정이 늘수록
  주입도 늘어 **O(n)** 이 된다 — 실측에서 634줄 중 337줄(53%)이 이미 제목이었다. 예산 안에서
  최근 본문부터 채우고, 남는 예산으로 제목을 채우고, 넘치면 **"그 이전 N건이 있다"는 한 줄로
  접는다.** 접어도 있다는 사실은 숨기지 않는다. 절 하나가 예산보다 크면 잘라서 준다 —
  안 자르면 상한이 상한이 아니다(실측에 1447줄짜리 결정이 있었다).
- **파일을 줄이는 것은 `--ledger-archive`** 다. 오래된 절을 `<문서>_ARCHIVE.md` 로 **옮기고**
  원본에 포인터 한 줄을 남긴다. 멱등이고, 단계 번호를 못 읽으면 옮기지 않는다.
- **순서가 있다: 승격 먼저, 아카이브 나중.** 오래됐다고 안 중요한 것이 아니다.
  "우리는 sqlite 를 쓴다" 같은 **계속 유효한 제약**은 로그에 두면 접히거나 묻힌다 —
  `PROJECT_RULES.md` 로 승격한다(언제나 통째로 전달된다). 판단 기준: **"이걸 모르고 작업하면
  팀이 틀리게 가는가?"** 승격 없이 내리면 유효한 제약이 사라진다(원칙 1).
  **접히는 것은 지나간 로그뿐이어야 한다.**
  실측: 5424줄 → 아카이브(keep 10) 뒤 파일 2534줄, 주입 122줄.
- **`DESIGN.md` 도 같은 규칙이다.** 명세인 줄 알았는데 실물은 **단계순 로그**였다 —
  24개 절 중 19개가 `단계10 … 단계199 … stage-202` 에 묶여 있다. 그래서 ledger 로 다룬다.
  다만 **고정으로 남길 곳이 다르다**: 디자인 규칙(토큰 체계·용어·컴포넌트 규약)은
  `PROJECT_RULES.md`(모든 역할에 감)가 아니라 **`DESIGN.md` 머리말**(첫 `##` 앞)에 둔다.
  머리말은 접히지도 아카이브되지도 않고 designer 호출에 언제나 통째로 간다.
- **`## [규칙] …` 절은 고정이다** — 단계 번호가 붙어 있어도 **아카이브되지 않고 주입에서도
  접히지 않는다.** "승격 먼저, 아카이브 나중" 은 절차 문장이라 지켜지지 않으므로(이 저장소에서
  P-규칙 통합이 76개 중 2번뿐이었다) 구조로 막는다. 판정은 **쓰는 사람이 단 표시**로 한다 —
  자유 텍스트에서 "전역"·"규칙" 을 찾아 추측하지 않는다(원칙 2).
  실측 근거: `§121 폰트 크기 토큰 체계(AppFontSize, 전역 타이포 정리)` 가 단계121 절에
  묶여 있었다. 전역 타이포 규칙인데 그 단계가 아카이브되면 다음 designer 가 못 본다.
  `--ledger-archive` 는 옮긴 절 제목을 보여 주어 섞여 든 규칙을 되돌릴 수 있게 한다.
- **머리말은 모든 ledger 에서 고정이다.** 그래서 머리말이 예산의 40%를 넘으면 알린다.
- **단계 번호가 없는 절은 아카이브되지 않는다**(추측하지 않는다). 실측에서 DECISIONS 43개·
  DESIGN 7개가 그랬다 — 영영 쌓인다. `--ledger-stats` 가 센다.
- **ledger 라고 다 절이 짧아야 하는 건 아니다**(`SECTION_TERSE`). 결정·개정·방향은 한 절이
  한 건이라 길면 조사가 섞인 것이지만, DESIGN 의 한 절은 화면 하나라 500줄이 정상이다.
  전부에 같은 잣대를 대면 또 늘 울린다.
- 크기는 `--ledger-stats` 로 본다. 실측(단계 202 시점): DECISIONS 5424 · DESIGN 4880 ·
  PROCESS 1671 · BACKLOG 891 · DIRECTION 481줄.
- **완료된 백로그는 `BACKLOG_DONE.md` 로 옮긴다**(12b-1). 지우는 게 아니라 옮기는 것이다.
  BACKLOG 는 planner·coder·designer·lead 가 매 단계 읽는다. 이 관례는 실제 프로젝트 팀이
  **하네스에 없는데도 스스로 만들어 쓰고 있었다** — 필요가 실재한다는 증거라 정식화했다.
  GitHub 이슈(45건 참조)와 `evidence/` 도 같은 경우다. 팀이 스스로 만든 관례는 **결함이
  아니라 요구사항**이다 — 하네스에 없는 것을 세 번 발견했으면 하네스가 모자란 것이다.

### 결정 기록과 백로그를 작게 유지하는 법
- **항목 수가 아니라 한 항목의 크기가 문제다.** 실측: DECISIONS 208건 5421줄인데 중앙값은
  7줄이고, **41줄 넘는 26건(12%)이 전체의 63%**를 차지했다. 한 건이 1447줄이었고 그중 결정은
  앞 30줄, 나머지는 조사 기록이었다.
- **코드를 읽어 알 수 있는 것은 적지 않는다.** `payment_screen.dart:431` 같은 위치 증거는
  적는 순간부터 낡아 거짓말을 한다. 꼭 가리켜야 하면 커밋 해시로 가리킨다.
  적어야 하는 것은 코드가 절대 말해 주지 않는 것 — 무엇을 골랐나, 무엇을 왜 버렸나,
  되돌리는 데 무엇이 드나, 코드에 없는 외부 제약.
- 조사는 `dev-agent-team/evidence/` 로 빼고 파일 이름만 남긴다. 단 **조사를 못 읽어도
  결정은 온전해야 한다** — 조사가 사라져 곤란해지는 내용이면 그건 조사가 아니라 결정이다(원칙 1).
- **개발 상태를 GitHub 이슈로 추적하지 않는다.** ① 상태가 전부 파일에 있어야 small↔large
  무손실 전환이 성립한다 ② small 프로파일에는 remote 자체가 없다 ③ **만드는 규칙만 있고
  닫는 규칙이 없으면 샌다** — 예전엔 절차가 `gh issue create` 를 시키면서 닫으라는 말은
  어디에도 없었다(실측 프로젝트: 이슈를 참조한 커밋 216개 vs 닫는다고 적은 커밋 4개).
  프로젝트가 이미 이슈를 쓰면 `조사: #번호` 로 적어도 되지만 **하네스는 그 이슈를 만들지도
  닫지도 추적하지도 않는다.** 여닫는 것은 프로젝트 몫이다.
  (main 합류 지점의 push·PR 은 상태 추적이 아니라 **코드 전달**이라 remote 조건부로 그대로 둔다.)
- **백로그는 컬럼을 늘리지 않는다.** 단계를 하나씩 도므로 WIP 는 이미 1이고, todo/done 은
  `- [ ]` 와 `BACKLOG_DONE.md` 로 이미 나뉘어 있다. 모자란 것은 컬럼이 아니라 **진행 표시
  (`- [~] · 진행:stageN`)와 계측**이었다.
- **쌓이는 것은 목록이 부족해서가 아니라 버리는 결정을 아무도 안 해서다**(열린 항목 279개 중
  139개가 20단계 넘게 묵음). 그루밍을 7-0에 묶어 두면 관심이 단계 초점으로 가서 안 돈다 —
  **7-0b 백로그 정리**를 조건부 별도 단계로 뒀다. 폐기는 삭제가 아니라 `BACKLOG_DONE.md` 로
  **이동**이고, 사유는 넷 중 하나여야 한다(이미 해결됨/요구사항 변경/흡수됨/재현 안 됨).
  출처가 Owner 인 항목은 팀이 스스로 폐기하지 않는다(C등급).
- `--ledger-stats` 는 **문서 종류마다 다른 잣대**를 댄다. ledger(결정·개정·방향)는 절이
  크면 조사가 섞인 것, list(백로그)는 길어도 정상, spec(설계·요구사항)은 요약이 아니라
  분할 대상. 전부에 같은 경고를 울리면 늘 울리고, 늘 울리는 경보는 무시된다.
- **보관과 주입은 다른 문제다.** `PROCESS.md`·`DIRECTION.md` 는 이력이라 append-only 이고
  **절대 자르지 않는다.** 대신 역할 호출에는 전문이 아니라 파생본만 준다.
- 안 그러면 프롬프트가 계속 무거워진다. 실측: P-규칙 76개 1558줄, 그중 `대상: 전체` 가
  1062줄이라 **coder 를 한 번 부를 때마다 1200줄 넘게** 붙었다. DIRECTION 은 481줄이었다.
- **줄이는 방법은 삭제가 아니라 통합이다.** 새 P-번호가 옛 것들을 "대체한다"고 적으면
  원문은 파일에 남고 주입에서만 빠진다 — 이력 100% 보존. 실측 프로젝트에서 폐기·대체가
  76개 중 **2개**뿐이었다. 메커니즘은 있었는데 안 쓰인 것이 원인이다.
- `--process-stats` 가 개수·줄수·`전체` 비중·역할별 주입량을 센다. 권고(300줄)를 넘으면
  **통합을 요구**한다 — 막지는 않는다(점수와 같은 원칙).
- `IMPROVE` 의 `대상: 전체` 는 되도록 쓰지 않는다. 모든 호출에 붙는다.
- **폐지한 역할은 `ROLES_ALL` 에 남겨 둔다.** 빼면 옛 설치본에서 영영 안 치워진다.
  치우기는 에이전트 블록 **밖**에서 세 경로를 모두 본다 — 안 그러면 지금 설치하는
  오버레이만 치워서, 예전에 codex 로 깔았다 뺀 `.agents/skills/<role>` 이 남는다.

### 하네스를 올린 뒤 기존 내용 (`selfcheck.py --migrate-check`)
- **새 규약은 앞으로 쓸 것에만 적용된다.** 이미 쓴 수백 건은 그대로다 — 규약이 안 맞으면
  도구가 덜 먹는다(단계 번호가 없으면 아카이브가 안 되고, `[규칙]` 이 없으면 지켜야 할 것이
  로그와 함께 내려간다). 그 격차를 `--migrate-check` 가 센다.
- **아무것도 자동으로 고치지 않는다.** Owner 의 글을 설치기가 고쳐 쓰는 것은 이 저장소가
  크게 데인 길이다(재설치 두 번에 157줄짜리 헌법이 사라졌다). 무엇을 옮길지는 사람이 정한다.
- `init.sh` 가 설치 끝에 어긋난 종수만 알린다(갓 설치한 빈 프로젝트에서는 안 뜬다).
- 실측(v1.65.0 시점): 11종 — 단계 번호 없는 절(DECISIONS 43·DIRECTION 31·DESIGN 7),
  고정 절 0개, 40줄 넘는 절 26개, PROCESS 주입 1305줄, 완료 미이관 5건, 묵은 항목 139건.
- 문서 종류마다 잣대가 다르다: **PROCESS 는 규칙 집합이라 단계 번호를 요구하지 않는다**
  (P-번호로 산다. 아카이브 대상도 아니고 줄이는 방법은 통합뿐이다).
- 파서는 **코드블록 안의 `##` 를 절로 세지 않는다** — 템플릿의 형식 예시가 유령 절이 됐다.

### 컨텍스트 총량 (역할 하나를 부를 때, 실측)
- 바탕 = `AGENTS.md` + `PROJECT_RULES.md`. 여기에 역할 본문·PROCESS 개정·역할별 문서가 붙는다.
- v1.58→v1.64 로 줄어든 폭: lead 8859→2526, critic 7797→1566, designer 6744→1440,
  checker·reviewer·security 1869→1183.
- **남은 병목은 도구로 못 줄인다.** PROCESS 가 모든 호출에 988줄(coder 1247), BACKLOG 가
  915줄이다. PROCESS 에 예산을 걸 수 없는 이유: 로그는 접혀도 이력이 안 보일 뿐이지만
  **규칙을 조용히 빼면 그 규칙이 안 지켜진다**(원칙 1). 원천에서 통합해야 한다.
  BACKLOG 도 7-0b 폐기가 돌아야 준다. 둘 다 운영이지 도구가 아니다.

### PROCESS 를 줄이는 법 (`selfcheck.py --process-check`)
- **주입 예산을 걸 수 없다.** 로그는 접혀도 이력이 안 보일 뿐이지만 **운영 규칙을 조용히
  빼면 그 규칙이 안 지켜진다**(원칙 1). 원천에서 줄이는 수밖에 없다.
- 그런데 실측 프로젝트에서 규칙이 76개까지 자라는 동안 통합·폐기는 **2번**뿐이었다.
  이유: 통합이 "또 하나의 IMPROVE" 라서 새 규칙 추가와 경쟁했고, 트리거도 목표도 없었다.
- 그래서 셋을 둔다. ① 기계 트리거(가장 무거운 역할의 주입량) ② **순증 금지** — 권고를 넘은
  상태에서 새 P-번호를 넣으려면 **최소 하나를 대체**해야 한다(7-0c). 규칙을 못 만들게 막는
  것이 아니라 값을 치르게 하는 것이다(WIP 제한과 같은 원리) ③ **좁히기 후보를 짚는다** —
  `대상: 전체` 인데 본문에 역할이 하나만 나오는 블록. 전체는 아홉 역할에 전부 붙으므로
  하나만 좁혀도 크게 준다. 역할이 여럿 나오면 후보로 올리지 않는다(추측하지 않는다).
- 실측: 살아 있는 규칙 78개 · coder 1305줄 · **좁힐 수 있는 것 10개 270줄**.

### 권한과 그 밖의 원칙
- deny/ask 목록 — `git push` 전체와 `gh pr` 은 **ask**(Owner 승인 후 에이전트가 실행).
  브랜치 생성은 도구 allow 로 두고 Gate 1 계획 승인이 일괄 승인을 겸한다(절차 필수라 도구
  ask 면 headless 에서 멈춘다). 계획에 없는 브랜치는 C등급. 평가 순서는 deny→ask→allow.
- append-only 테스트 원칙.
- 로그 형식 — `[HH:MM:SS] [LEVEL] [모듈] 동작 | key=value`, logs/app.log + 표준출력,
  언어 무관(logging-rule이 정본).
- 역할 경계 — 5역할 공통 + designer(UI 단계 공통) + large 전용 lead·reviewer·critic·security.
- **Read 를 가진 역할은 Grep 도 갖는다.** Grep 은 Read 이상의 권한을 주지 않는다 — 읽을 수
  있는 것을 찾을 수 있게 할 뿐이다. 빼 봐야 권한이 줄지 않고 둘 중 하나가 된다: 역할이 제
  일을 못 하거나(`tester` 는 "기존 테스트를 수정하지 않는다" 를 지켜야 하는데 무엇이 기존인지
  **찾을 수단이 없었다**. `designer` 도 같았다), **더 큰 권한으로 우회한다**
  (`coder`·`checker`·`documenter` 는 Grep 없이 Bash 를 가져서 `bash grep` 을 썼다 —
  작은 도구를 막고 큰 도구를 열어 둔 꼴이다).
  게다가 이 제한은 **Claude 에만** 걸렸다 — opencode 템플릿은 write/edit/bash 만 적어
  read·grep 을 제한하지 않고, codex 역할에는 도구 제한이 없다. 같은 역할이 에이전트마다
  다르게 동작하면 "산출물의 비종속성" 이 깨진다. `verify_parity.py` 가 구조로 고정한다.
- 단일 작성자 원칙.

## 절차를 고칠 때 (`tests/test_procedure.py`)

절차에 단계를 **끼워 넣으면 전이를 같이 고쳐야 한다.** 안 고치면 그 단계는 정의만 되고
아무도 안 보내는 **고아**가 된다 — 실제로 둘이 그랬다. `4-0`(lead 방향 설정)은 Gate 0 이
`4번` 으로 보내서, `12b-1`(완료 백로그 아카이브 이관)은 12번이 `12c로` 뛰어서 건너뛰어졌다.
**12b-1 이 막으려던 것이 바로 "백로그가 쌓이기만 하는 것"** 이라, 고아가 된 순간 그 문제가
조용히 계속된다.

`test_procedure.py` 가 렌더된 절차를 기계로 훑는다 — selfcheck 플래그가 실재하는지,
부르는 역할이 설치되는지(그 반대도), 가리키는 단계 번호가 있는지, 고아 단계가 없는지.
`run_all.sh` 에 들어 있다.

**점프는 두 종류다.** "…없으면 7번으로 간다"(조건부)는 다음 단계를 건너뛰지 않고,
"12b-1로."(종료)만 건너뛴다. 줄 단위로 조건 표지를 보고 가른다 — 안 가르면 멀쩡한 단계가
고아로 찍히고, **오탐이 나는 검사는 곧 무시된다.**

**한국어에서 파이썬 `\b` 는 경계를 안 만든다**(한글이 `\w` 다). `\bcritic\b` 가 `critic을` 에
안 맞는다. 이 감사를 짜면서 세 번 헛돌았다 — 역할 이름·단계 번호를 셀 때는
`(?<![A-Za-z])…(?![A-Za-z])` 로 판정한다.

## 검사를 쓸 때의 원칙 (이 저장소에서 반복된 사고)

가드·게이트·검증기를 **새로 넣거나 고칠 때 이 셋을 먼저 통과시킨다.** 같은 유형의 결함을
이 저장소에서 다섯 번 고쳤다 — 매번 다른 코드였지만 원인은 하나였다.

1. **못 찾았을 때 어느 쪽으로 기우는가**를 먼저 정한다. 안전장치는 fail-closed 다.
   "읽지 못했다"·"판정할 수 없다"를 **통과로 바꾸지 마라**. 못 읽은 것을 "깨끗하다"고
   보고하는 것이 이 저장소가 저지를 수 있는 가장 나쁜 실패다.
   — 예: `protect_tests.sh` 는 파이썬이 없으면 막는다. `selfcheck --score` 는 PLAN 을
   못 읽으면 만점이 아니라 escalate 다. 게이트는 가드 파일이 없으면 막는다.

2. **자유 텍스트에서 토큰을 찾아 판정하지 마라.** Owner 와 에이전트가 쓰는 산문에는
   그 토큰이 들어간다. 판정은 **구조**로 한다 — 헤더 줄, 칸 위치, 마지막 줄, 파일 목록.
   — 실제로 샌 것들: TEST_LOG 마이그레이션이 본문의 `재시도` 에(101행이 영영 5열로 남음),
   로그 요약이 설명의 `NEW_FAIL` 에(전부 PASS 인데 14개가 FAIL), 설치 검증이 PNG 안의
   `{{` 에(멀쩡한 설치를 "쓰지 말라"고 함), **C등급 정지가 질문 본문의 예시 `답: 2` 에**
   (질문을 쓰자마자 정지가 풀림).

3. **구분자가 든 데이터를 가운데부터 쪼개지 마라.** 표의 자유 서술 칸에는 `|` 가 들어간다.
   앞에서 N칸·뒤에서 M칸을 세고 나머지를 통째로 두는 쪽이 안전하다.

넣은 검사는 **결함을 주입해 실제로 잡히는지 확인**한다. 안 잡히는 검사는 장식이고,
장식은 있는 것보다 나쁘다 — 검사가 돈다고 믿게 만든다.

## 확장점 — 프로젝트 규칙은 하니스 파일에 넣지 않는다

업그레이드는 `dev-agent-team/hooks/*.sh` 와 `dev-agent-team/selfcheck.py` 를 **무조건
덮는다**(옛 강제 장치에는 구멍이 있을 수 있으므로 그게 맞다). 그래서 프로젝트가 거기에
직접 규칙을 넣으면 업그레이드마다 사라진다 — 한 사용처에서 1.51→1.58, 1.58→1.66 두 번
사라졌고, **두 번째에는 그것을 감시하려고 넣은 검사까지 같이** 지워졌다. 탐지기가 탐지
대상과 함께 사라지면 게이트는 조용히 `[guards] OK` 를 찍는다.

확장점이 없으면 사용처의 합리적 반응이 **"업그레이드를 안 하는 것"** 이 되고, 그러면 새
기능이 영영 전달되지 않는다. `/etc/profile ↔ ~/.bashrc`·`nginx conf.d/`·`git core.hooksPath`
와 같은 자리다.

- `dev-agent-team/guards/project.sh` — `protect_tests.sh` 가 자기 판정을 끝낸 뒤 source 한다.
  `$HARNESS_CANDIDATES`(개행 구분 경로)를 받고 `exit 2` 로 막는다.
- `dev-agent-team/guards/project_checks.py` — `--gate` 가 자기 축을 다 돈 뒤 `run(ctx)` 를
  부른다. `[{"name","ok","message","blocking"}]` 를 돌려주면 게이트 축으로 합쳐진다.
- **둘 다 없으면 조용히 건너뛰고, 있는데 터지면 막는다**(fail-closed). 못 돌린 확장을
  "통과" 로 바꾸지 않는다(원칙 1).
- **확장은 조일 수만 있고 풀 수는 없다.** 훅이 차단을 정하면 그 자리에서 `exit 2` 하므로
  확장은 불리지도 않는다. 의도한 방향이다 — 안전장치의 확장점이 차단을 풀 수 있으면
  확장점이 곧 우회로가 된다. **푸는 경로는 `TEST_UNFREEZE.md`**(역시 프로젝트 소유,
  업그레이드가 안 덮는다)이고, 그것으로도 부족하면 판정 규칙이 좁은 것이니 상류에 올린다.
- 설치기는 이 폴더를 **만들기만 하고 덮지 않는다**. README 만 install-if-missing 이다.

### 강제 장치도 매니페스트로 관리한다
- 예전엔 매니페스트에 `AGENTS.md`·`CLAUDE.md` 두 줄뿐이라, 정작 갈아엎히는 `hooks/*.sh` 와
  `selfcheck.py` 가 **관리 목록 밖**이었다. 사용처는 무엇을 잃었는지 도구로 알 수 없어
  사람이 `git status` 를 눈으로 봐야 했다(`--migrate-check` 는 문서 규약을 보는 것이라
  이 사고를 못 잡는다).
- 이제 셋 다 해시를 기록한다. 프로젝트가 고친 흔적이 있으면 **덮되 `.orig` 로 남기고
  크게 알린다** — 무엇을 잃었는지 `diff` 로 볼 수 있고, guards/ 로 옮기라고 말해 준다.

## 생성된 프로젝트의 안전장치 (= templates/ 에서 무엇을 깨면 안 되는가)

- **「기존 테스트」의 판정축은 git 추적 여부다**(파일 존재가 아니다). 존재로 판정하던 때는
  에이전트가 **방금 만들어 아직 커밋도 안 한** 자기 테스트를 스스로 못 고쳤다 — 한 프로젝트에서
  여덟 번 재발했고, 그때마다 자기 산출물의 결함을 발견하고도 못 고친 채 넘어갔다(한 번은 실제
  구멍이 그대로 통과했다). 헌법 2번의 「기존」도 커밋된 것을 뜻한다 — 문언과 동작을 맞췄다.
  추적 안 됨→통과 / 추적됨→차단(단 `TEST_UNFREEZE.md` 에 「근거:」와 함께 적힌 경로는 통과)
  / **git 없음·판정 실패→차단**(fail-closed). 해제 목록을 못 읽어도 전면 동결이다.
  **경로 표기를 루트 기준으로 맞춰 비교한다** — 해제 목록은 사람이 써서 상대경로인데
  편집 도구는 보통 절대경로를 넘긴다(Claude Code 의 Edit 이 그렇다). 문자열로 비교하다가
  같은 파일의 표기 셋(절대·상대·`./상대`)이 갈려 **해제 목록이 통째로 안 먹었다.**
  보호 범위는 `tests?/` 아래 **모든 .py** — `conftest.py`(데이터 게이트)와
  `_contract.py`·`_synthetic.py`(계약·합성 헬퍼)가 조용히 바뀌면 "독립 검증"·"조용한 skip
  차단" 보장이 집행되지 않는다. 훅은 프로젝트 루트를 **자기 위치**로 안다(cwd 가 아니다).
- **인자는 전부 받는다.** `_parse_args` 가 `rest[0]` 만 돌려주던 때 `selfcheck.py A.py B.py`
  가 A.py 만 보고 "0건" 을 찍었다 — **검사했는데 깨끗한 것과 안 본 것이 같은 글자**였다.
  `[collect]` 는 merge 를 막는 결정적 축이라 더 무겁다. 두 번 고쳤다 두 번 되돌아온
  버그라 테스트로 못 박았다. 축 출력에 **실제로 본 파일 수**를 붙이고, 못 읽은 파일은
  「0건」에 섞지 않고 따로 말한다.
- **공유 가드 스크립트 2개**(`dev-agent-team/hooks/`): `block_on_owner_question.sh`
  (OWNER_QUESTION.md 의 **마지막** `답:` 줄에 숫자가 없으면 exit 2 차단 — 아무 `답:` 줄이나
  보면 질문 본문에 예시로 적힌 `답: 2` 한 줄이 정지를 풀어 버린다), `protect_tests.sh`
  (기존 테스트 파일 수정 시 exit 2 — 언어 무관: py/go/rs/js·ts/dart, `tests/`·`test/` **하위 폴더까지** 판정. 정규식은
  `protect_tests.sh` 와 `guard.js` 가 동일). exit 2 + stderr 규약 — 바꾸면 `verify_hooks.sh` 도 함께.
- **에이전트별 연결**: Claude=`.claude/settings.json` hooks가 `dev-agent-team/hooks/*.sh` 호출 +
  allow/ask/deny(`rm -rf`/`git reset --hard`/`git branch -D`/`python -c`/`node -e`/`curl`/`wget` 등 deny,
  force push(`--force`/`-f`/`--force-with-lease`)는 **ask**;
  일반 `git push`(작업 브랜치)·go/cargo/npm/node 테스트 실행은 allow. main 직접 push·force 금지는
  AGENTS.md 규칙 병행). Codex=
  `.codex/hooks.json` 이 같은 `dev-agent-team/hooks/*.sh` 호출(단 apply_patch·MCP 훅 불안정·Windows 미지원).
  opencode=`.opencode/plugins/guard.js` 가 동일 로직을 JS로 재현(`tool.execute.before` throw).
- **C등급 정지 흐름**: planner가 dev-agent-team/OWNER_QUESTION.md 작성 → 가드레일이 도구 사용 차단 →
  Owner가 "답: 번호" 기입 → 자동 해제. 이 3박자는 계약이다(강제 방식만 에이전트별로 다름).
- **세 경로 동기화**: 가드 로직을 바꾸면 `.sh` 2개와 `guard.js` 를 **함께** 고쳐야 한다.
  `verify_hooks.sh` 의 guard.js 항목 3개가 같은 입력 6케이스를 양쪽에 넣어 판정이 갈리는지
  기계적으로 대조한다(node 없으면 SKIP). 예전엔 전 항목이 `.sh` 만 봐서 `guard.js` 는
  육안 대조뿐이었다. 중첩(`tests/sub/`·`test/utils/`)과 dart 케이스도 그 안에 있다.

## 에이전트 역할 경계 (단일 작성자 원칙)

공유 상태 파일(dev-agent-team/PLAN.json, dev-agent-team/DECISIONS.md, dev-agent-team/TEST_LOG.md, dev-agent-team/OWNER_QUESTION.md, dev-agent-team/BACKLOG.md, dev-agent-team/SCORE.json, dev-agent-team/DIRECTION.md, dev-agent-team/PROCESS.md)은 **메인 세션만**
쓴다. subagent는 자기 산출물만 쓴다(planner=계획/질문, tester=tests/, coder=구현,
checker=pytest 실행·판정, documenter=제품 README/문서(단계마다 그 단계 R번호 + 17번 최종 정리), designer=dev-agent-team/DESIGN.md(UI 단계),
lead·reviewer·critic·security(large)=제안만 출력. dev-agent-team/는 읽기만).
절차 전체는 `templates/skills/team-dev/SKILL.md.tmpl` 가 정본이다.

## 알려진 제약

- 가드레일 강제력은 에이전트별로 다르다(Codex 파일편집 훅 불안정·Windows 미지원, opencode는
  bun/node 필요). 강제가 불완전할 수 있어 AGENTS.md 규칙을 병행하고 컨테이너 실행을 권장한다.
- **Codex 는 역할 도구 격리가 아예 없다.** `.agents/skills/<role>/SKILL.md` 에 name·description
  만 적는다 — 도구 제한 필드를 쓰지 않는다. 그래서 읽기만 해야 하는 역할(reviewer·lead·
  critic·security)이 Codex 에서는 파일을 쓸 수 있고, 막는 것은 역할 프롬프트 문장뿐이다.
  README 가 오래 "정밀하지 않다" 고 적어 두었는데 그건 "있는데 덜 정확하다" 로 읽힌다 —
  **없는 것을 있는 것처럼 말하지 않는다**(원칙 1과 같은 자리). claude↔opencode 동등성은
  `verify_parity.py` 가 기계로 지키지만, codex 는 지킬 대상 자체가 없다.
- `AGENTS.md` 는 이제 **심볼릭 링크가 아니라 렌더된 실파일**(공통 헌법)이다. Claude는
  `CLAUDE.md` 가 `@AGENTS.md` 로 import 한다.
- Codex `.codex` 설정은 trusted 프로젝트에서만 적용된다(설치 후 안내 참조).
- **파이썬은 제품 언어와 무관하게 필수다.** 가드 훅이 훅 입력(JSON)에서 경로를 뽑을 때와
  `selfcheck.py`(게이트·점수)에 쓴다. 없으면 `protect_tests.sh` 가 fail-closed 라 **파일
  편집이 전부 막힌다**. 자바·C# 팀이 특히 걸린다 — `init.sh`/`init.ps1` 이 설치 끝에 경고한다.
- **selfcheck 가 아는 제품 언어는 python/go/rust/node/dart 뿐이다.** 자바 프로젝트는 `[lang] 감지된
  제품 언어 없음` 이 되어 collect·print·trace·size·security 가 전부 건너뛰어지고 `[gate] PASS`
  가 무조건 난다 — 게이트가 사실상 비어 있다. 테스트 실행·판정은 checker 가 제품 언어 러너로
  하므로 개발 자체는 돌지만, 결정적 검사는 걸리지 않는다.
- pwsh가 없는 환경에선 `init.ps1` 파리티를 **런타임** 검증할 수 없다. `tests/verify_parity.py`
  가 매핑·목록·렌더 결과를 정적으로 대조하지만, 그건 PowerShell 의미론을 파이썬으로 흉내 낸
  것이라 시뮬레이터가 틀리면 같이 틀린다. 실제 Windows 실행이 파리티 확인의 상한이다.
