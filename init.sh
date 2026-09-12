#!/usr/bin/env bash
# team-dev-harness 설치 스크립트
# 사용법: ./init.sh [--profile small|large] [--agent claude|codex|opencode|all] [대상디렉토리]
#         ./init.sh --accept-constitution [대상디렉토리]
#           헌법 동결(AGENTS.md.new/CLAUDE.md.new 가 남은 상태)을 이 명령 하나로 푼다.
#           Owner 가 직접 넣은 줄은 dev-agent-team/PROJECT_RULES.md 로 옮기고, 새 헌법을
#           받아들인 뒤 그대로 설치를 계속해 manifest 까지 맞춘다.
# 프로파일 생략 시: 온프레미스(ANTHROPIC_BASE_URL/OPENAI_BASE_URL이 내부망)면 small, 그 외 large.
# 에이전트 생략 시: all (claude + codex + opencode).
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(cat "$SRC/HARNESS_VERSION")"

PROFILE=""; TARGET=""; AGENTS_SEL=""; ACCEPT_CONST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --agent)   AGENTS_SEL="$2"; shift 2 ;;
    --accept-constitution) ACCEPT_CONST=1; shift ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) TARGET="$1"; shift ;;
  esac
done
TARGET="${TARGET:-$(pwd)}"
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

if [ "$TARGET" = "$SRC" ]; then
  echo "오류: 하니스 저장소 안에는 설치할 수 없습니다. 프로젝트 폴더를 지정하세요."
  echo "예) ./init.sh ~/projects/my-app"
  exit 1
fi

# ── 0. 재설치라면 기존 구성을 따른다 ──────────────────────────
# 플래그를 생략한 재설치가 프로파일·에이전트를 새로 판별하면, small 로 깔아 둔 온프레미스
# 프로젝트가 조용히 large 로 바뀌고 codex 오버레이까지 깔린다(역할 6개 -> 11개, RETRY_LIMIT
# 3 -> 5). 업데이트하려던 사람에게는 사고다. 이미 깔린 것에서 읽어 온다.
# 명시한 플래그가 언제나 이긴다 — 프로파일을 바꾸는 것은 의도적인 행위여야 한다.
installed_profile() {
  for f in "$TARGET/.claude/agents/lead.md" "$TARGET/.agents/skills/lead/SKILL.md" \
           "$TARGET/.opencode/agents/lead.md"; do
    [ -f "$f" ] && { echo large; return; }
  done
  [ -f "$TARGET/AGENTS.md" ] && echo small
}
installed_agents() {
  out=""
  [ -f "$TARGET/.claude/settings.json" ] && out="$out,claude"
  [ -f "$TARGET/.codex/config.toml" ]    && out="$out,codex"
  [ -f "$TARGET/opencode.json" ]         && out="$out,opencode"
  printf '%s' "${out#,}"
}
if [ -f "$TARGET/AGENTS.md" ]; then
  if [ -z "$PROFILE" ]; then
    P_WAS=$(installed_profile)
    [ -n "$P_WAS" ] && { PROFILE="$P_WAS"; echo "재설치: 기존 프로파일 $PROFILE 을(를) 유지합니다(--profile 로 바꿀 수 있습니다)."; }
  fi
  if [ -z "$AGENTS_SEL" ]; then
    A_WAS=$(installed_agents)
    [ -n "$A_WAS" ] && { AGENTS_SEL="$A_WAS"; echo "재설치: 기존 에이전트 구성 $AGENTS_SEL 을(를) 유지합니다(--agent 로 바꿀 수 있습니다)."; }
  fi
fi

# ── 1. 에이전트 선택 ──────────────────────────────────────────
AGENTS_SEL="${AGENTS_SEL:-all}"
case "$AGENTS_SEL" in
  all) AGENTS="claude codex opencode" ;;
  *)   AGENTS="$(echo "$AGENTS_SEL" | tr ',' ' ')" ;;
