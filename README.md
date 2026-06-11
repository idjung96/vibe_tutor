# team-dev-harness

AI 에이전트 개발팀 하니스. 요구사항을 입력하면 planner / tester / coder /
checker 4개 에이전트가 Stage-Gate 방식으로 단계별 자동 개발을 수행한다.
Owner(사용자)는 시작 승인, C등급 질문 답변, 최종 인수 — 3개 지점에만 개입한다.

- 단일 소스(templates/) + 설치 시점 프로파일 렌더링 구조
- 소형 모델(온프레미스 LLM)과 대형 모델(Claude) 모두 지원
- 컴퓨터 초보자의 바이브코딩을 전제로 설계

## 설치

macOS / Linux:
```bash
git clone <이 저장소>
cd team-dev-harness
./init.sh ~/projects/my-app                   # 프로파일 자동 판별
./init.sh --profile small ~/projects/my-app   # 명시 지정
```

Windows (PowerShell):
```powershell
git clone <이 저장소>
cd team-dev-harness
.\init.ps1 -Target C:\projects\my-app                  # 프로파일 자동 판별
.\init.ps1 -Profile small -Target C:\projects\my-app   # 명시 지정
```
Windows 요구사항: PowerShell 5.1 이상, Git for Windows(Git Bash 포함 —
Claude Code Windows 버전의 요구사항이기도 하다). 두 설치 스크립트의
렌더링 결과는 동일하다(자동 비교 검증됨).

프로파일 자동 판별 기준: `ANTHROPIC_BASE_URL`이 사내망(내부 IP, kims,
litellm, localhost)을 가리키면 **small**, 비어 있거나 외부면 **large**.
판별 불가 시 "사내 AI인가요, Claude인가요?"를 묻는다.

설치가 끝나면 프로젝트 폴더에서 Claude Code(또는 사내 코딩 에이전트)를
열고 `개발 시작` 이라고 입력한다. 초보자 안내는 생성된 `OWNER_GUIDE.md` 참조.

## 저장소 구조

```
HARNESS_VERSION          # 버전 (호환성 계약 변경 시 올림)
init.sh                  # 설치 (macOS/Linux): 판별 → 렌더링 → hook 검증
init.ps1                 # 설치 (Windows): 동일 로직의 PowerShell 포팅
profiles/
  small.conf             # 온프레미스 LLM용 파라미터
  large.conf             # 외부 대형 모델용 파라미터
templates/
  CLAUDE.md.tmpl         # 헌법 (= AGENTS.md 링크로도 설치됨)
  settings.json.tmpl     # 권한 allow/deny + hook 등록
  agents/                # planner, tester, coder, checker
  skills/                # team-dev(절차), logging-rule, lib-research
  hooks/                 # Owner 질문 정지, 테스트 보호
  common/logger.py       # 공통 로거 (고정 포맷)
  docs/                  # OWNER_GUIDE, DEBUG_GUIDE
  project/               # DECISIONS, TEST_LOG, libs INDEX 초기 파일
samples/sample-task-todo # 표본 과제 (모델 전환 테스트용)
tests/verify_hooks.sh    # hook 실동작 검증 (init.sh가 자동 실행)
```

## 프로파일 차이 (이 7가지만 다르다)

| 항목 | small | large |
|---|---|---|
| RETRY_LIMIT | 3 | 5 |
| MAX_CHECKER_CALLS | 10 | 15 |
| tester 추가 탐색 | 없음 (체크리스트 4종만) | "보이면 더 쓴다" |
| NOTES.md (단계 밖 발견) | 없음 | 있음 |
| coder 디버깅 절차 | 4단계 강제 | 로그 우선 1줄 |
| 영향 표 파일 수 산정 | 추정 | grep 실측 |
| 단계 시작 병렬 (tester ∥ lib-research) | 순차 | 병렬 |

## 호환성 계약 (프로파일과 무관하게 동일 — 변경 시 버전 올림)

1. 파일 형식: PLAN.json 스키마, DECISIONS.md / TEST_LOG.md /
   OWNER_QUESTION.md / docs/libs/ 형식, 커밋 메시지, 브랜치 이름
2. C등급 목록(요구사항 변경, 삭제, 비용, 외부 배포, 보안, GPL)과
   정지 메커니즘 (OWNER_QUESTION.md → hook 차단, "답: 번호"로 해제)
3. deny 목록 (push, rm -rf, hard reset, python -c 우회 포함)
4. append-only 테스트 원칙 (hook으로 강제)
5. 로그 형식 `[LEVEL] [모듈] 메시지 | key=value`
6. 에이전트 4종 구조와 역할 경계
7. 공유 상태 파일은 메인 세션만 쓴다 (단일 작성자 원칙)

이 계약 덕분에 **모델 전환 인수인계**가 가능하다: small로 진행하던
프로젝트 폴더를 large 사용자가 이어받아도(역방향도) 상태가 전부
파일에 있으므로 무손실로 계속된다.

## 배포 전 검증 (관리자용)

1. `./init.sh --profile small /tmp/t1` 과 `--profile large /tmp/t2` 실행,
   hook 검증 6항목 전부 PASS 확인 (init.sh가 자동 수행).
2. samples/sample-task-todo 로 양 프로파일 실주행:
   - small: C등급 과잉 에스컬레이션, JSON 형식 파손율 관찰
   - large: 과소 에스컬레이션(애매한 요구를 스스로 해석), 범위 초과 관찰
3. 모델 전환 테스트: small로 3단계 진행 → 폴더를 large 환경으로 이동 →
   4단계부터 이어서 진행 → TEST_LOG.md 누적이 끊기지 않는지 확인.
4. 파일럿: 소형 사용자 2명 + Claude Code 사용자 2명.

## 알려진 제약

- hook 출력 규약(exit 2 / stderr)은 Claude Code 기준이다. 다른 코딩
  에이전트는 hook을 지원하지 않을 수 있다 — 이 경우 안전장치는
  프롬프트 규칙만으로 동작하므로, 가능하면 컨테이너 안에서 실행하라.
- `Bash(python -c:*)` 차단은 우회 차단의 1차 방어일 뿐이다. 기관 배포
  시 devcontainer/Docker로 프로젝트 디렉토리만 마운트하는 것을 권장한다.
- AGENTS.md는 CLAUDE.md의 심볼릭 링크다. Windows에서 링크 권한이 없으면
  init.ps1이 자동으로 복사본으로 대체한다(개발자 모드를 켜면 링크 생성).
  복사본인 경우 CLAUDE.md 변경 후 init.ps1을 재실행해 동기화한다.
- Windows에서 hook 검증은 Git Bash를 사용한다. Git Bash가 없으면 검증을
  건너뛰며 경고를 출력한다 — Claude Code 사용 전 반드시 설치할 것.
