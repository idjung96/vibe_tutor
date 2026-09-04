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
./init.sh ~/projects/my-app                     # 자동 판별. 온프레미스→small이면 all에 codex가 있어 에러 → claude,opencode로

# hook 실동작 검증 (init.sh가 설치 끝에 자동 실행; 단독 실행도 가능)
./tests/verify_hooks.sh /tmp/t1       # 공통 dev-agent-team/hooks 기준 18항목 PASS여야 함

# Windows 동등물 (init.sh와 동일 렌더링 — pwsh 없으면 코드리뷰로 파리티 확인)
.\init.ps1 -Profile large -Agent all -Target C:\projects\my-app
```

변경 후 검증 루틴: large는 `--agent all`, small은 `--agent claude,opencode`(codex 불가)로 설치 → `verify_hooks.sh` 18/18 PASS →
생성 트리에 미렌더 `{{` 마커 없는지 → `opencode.json`/`.codex/*.json` JSON·`config.toml`
TOML·`guard.js` 문법 유효성 확인 → 단일 에이전트 설치 시 다른 에이전트 폴더가 안 생기는지.

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
   고쳐야 한다.

## 에이전트 오버레이 (어디에 무엇이 깔리나)

- **공통**: `AGENTS.md`(헌법), `dev-agent-team/`(+`dev-agent-team/hooks/` 가드 스크립트), `common/`, `tests/` `logs/`.
- **claude**: `CLAUDE.md`(@AGENTS.md), `.claude/settings.json`·`agents/`·`skills/`.
- **codex**: `.codex/config.toml`(large 전용이라 `model_reasoning_effort="high"` 무조건 포함)·`.codex/hooks.json`(→`dev-agent-team/hooks` 재사용), `.agents/skills/`.
  **codex는 large 프로파일 전용**이다 — small에서 codex가 요청되면(`all` 포함) init이 프로파일 확정 직후 에러로 중단한다(`init.sh`/`init.ps1` 양쪽 가드).
- **opencode**: `opencode.json`, `.opencode/agents/`·`.opencode/plugins/guard.js`,
  스킬은 `.agents/skills/`(호환 경로)로 보장.

스킬 6종(team-dev/logging-rule/lib-research/code-convention/test-design/ui-design)은 claude면 `.claude/skills/`,
codex/opencode면 `.agents/skills/` 로 렌더된다(`emit_skills`).

## 프로파일은 단 7가지만 다르다

`profiles/*.conf`(RETRY_LIMIT, MAX_CHECKER_CALLS)와 `.tmpl` 안의 `{{#IF_*}}` 블록으로만
차이를 만든다. 새 차이를 도입할 때도 이 두 경로만 쓴다 — 별도 분기 파일을 만들지 말 것.
차이 13종: RETRY_LIMIT, MAX_CHECKER_CALLS, tester 추가 탐색, coder 단계 밖 발견→BACKLOG 보고(large만),
coder 디버깅 절차, 영향 표 산정 방식, 단계 시작 병렬성, reviewer 역할(large 전용 코드·테스트 리뷰),
lead 역할(large 전용 팀장 방향·백로그 그루밍, DIRECTION.md; 회고·절차 자기개선 제안 IMPROVE),
critic 역할(large 전용 결정 심의·합의; 명확하면 자율, 모호·고위험은 Owner),
security 역할(large 전용 보안 점검), planner 요구사항 충돌·누락 점검(large만),
절차 자기개선(large 전용 lead 회고→Owner 승인→PROCESS.md 오버레이). (BACKLOG.md 파일 자체는 양 프로파일 공통.)

## 생성된 프로젝트의 디렉터리 규약

에이전트 작업/상태 파일은 모두 **`dev-agent-team/`** 아래에 둔다(REQUIREMENTS, PLAN.json/PLAN.md,
DECISIONS, TEST_LOG, OWNER_QUESTION, BACKLOG, DIRECTION(large), PROCESS(large), DESIGN(UI 단계), `dev-agent-team/libs/`, `dev-agent-team/answered/`, `dev-agent-team/guides/`).
**에이전트가 실행하는 코드·스크립트도 `dev-agent-team/` 안에 둔다** — 가드 훅(`dev-agent-team/hooks/*.sh`),
자가점검 도구(`dev-agent-team/selfcheck.py`). generic depth-1 폴더에 두면 제품 폴더와 헷갈리므로 금지.
`tests/` `logs/` `common/` 은 **제품 디렉터리**(만들고 있는 프로그램의 것 — pytest 표준 위치,
앱 런타임 로그, 제품 공통 코드 `common/logger.py`)라 이름이 겹쳐도 그대로 둔다. 경로를 옮기면 호환성
계약이 바뀌므로 `HARNESS_VERSION` 을 올린다(team/ 도입 v1.2.0 → `dev-agent-team/` 개명 v1.3.0 →
selfcheck를 `common/`에서 `dev-agent-team/`로 v1.9.0).

## 호환성 계약 — 변경 시 `HARNESS_VERSION` 을 올릴 것

프로파일과 무관하게 동일해야 하는 것들(파일 위치/형식: dev-agent-team/ 레이아웃, dev-agent-team/PLAN.json 스키마,
dev-agent-team/DECISIONS.md / dev-agent-team/TEST_LOG.md / dev-agent-team/OWNER_QUESTION.md 형식,
dev-agent-team/PROCESS.md 형식(P번호·append-only, large 전용), 커밋 메시지, 브랜치명 /
C등급 목록과 정지 메커니즘 / deny 목록 / append-only 테스트 원칙 / 로그 형식 /
역할 경계(5역할 공통 + designer(UI 단계 공통) + large 전용 lead·reviewer·critic·security) / 단일 작성자 원칙).
이 계약 덕에 small↔large **무손실 모델 전환 인수인계**가 성립한다(상태가 전부 파일에 있음).
계약을 바꾸면 README "호환성 계약" 절과 `HARNESS_VERSION` 을 함께 갱신한다.

## 생성된 프로젝트의 안전장치 (= templates/ 에서 무엇을 깨면 안 되는가)

- **공유 가드 스크립트 2개**(`dev-agent-team/hooks/`): `block_on_owner_question.sh`
  (dev-agent-team/OWNER_QUESTION.md에 `^답: 숫자`가 없으면 exit 2 차단), `protect_tests.sh`
  (기존 테스트 파일 수정 시 exit 2 — 언어 무관: py/go/rs/js·ts, `tests/` 밑 판정 정규식은
  `protect_tests.sh` 와 `guard.js` 가 동일). exit 2 + stderr 규약 — 바꾸면 `verify_hooks.sh` 도 함께.
- **에이전트별 연결**: Claude=`.claude/settings.json` hooks가 `dev-agent-team/hooks/*.sh` 호출 +
  allow/deny(force push(`--force`/`-f`)/`rm -rf`/`git reset --hard`/`python -c`/`node -e` 등 deny;
  일반 `git push`(작업 브랜치)·go/cargo/npm/node 테스트 실행은 allow. main 직접 push·force 금지는
  AGENTS.md 규칙 병행). Codex=
  `.codex/hooks.json` 이 같은 `dev-agent-team/hooks/*.sh` 호출(단 apply_patch·MCP 훅 불안정·Windows 미지원).
  opencode=`.opencode/plugins/guard.js` 가 동일 로직을 JS로 재현(`tool.execute.before` throw).
- **C등급 정지 흐름**: planner가 dev-agent-team/OWNER_QUESTION.md 작성 → 가드레일이 도구 사용 차단 →
  Owner가 "답: 번호" 기입 → 자동 해제. 이 3박자는 계약이다(강제 방식만 에이전트별로 다름).
- **세 경로 동기화**: 가드 로직을 바꾸면 `.sh` 2개와 `guard.js` 를 **함께** 고쳐야 동작이 일치한다.

## 에이전트 역할 경계 (단일 작성자 원칙)

공유 상태 파일(dev-agent-team/PLAN.json, dev-agent-team/DECISIONS.md, dev-agent-team/TEST_LOG.md, dev-agent-team/OWNER_QUESTION.md, dev-agent-team/BACKLOG.md, dev-agent-team/DIRECTION.md, dev-agent-team/PROCESS.md)은 **메인 세션만**
쓴다. subagent는 자기 산출물만 쓴다(planner=계획/질문, tester=tests/, coder=구현,
checker=pytest 실행·판정, documenter=제품 README/문서, designer=dev-agent-team/DESIGN.md(UI 단계),
lead·reviewer·critic·security(large)=제안만 출력. dev-agent-team/는 읽기만).
절차 전체는 `templates/skills/team-dev/SKILL.md.tmpl` 가 정본이다.

## 알려진 제약

- 가드레일 강제력은 에이전트별로 다르다(Codex 파일편집 훅 불안정·Windows 미지원, opencode는
  bun/node 필요). 강제가 불완전할 수 있어 AGENTS.md 규칙을 병행하고 컨테이너 실행을 권장한다.
- `AGENTS.md` 는 이제 **심볼릭 링크가 아니라 렌더된 실파일**(공통 헌법)이다. Claude는
  `CLAUDE.md` 가 `@AGENTS.md` 로 import 한다.
- Codex `.codex` 설정은 trusted 프로젝트에서만 적용된다(설치 후 안내 참조).
- pwsh가 없는 환경에선 `init.ps1` 파리티를 런타임 검증할 수 없다 — 코드리뷰로 확인한다.