esac
for a in $AGENTS; do
  case "$a" in claude|codex|opencode) ;; *) echo "알 수 없는 에이전트: $a (claude|codex|opencode|all)"; exit 1 ;; esac
done
has_agent() { case " $AGENTS " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

# ── 2. 프로파일 판별: 온프레미스면 small, 그 외 large ─────────
if [ -z "$PROFILE" ]; then
  BASE="${ANTHROPIC_BASE_URL:-}${OPENAI_BASE_URL:-}"
  if echo "$BASE" | grep -qiE '134\.75\.147\.|kims|litellm|localhost|127\.0\.0\.1|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.'; then
    PROFILE=small   # 사내/내부망 엔드포인트 = 온프레미스 LLM
  else
    PROFILE=large   # 비어 있거나 외부 = 외부 대형 모델
  fi
fi
case "$PROFILE" in small|large) ;; *) echo "프로파일은 small 또는 large 여야 합니다."; exit 1 ;; esac

# codex는 large 프로파일 전용(외부 대형 추론 모델). small에서 요청되면 차단한다.
if [ "$PROFILE" = small ] && has_agent codex; then
  echo "codex는 large 프로파일 전용입니다 (small 미지원)." >&2
  echo "small로 설치하려면 codex를 빼고 실행하세요: --agent claude,opencode" >&2
  exit 1
fi

# shellcheck source=/dev/null
. "$SRC/profiles/$PROFILE.conf"

# ── 3. 템플릿 렌더링 ──────────────────────────────────────────
# {{#IF_SMALL}}/{{#IF_LARGE}} 블록은 마커가 한 줄을 통째로 차지해야 한다.
render_stdout() {
  awk -v profile="$PROFILE" '
    $0=="{{#IF_SMALL}}" { mode=(profile=="small")?"keep":"skip"; next }
    $0=="{{#IF_LARGE}}" { mode=(profile=="large")?"keep":"skip"; next }
    $0=="{{/IF_SMALL}}" || $0=="{{/IF_LARGE}}" { mode=""; next }
    mode=="skip" { next }
    { print }
  ' "$1" \
  | sed -e "s|{{PROFILE_LABEL}}|$PROFILE_LABEL|g" \
        -e "s|{{RETRY_LIMIT}}|$RETRY_LIMIT|g" \
        -e "s|{{MAX_CHECKER_CALLS}}|$MAX_CHECKER_CALLS|g" \
        -e "s|{{HARNESS_VERSION}}|$VERSION|g"
}
render() {
  mkdir -p "$(dirname "$2")"
  render_stdout "$1" > "$2"
}

# ── conffile 방식 (dpkg 관행) ────────────────────────────────
# AGENTS.md·CLAUDE.md 는 Owner가 손댈 수 있는 문서다. 무조건 덮어쓰면 편집이 사라지고,
# 무조건 보존하면 헌법 갱신이 기존 프로젝트에 영원히 도달하지 않는다. 그래서
# "손대지 않았으면 갱신하고, 손댔으면 덮지 않고 알린다".
# 강제 장치(settings.json deny 목록·hooks·guard.js·역할·스킬)는 낡으면 안전 계약이
# 깨지므로 이 규칙을 쓰지 않고 지금처럼 무조건 덮어쓴다.
MANIFEST="$TARGET/dev-agent-team/.harness-manifest"
rm -f "$MANIFEST.tmp"   # 이전 실행이 남긴 찌꺼기에 덧붙지 않게

# CR 을 지우고 해시한다. Windows 에서 git 이 줄끝을 바꿔도(core.autocrlf=true) Owner 가
# 편집한 것으로 오인해 .new 를 남기지 않게 하려는 것이다. 대상은 AGENTS.md·CLAUDE.md
# 두 텍스트 문서뿐이라 CR 제거가 안전하다. LF 파일은 해시가 그대로라 기존 manifest 와 호환된다.
sha256_of() {
  [ -f "$1" ] || { echo ""; return; }
  if command -v sha256sum >/dev/null 2>&1; then
    tr -d '\r' < "$1" | sha256sum | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    tr -d '\r' < "$1" | shasum -a 256 | cut -d' ' -f1
  else
    echo ""   # 해시 도구가 없으면 비교를 포기하고 보수적으로 간다
  fi
}

