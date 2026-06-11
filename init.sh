#!/usr/bin/env bash
# team-dev-harness 설치 스크립트
# 사용법: ./init.sh [--profile small|large] [대상디렉토리]
# 프로파일을 생략하면 ANTHROPIC_BASE_URL로 자동 판별한다.
#   온프레미스(사내 LLM) = small, 외부(Claude) = large
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(cat "$SRC/HARNESS_VERSION")"

PROFILE=""
TARGET=""
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
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

# ── 1. 프로파일 자동 판별 ──────────────────────────────────────
if [ -z "$PROFILE" ]; then
  BASE="${ANTHROPIC_BASE_URL:-}"
  if [ -z "$BASE" ]; then
    PROFILE=large   # 기본 엔드포인트 = api.anthropic.com = 외부 Claude
  elif echo "$BASE" | grep -qiE '134\.75\.147\.|kims|litellm|localhost|127\.0\.0\.1|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.'; then
    PROFILE=small   # 사내/내부망 엔드포인트 = 온프레미스 LLM
  else
    echo "어떤 AI에 연결하나요?"
    echo "1. 사내 AI (온프레미스 LLM)"
    echo "2. Claude (인터넷)"
    printf "번호: "
    read -r ans
    if [ "$ans" = "1" ]; then PROFILE=small; else PROFILE=large; fi
  fi
fi

case "$PROFILE" in small|large) ;; *) echo "프로파일은 small 또는 large 여야 합니다."; exit 1 ;; esac

# shellcheck source=/dev/null
. "$SRC/profiles/$PROFILE.conf"

# ── 2. 템플릿 렌더링 ──────────────────────────────────────────
# {{#IF_SMALL}}/{{#IF_LARGE}} 블록은 마커가 한 줄을 통째로 차지해야 한다.
render() {
  src="$1"; dst="$2"
  mkdir -p "$(dirname "$dst")"
  awk -v profile="$PROFILE" '
    $0=="{{#IF_SMALL}}" { mode=(profile=="small")?"keep":"skip"; next }
    $0=="{{#IF_LARGE}}" { mode=(profile=="large")?"keep":"skip"; next }
    $0=="{{/IF_SMALL}}" || $0=="{{/IF_LARGE}}" { mode=""; next }
    mode=="skip" { next }
    { print }
  ' "$src" \
  | sed -e "s|{{PROFILE_LABEL}}|$PROFILE_LABEL|g" \
        -e "s|{{RETRY_LIMIT}}|$RETRY_LIMIT|g" \
        -e "s|{{MAX_CHECKER_CALLS}}|$MAX_CHECKER_CALLS|g" \
        -e "s|{{HARNESS_VERSION}}|$VERSION|g" \
  > "$dst"
}

echo "프로파일: $PROFILE_LABEL → $TARGET"

render "$SRC/templates/CLAUDE.md.tmpl"     "$TARGET/CLAUDE.md"
render "$SRC/templates/settings.json.tmpl" "$TARGET/.claude/settings.json"
for a in planner tester coder checker; do
  render "$SRC/templates/agents/$a.md.tmpl" "$TARGET/.claude/agents/$a.md"
done
for s in team-dev logging-rule lib-research; do
  render "$SRC/templates/skills/$s/SKILL.md.tmpl" "$TARGET/.claude/skills/$s/SKILL.md"
done

# ── 3. 공통 파일과 디렉토리 ───────────────────────────────────
mkdir -p "$TARGET/.claude/hooks" "$TARGET/common" "$TARGET/tests" \
         "$TARGET/logs" "$TARGET/docs/libs" "$TARGET/answered"
cp "$SRC/templates/hooks/block_on_owner_question.sh" "$TARGET/.claude/hooks/"
cp "$SRC/templates/hooks/protect_tests.sh"           "$TARGET/.claude/hooks/"
chmod +x "$TARGET/.claude/hooks/"*.sh
cp "$SRC/templates/common/logger.py"        "$TARGET/common/logger.py"
cp "$SRC/templates/docs/OWNER_GUIDE.md"     "$TARGET/OWNER_GUIDE.md"
cp "$SRC/templates/docs/DEBUG_GUIDE.md"     "$TARGET/DEBUG_GUIDE.md"
[ -f "$TARGET/DECISIONS.md" ] || cp "$SRC/templates/project/DECISIONS.md" "$TARGET/DECISIONS.md"
[ -f "$TARGET/TEST_LOG.md" ]  || cp "$SRC/templates/project/TEST_LOG.md"  "$TARGET/TEST_LOG.md"
[ -f "$TARGET/docs/libs/INDEX.md" ] || cp "$SRC/templates/project/docs-libs-INDEX.md" "$TARGET/docs/libs/INDEX.md"
if [ "$PROFILE" = "large" ] && [ ! -f "$TARGET/NOTES.md" ]; then
  printf "# 단계 밖 발견사항 (한 줄씩)\n\n" > "$TARGET/NOTES.md"
fi
touch "$TARGET/logs/.gitkeep" "$TARGET/answered/.gitkeep"

# ── 4. AGENTS.md 호환 링크 ────────────────────────────────────
ln -sf CLAUDE.md "$TARGET/AGENTS.md"

# ── 5. git 초기화 ─────────────────────────────────────────────
if [ ! -d "$TARGET/.git" ]; then
  ( cd "$TARGET" \
    && git init -q \
    && printf "logs/app.log\n__pycache__/\n.pytest_cache/\n" > .gitignore \
    && git add -A \
    && git -c user.name=harness -c user.email=harness@local \
         commit -qm "[harness] init (profile=$PROFILE, v$VERSION)" )
fi

# ── 6. hook 실동작 검증 ───────────────────────────────────────
if bash "$SRC/tests/verify_hooks.sh" "$TARGET"; then
  echo ""
  echo "설치 완료 (v$VERSION, $PROFILE)."
  echo "다음: $TARGET 에서 Claude Code를 열고 '개발 시작'이라고 입력하세요."
  echo "초보자 안내: $TARGET/OWNER_GUIDE.md"
else
  echo ""
  echo "경고: hook 검증 실패. 안전장치가 동작하지 않을 수 있습니다."
  echo "이 상태로 사용하지 말고 관리자에게 문의하세요."
  exit 1
fi