manifest_get() { # $1=상대경로
  [ -f "$MANIFEST" ] || return 1
  awk -v k="$1" '$2==k { print $1; found=1 } END { exit !found }' "$MANIFEST"
}

ver_minor() { # 1.27.2 -> 127 처럼 비교 가능한 수로. 못 읽으면 빈 값.
  printf '%s' "$1" | awk -F. 'NF>=2 { printf "%d", $1*1000 + $2 }'
}
render_managed() { # $1=템플릿 $2=대상 $3=상대경로
  mkdir -p "$(dirname "$2")" "$(dirname "$MANIFEST")"
  TMP="$2.harness-tmp"
  render_stdout "$1" > "$TMP"
  NEWHASH=$(sha256_of "$TMP")

  if [ ! -f "$2" ]; then
    mv "$TMP" "$2"
  else
    CURHASH=$(sha256_of "$2")
    # 해시 도구가 없으면 편집 여부를 가릴 수 없다. 갱신은 살리고 편집은 .bak 으로 남기는
    # 보수적 경로(manifest 없음과 동일)로 간다. 비교를 시도하면 ""=="" 가 참이 되어
    # 파일이 조용히 갱신되지 않는 쪽으로 샐 수 있다.
    if [ -z "$CURHASH" ] || [ -z "$NEWHASH" ]; then
      cp "$2" "$2.bak"
      mv "$TMP" "$2"
      echo "알림: 해시 도구(sha256sum/shasum)가 없어 $3 을(를) 백업 후 갱신했습니다($3.bak)."
    elif RECORDED=$(manifest_get "$3"); then
      if [ -n "$CURHASH" ] && [ "$CURHASH" = "$RECORDED" ]; then
        mv "$TMP" "$2"                     # Owner가 안 건드림 → 갱신
      elif [ "$CURHASH" = "$NEWHASH" ]; then
        rm -f "$TMP"                       # 이미 새 내용과 같음
      else
        mv "$TMP" "$2.new"                 # Owner가 편집함 → 덮지 않는다
        # 편집을 지키는 건 맞지만, 그 대가로 이 파일만 옛 버전에 묶인다. 절차·역할·권한은
        # 새 버전으로 갱신되므로 규칙이 서로 어긋난다. 몇 버전 뒤처졌는지 숫자로 말해 준다.
        OLDV=$(sed -n 's/^HARNESS_VERSION: *//p' "$2" | head -1)
        GAP=$(( $(ver_minor "$VERSION") - $(ver_minor "${OLDV:-$VERSION}") ))
        echo "알림: $3 을(를) 직접 수정한 것으로 보여 덮어쓰지 않았습니다. 새 버전은 $3.new 입니다."
        echo "      주의: $3 는 v${OLDV:-?} 에 묶입니다. 절차·역할·권한은 v$VERSION 으로 갱신되므로"
        echo "      규칙이 서로 어긋난 상태로 돌게 됩니다."
        if [ "$GAP" -ge 5 ] 2>/dev/null; then
          echo ""
          echo "      *** 버전 차이가 큽니다(마이너 $GAP 단계). 그 사이에 절차·역할·권한이 여러 번"
          echo "          바뀌었으므로 이 상태의 팀은 정상 동작하지 않습니다. 반드시 갱신하세요. ***"
          echo ""
        fi
        echo "      해결(권장) — 이 명령 하나면 됩니다:"
        echo "        ./init.sh --accept-constitution $TARGET"
        echo "      직접 쓰신 규칙을 dev-agent-team/PROJECT_RULES.md 로 옮기고 새 헌법을 받아들인 뒤"
        echo "      설치를 계속해 manifest 까지 맞춥니다(이전 내용은 $3.owner-backup 에 남습니다)."
        echo "      무엇이 바뀌는지 먼저 보려면:"
        echo "        python3 dev-agent-team/selfcheck.py --constitution-diff"
        echo "      갱신하지 않으면 단계 merge 게이트가 constitution 으로 막힙니다."
      fi
    else
      cp "$2" "$2.bak"                     # manifest 이전 프로젝트 → 백업 후 갱신
      mv "$TMP" "$2"
      echo "알림: $3 을(를) 갱신했습니다. 이전 내용은 $3.bak 에 보관했습니다."
    fi
  fi
  # 현재 파일 기준으로 기록한다(덮어썼으면 새 해시, 보존했으면 편집된 해시).
  printf '%s  %s\n' "$(sha256_of "$2")" "$3" >> "$MANIFEST.tmp"
}

# 스킬 3종을 주어진 디렉터리에 렌더
emit_skills() {
  for s in team-dev logging-rule lib-research code-convention test-design ui-design; do
    render "$SRC/templates/skills/$s/SKILL.md.tmpl" "$TARGET/$1/$s/SKILL.md"
  done
}

# 역할 메타데이터 (frontmatter 생성용)
role_desc() { case "$1" in
  planner) echo "요구사항을 단계로 나눈다. 결정을 내린다. Owner 질문을 만든다." ;;
  tester)  echo "단계 목표를 받아 테스트케이스를 작성한다." ;;
  coder)   echo "테스트를 통과시키는 코드를 작성한다." ;;
  checker) echo "테스트 전체를 실행하고 PASS/FAIL을 판정한다." ;;
  documenter) echo "완성된 코드로 README와 사용법 문서를 만든다." ;;
  designer)   echo "UI/화면의 설계 명세(디자인 토큰·컴포넌트·접근성·반응형)를 만든다." ;;
  reviewer)   echo "코드와 테스트코드를 규칙에 비추어 검토하고 지적한다." ;;
  lead)       echo "개발 방향·우선순위를 정하고 백로그를 그루밍하며, 단계·최종 회고로 절차 개선안을 낸다." ;;
  critic)     echo "결정과 계획에 반론을 펴고 고위험·모호성을 가린다." ;;
  security)   echo "코드의 보안 위험(비밀·인젝션·위험 호출)을 점검한다." ;;
  evaluator)  echo "산출물이 요구한 것을 했는지 축별로 점수와 격차를 낸다." ;;
esac; }
role_model() { case "$1" in
  coder|tester|designer)      echo "opus" ;;
  checker|documenter)         echo "sonnet" ;;
  planner|lead|reviewer|critic|security|evaluator) echo "opus" ;;
esac; }
# 추론 강도는 전 역할 high 고정 — 역할별로 낮추지 않는다.
role_effort() { echo "high"; }
claude_tools() { case "$1" in
  planner)        echo "Read, Write, Grep" ;;
  tester)         echo "Read, Write" ;;
  coder)          echo "Read, Write, Edit, Bash" ;;
  checker)        echo "Bash, Read" ;;
  documenter)     echo "Read, Write, Edit, Bash" ;;
  designer)       echo "Read, Write" ;;
  reviewer|lead|critic|security|evaluator) echo "Read, Grep" ;;
esac; }
opencode_tools() { case "$1" in
  planner|tester) printf '  write: true\n  edit: false\n  bash: false' ;;
  coder)          printf '  write: true\n  edit: true\n  bash: true' ;;
  checker)        printf '  write: false\n  edit: false\n  bash: true' ;;
  documenter)     printf '  write: true\n  edit: true\n  bash: true' ;;
  designer)       printf '  write: true\n  edit: false\n  bash: false' ;;
  reviewer|lead|critic|security|evaluator) printf '  write: false\n  edit: false\n  bash: false' ;;
esac; }

# TEST_LOG.md 5열 -> 7열 마이그레이션 (v1.22.0에서 재시도·리뷰지적 열이 생겼다).
# init은 기존 상태 파일을 덮지 않으므로 옛 프로젝트는 재설치해도 5열로 남는다.
# 모두 7열로 올라간 뒤에는 이 함수를 지워도 된다.
migrate_test_log() {
  f="$1"
  [ -f "$f" ] || return 0
  # 옛 5열 헤더가 있고 새 열이 아직 없을 때만 건드린다(멱등).
  grep -qE "^\|[[:space:]]*단계[[:space:]]*\|[[:space:]]*신규[[:space:]]*\|[[:space:]]*누적[[:space:]]*\|[[:space:]]*전체 결과[[:space:]]*\|[[:space:]]*커밋[[:space:]]*\|$" "$f" || return 0
  grep -q "재시도" "$f" && return 0
  cp "$f" "$f.bak"
  # 파이프가 정확히 6개인 줄만 마지막 칸(커밋) 앞에 두 칸을 끼운다. 나머지 줄은 원문 유지.
  awk '
    {
      line = $0
      if (substr(line, 1, 1) == "|" && gsub(/\|/, "|", line) == 6) {
        split($0, a, "|")
        head = a[2] "|" a[3] "|" a[4] "|" a[5]
        sep = head
        gsub(/[-| :]/, "", sep)
        if (a[2] ~ /단계/ && a[6] ~ /커밋/) {
          # 헤더 앞에 새 열 설명을 넣는다(위 가드 덕에 아직 없는 것이 보장된다).
          print "- 재시도: 이 단계에서 checker를 다시 부른 횟수(NEW_FAIL·REGRESSION 재시도 포함)."
          print "- 리뷰지적: 이 단계에서 받은 코드·보안 리뷰 지적 건수. 리뷰 단계가 없으면 `-`."
          print ""
          mid = " 재시도 | 리뷰지적 "
        }
        else if (sep == "") mid = "---|---"
        else mid = " - | - "
        print "|" head "|" mid "|" a[6] "|"
        next
      }
      print
    }
  ' "$f.bak" > "$f.tmp" && mv "$f.tmp" "$f"
  echo "TEST_LOG.md를 7열로 갱신했습니다 (원본: dev-agent-team/TEST_LOG.md.bak)."
}

# 역할 목록: designer는 양 프로파일 공통(UI 단계에서만 호출).
# lead·reviewer·critic·security는 large 프로파일에서만 깐다.
ROLES="planner tester coder checker documenter designer"
[ "$PROFILE" = large ] && ROLES="$ROLES lead reviewer critic security evaluator"

echo "프로파일: $PROFILE_LABEL / 에이전트: $AGENTS → $TARGET"

# ── 4. 공통 파일 (모든 에이전트) ──────────────────────────────
# AGENTS.md = 공통 헌법. dev-agent-team/ = 에이전트 작업/상태. tests/ logs/ common/ = 제품.
# ── 4-0. 헌법 동결 해소 (--accept-constitution) ─────────────────────────
# render_managed 가 돌기 **전에** 처리해야 한다. 여기서 .new 를 본파일로 올려 두면
# render_managed 가 "이미 새 내용" 으로 보고 manifest 까지 맞춰 준다 — 설치를 두 번
# 돌릴 필요가 없다.
accept_one() { # $1=본파일 경로  $2=표시 이름
  [ -f "$1.new" ] || return 0
  OLDV=$(sed -n 's/^HARNESS_VERSION: *//p' "$1" | head -1)
  NEWV=$(sed -n 's/^HARNESS_VERSION: *//p' "$1.new" | head -1)
  # Owner 가 직접 넣은 줄을 PROJECT_RULES.md 로 옮긴다. 판정은 설치될 selfcheck 가 한다
  # (규칙 안의 줄과 하네스 옛 문장을 걸러 내는 로직이 거기 있다).
  OWNER_LINES=""
  if [ -f "$TARGET/dev-agent-team/selfcheck.py" ] && [ -n "$PY_BIN" ]; then
    OWNER_LINES=$( cd "$TARGET" && "$PY_BIN" dev-agent-team/selfcheck.py --constitution-diff 2>/dev/null \
      | sed -n 's/^\[scope\]     //p' )
  fi
  if [ -n "$OWNER_LINES" ]; then
    mkdir -p "$TARGET/dev-agent-team"
    { echo ""
      echo "## $2 에서 옮겨온 규칙 (하네스 v$NEWV 업데이트 시 자동 이관)"
      echo "<!-- 헌법을 좁히는 방향으로만 작동합니다. 안전장치는 무효화하지 못합니다. -->"
      printf '%s\n' "$OWNER_LINES"
    } >> "$TARGET/dev-agent-team/PROJECT_RULES.md"
    echo "알림: $2 에 직접 쓰신 규칙을 dev-agent-team/PROJECT_RULES.md 로 옮겼습니다:"
    printf '%s\n' "$OWNER_LINES" | sed 's/^/        /'
  fi
  cp "$1" "$1.owner-backup"
  mv "$1.new" "$1"
  echo "알림: $2 를 v${OLDV:-?} -> v${NEWV:-?} 로 갱신했습니다(이전 내용은 $2.owner-backup)."
}
if [ "$ACCEPT_CONST" = "1" ]; then
  PY_BIN=$(command -v python3 || command -v python || true)
  accept_one "$TARGET/AGENTS.md" "AGENTS.md"
  accept_one "$TARGET/CLAUDE.md" "CLAUDE.md"
fi

render_managed "$SRC/templates/AGENTS.md.tmpl" "$TARGET/AGENTS.md" "AGENTS.md"
mkdir -p "$TARGET/common" "$TARGET/tests" "$TARGET/logs" \
         "$TARGET/dev-agent-team/libs" "$TARGET/dev-agent-team/guides" "$TARGET/dev-agent-team/answered" "$TARGET/dev-agent-team/hooks"
cp "$SRC/templates/common/logger.py"        "$TARGET/common/logger.py"
cp "$SRC/templates/project/selfcheck.py"     "$TARGET/dev-agent-team/selfcheck.py"
cp "$SRC/templates/hooks/block_on_owner_question.sh" "$TARGET/dev-agent-team/hooks/"
cp "$SRC/templates/hooks/protect_tests.sh"           "$TARGET/dev-agent-team/hooks/"
chmod +x "$TARGET/dev-agent-team/hooks/"*.sh
cp "$SRC/templates/docs/OWNER_GUIDE.md"     "$TARGET/dev-agent-team/guides/OWNER_GUIDE.md"
cp "$SRC/templates/docs/DEBUG_GUIDE.md"     "$TARGET/dev-agent-team/guides/DEBUG_GUIDE.md"
[ -f "$TARGET/dev-agent-team/DECISIONS.md" ] || cp "$SRC/templates/project/DECISIONS.md" "$TARGET/dev-agent-team/DECISIONS.md"
[ -f "$TARGET/dev-agent-team/PROJECT_RULES.md" ] || cp "$SRC/templates/project/PROJECT_RULES.md" "$TARGET/dev-agent-team/PROJECT_RULES.md"
[ -f "$TARGET/dev-agent-team/TEST_LOG.md" ]  || cp "$SRC/templates/project/TEST_LOG.md"  "$TARGET/dev-agent-team/TEST_LOG.md"
migrate_test_log "$TARGET/dev-agent-team/TEST_LOG.md"
[ -f "$TARGET/dev-agent-team/libs/INDEX.md" ] || cp "$SRC/templates/project/docs-libs-INDEX.md" "$TARGET/dev-agent-team/libs/INDEX.md"
[ -f "$TARGET/dev-agent-team/BACKLOG.md" ] || cp "$SRC/templates/project/BACKLOG.md" "$TARGET/dev-agent-team/BACKLOG.md"
if [ "$PROFILE" = "large" ] && [ ! -f "$TARGET/dev-agent-team/DIRECTION.md" ]; then
  cp "$SRC/templates/project/DIRECTION.md" "$TARGET/dev-agent-team/DIRECTION.md"
fi
# 가드 훅의 줄끝을 대상 프로젝트의 git 에서도 고정한다. 이게 없으면 Owner 가 이 프로젝트를
# 커밋한 뒤 Windows 에서 클론할 때 .sh 가 CRLF 가 되어 정지 메커니즘이 무력화된다.
# Owner 가 이미 쓰던 .gitattributes 는 덮지 않고 필요한 줄만 끝에 덧붙인다(뒤 규칙이 이긴다).
GA="$TARGET/.gitattributes"
if [ ! -f "$GA" ]; then
  cp "$SRC/templates/project/gitattributes" "$GA"
elif ! grep -q 'team-dev-harness-eol-guard' "$GA"; then
  printf '\n' >> "$GA"
  cat "$SRC/templates/project/gitattributes" >> "$GA"
  echo "알림: .gitattributes 끝에 가드 훅 줄끝 고정 규칙을 추가했습니다."
fi

touch "$TARGET/logs/.gitkeep" "$TARGET/dev-agent-team/answered/.gitkeep"

# ── 5. Claude Code 오버레이 ───────────────────────────────────
if has_agent claude; then
  render_managed "$SRC/templates/CLAUDE.md.tmpl" "$TARGET/CLAUDE.md" "CLAUDE.md"
  render "$SRC/templates/settings.json.tmpl" "$TARGET/.claude/settings.json"
  emit_skills ".claude/skills"
  mkdir -p "$TARGET/.claude/agents"
  for r in $ROLES; do
    body="$(render_stdout "$SRC/templates/roles/$r.md.tmpl")"
    model="$(role_model "$r")"
    effort="$(role_effort "$r")"
    { echo "---"
      printf 'name: %s\n' "$r"
      printf 'description: %s\n' "$(role_desc "$r")"
      [ -n "$model" ] && printf 'model: %s\n' "$model"
      [ -n "$effort" ] && printf 'effort: %s\n' "$effort"
      printf 'tools: %s\n' "$(claude_tools "$r")"
      echo "---"
      printf '%s\n' "$body"
    } > "$TARGET/.claude/agents/$r.md"
  done
fi

# ── 6. Codex 오버레이 ─────────────────────────────────────────
# Codex는 별도 서브에이전트가 없어 역할을 .agents/skills/ 로 둔다(단일 에이전트가 순차 수행).
if has_agent codex; then
  render "$SRC/templates/codex/config.toml.tmpl" "$TARGET/.codex/config.toml"
  cp "$SRC/templates/codex/hooks.json"           "$TARGET/.codex/hooks.json"
  emit_skills ".agents/skills"
  for r in $ROLES; do
    body="$(render_stdout "$SRC/templates/roles/$r.md.tmpl")"
    mkdir -p "$TARGET/.agents/skills/$r"
    { printf -- "---\nname: %s\ndescription: %s\n---\n" "$r" "$(role_desc "$r")"
      printf '%s\n' "$body"; } > "$TARGET/.agents/skills/$r/SKILL.md"
  done
fi

# ── 7. opencode 오버레이 ──────────────────────────────────────
if has_agent opencode; then
  render "$SRC/templates/opencode/opencode.json.tmpl" "$TARGET/opencode.json"
  mkdir -p "$TARGET/.opencode/plugins" "$TARGET/.opencode/agents"
  cp "$SRC/templates/opencode/plugins/guard.js" "$TARGET/.opencode/plugins/guard.js"
  # opencode는 .agents/skills/ 를 호환 경로로 읽는다. codex가 안 깔렸으면 여기서 보장.
  [ -d "$TARGET/.agents/skills/team-dev" ] || emit_skills ".agents/skills"
  for r in $ROLES; do
    body="$(render_stdout "$SRC/templates/roles/$r.md.tmpl")"
    { printf -- "---\ndescription: %s\nmode: subagent\ntools:\n%s\n---\n" "$(role_desc "$r")" "$(opencode_tools "$r")"
      printf '%s\n' "$body"; } > "$TARGET/.opencode/agents/$r.md"
  done
fi

# manifest 확정. 이번에 렌더하지 않은 항목(에이전트 구성을 바꿔 설치한 경우)은 그대로
# 이어간다 — 안 그러면 다음 설치 때 "기록 없음"으로 보여 불필요한 .bak 이 생긴다.
if [ -f "$MANIFEST.tmp" ]; then
  if [ -f "$MANIFEST" ]; then
    awk 'NR==FNR { seen[$2]=1; next } !($2 in seen)' "$MANIFEST.tmp" "$MANIFEST" > "$MANIFEST.keep"
    cat "$MANIFEST.tmp" "$MANIFEST.keep" > "$MANIFEST.merged"
    mv "$MANIFEST.merged" "$MANIFEST"
    rm -f "$MANIFEST.keep"
  else
    mv "$MANIFEST.tmp" "$MANIFEST"
  fi
  rm -f "$MANIFEST.tmp"
fi

# ── 8. git 초기화 ─────────────────────────────────────────────
if [ ! -d "$TARGET/.git" ]; then
  ( cd "$TARGET" \
    && git init -q \
    && printf "logs/app.log\n__pycache__/\n.pytest_cache/\n" > .gitignore \
    && git add -A \
    && git -c user.name=harness -c user.email=harness@local \
         commit -qm "[harness] init (profile=$PROFILE, agents=$AGENTS, v$VERSION)" )
fi

# ── 8b. 파이썬 필수 확인 ────────────────────────────────────────────────
# 하네스는 제품 언어와 무관하게 파이썬을 쓴다 — 가드 훅이 훅 입력(JSON)에서 경로를 뽑을 때,
# 그리고 dev-agent-team/selfcheck.py(게이트·점수)를 돌릴 때. 자바·C#처럼 파이썬을 안 쓰는
# 팀이 그냥 설치하면, 가드가 fail-closed 라 **파일 편집이 전부 막힌다**. 여기서 먼저 말한다.
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo ""
  echo "경고: python3/python 을 찾지 못했습니다."
  echo "      이 하네스는 만들려는 제품의 언어와 무관하게 파이썬이 필요합니다:"
  echo "        - dev-agent-team/hooks/protect_tests.sh 가 훅 입력에서 경로를 뽑을 때"
  echo "        - dev-agent-team/selfcheck.py (단계 merge 게이트·산출물 점수)"
  echo "      가드는 확인이 불가능하면 통과시키지 않고 막습니다(fail-closed)."
  echo "      **파이썬 없이는 파일 편집이 전부 차단됩니다.** 먼저 파이썬을 설치하세요."
  echo ""
fi

# ── 9. hook 실동작 검증 (공통 dev-agent-team/hooks) ─────────────────────
if bash "$SRC/tests/verify_hooks.sh" "$TARGET"; then
  echo ""
  echo "설치 완료 (v$VERSION, $PROFILE, [$AGENTS])."
  echo "다음: $TARGET 에서 코딩 에이전트를 열고 '개발 시작'이라고 입력하세요."
  echo "초보자 안내: $TARGET/dev-agent-team/guides/OWNER_GUIDE.md"
  if has_agent codex; then
    echo "Codex 주의: ~/.codex/config.toml 의 [projects.\"$TARGET\"] trust_level=\"trusted\" 등록 후 .codex 설정이 적용됩니다."
  fi
  if has_agent opencode; then
    echo "opencode 주의: 가드레일 플러그인은 .opencode/plugins/guard.js 로 자동 로드됩니다(bun/node 필요)."
  fi
else
  echo ""
  echo "경고: hook 검증 실패. 안전장치가 동작하지 않을 수 있습니다."
  echo "이 상태로 사용하지 말고 관리자에게 문의하세요."
  exit 1
fi
