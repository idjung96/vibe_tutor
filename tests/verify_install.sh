#!/usr/bin/env bash
# 설치 결과 건강검진. "깔리긴 했는데 쓸 수 있는 상태인가" 를 본다.
# 사용법: ./tests/verify_install.sh [프로젝트디렉토리]
#
# verify_hooks.sh 는 가드 훅의 **동작**만 본다. 이 스크립트는 그보다 넓다 —
# 프로파일에 맞는 파일이 다 있는지, 에이전트 오버레이가 서로 어긋나지 않는지,
# 미렌더 마커가 없는지, 설정 파일이 파싱되는지, 제품 언어와 무관하게 필요한
# 파이썬이 있는지, 헌법이 동결돼 있지 않은지. 마지막에 verify_hooks.sh 도 돌린다.
#
# Owner 가 설치 직후나 업데이트 직후에 그냥 돌리면 된다. init.sh 도 끝에서 이걸 부른다.
set -u
TARGET="${1:-$(pwd)}"
PASS=0; FAIL=0; WARN=0

ok()   { echo "  PASS: $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL: $1"; [ $# -gt 1 ] && echo "        $2"; FAIL=$((FAIL+1)); }
warn() { echo "  WARN: $1"; [ $# -gt 1 ] && echo "        $2"; WARN=$((WARN+1)); }
have() { [ -e "$TARGET/$1" ]; }

echo "[설치 검증] $TARGET"

# ── 1. 설치본인가 ──────────────────────────────────────────────────────────
if ! have AGENTS.md; then
  bad "설치본이 아니다" "$TARGET/AGENTS.md 가 없습니다. 먼저 init.sh 로 설치하세요."
  echo "[설치 검증] PASS $PASS / FAIL $FAIL / WARN $WARN"
  exit 1
fi
VER=$(sed -n 's/^HARNESS_VERSION: *//p' "$TARGET/AGENTS.md" | head -1)
ok "하네스 설치본 (헌법 v${VER:-?})"

# ── 2. 구성 판별 ───────────────────────────────────────────────────────────
# 설치 당시 옵션을 기록해 두지 않으므로 깔린 것에서 읽는다(init.sh 의 재설치 추론과 같은 방식).
PROFILE=small
for f in .claude/agents/lead.md .agents/skills/lead/SKILL.md .opencode/agents/lead.md; do
  have "$f" && { PROFILE=large; break; }
done
AGENTS=""
have .claude/settings.json && AGENTS="$AGENTS claude"
have .codex/config.toml    && AGENTS="$AGENTS codex"
have opencode.json         && AGENTS="$AGENTS opencode"
AGENTS="${AGENTS# }"
if [ -z "$AGENTS" ]; then
  bad "에이전트 오버레이가 하나도 없다" "claude/codex/opencode 중 최소 하나는 깔려야 합니다."
else
  ok "구성: $PROFILE / [$AGENTS]"
fi
if [ "$PROFILE" = small ] && printf '%s' "$AGENTS" | grep -q codex; then
  bad "small 에 codex 가 깔려 있다" "codex 는 large 전용입니다. 재설치하세요: --agent claude,opencode"
fi

# ── 3. 공통 파일 ───────────────────────────────────────────────────────────
for f in dev-agent-team/hooks/protect_tests.sh dev-agent-team/hooks/block_on_owner_question.sh \
         dev-agent-team/selfcheck.py dev-agent-team/guides/OWNER_GUIDE.md \
         dev-agent-team/PROJECT_RULES.md dev-agent-team/DECISIONS.md \
         dev-agent-team/TEST_LOG.md dev-agent-team/BACKLOG.md dev-agent-team/libs/INDEX.md \
         common/logger.py .gitattributes tests logs; do
  have "$f" || bad "공통 파일 없음: $f"
done
[ "$FAIL" -eq 0 ] && ok "공통 파일 13종"

# ── 4. 역할·스킬이 프로파일과 맞는가 ───────────────────────────────────────
COMMON_ROLES="planner tester coder checker documenter designer"
LARGE_ROLES="lead reviewer critic security evaluator"
role_path() { case "$1" in
  claude)   echo ".claude/agents/$2.md" ;;
  codex)    echo ".agents/skills/$2/SKILL.md" ;;
  opencode) echo ".opencode/agents/$2.md" ;;
esac; }
MISS=""; EXTRA=""
for a in $AGENTS; do
  for r in $COMMON_ROLES; do have "$(role_path "$a" "$r")" || MISS="$MISS $a/$r"; done
  for r in $LARGE_ROLES; do
    if [ "$PROFILE" = large ]; then
      have "$(role_path "$a" "$r")" || MISS="$MISS $a/$r"
    else
      have "$(role_path "$a" "$r")" && EXTRA="$EXTRA $a/$r"
    fi
  done
done
[ -n "$MISS" ]  && bad "빠진 역할" "$MISS"
[ -n "$EXTRA" ] && bad "small 인데 large 전용 역할이 있다" "$EXTRA"
{ [ -z "$MISS" ] && [ -z "$EXTRA" ]; } && ok "역할 구성이 $PROFILE 프로파일과 맞는다"

SKILL_BASE=".agents/skills"
printf '%s' "$AGENTS" | grep -q claude && SKILL_BASE=".claude/skills"
SMISS=""
for s in team-dev logging-rule lib-research code-convention test-design ui-design; do
  have "$SKILL_BASE/$s/SKILL.md" || SMISS="$SMISS $s"
done
[ -n "$SMISS" ] && bad "빠진 스킬" "$SMISS" || ok "스킬 6종 ($SKILL_BASE)"

# ── 5. 미렌더 마커 ─────────────────────────────────────────────────────────
# **하네스가 설치한 파일만** 본다. 대상 폴더 전체를 훑으면 Owner 의 제품 파일이 걸린다 —
# 실제로 Flutter 프로젝트에서 PNG 아이콘과 .DS_Store 가 "{{" 바이트를 우연히 담고 있어
# 설치가 실패로 끝났다. -I 로 바이너리도 제외한다(텍스트만 본다).
HARNESS_PATHS=""
for p in AGENTS.md CLAUDE.md opencode.json .gitattributes common/logger.py \
         .claude .codex .opencode .agents dev-agent-team; do
  have "$p" && HARNESS_PATHS="$HARNESS_PATHS $p"
done
LEFT=$(cd "$TARGET" && grep -rlI '{{' $HARNESS_PATHS 2>/dev/null | head -5)
[ -n "$LEFT" ] && bad "렌더되지 않은 {{ 마커가 남았다" "$LEFT" || ok "미렌더 마커 없음"

# ── 6. 설정 파일 파싱 ──────────────────────────────────────────────────────
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  bad "파이썬이 없다" "제품 언어와 무관하게 필요합니다 — 가드 훅과 selfcheck 가 씁니다.
        이 상태로는 파일 편집이 전부 차단됩니다."
else
  ok "파이썬 있음 ($PY)"
  for j in .claude/settings.json opencode.json .codex/hooks.json; do
    have "$j" || continue
    "$PY" -c "import json,sys; json.load(open(sys.argv[1]))" "$TARGET/$j" 2>/dev/null \
      && ok "JSON 유효: $j" || bad "JSON 파손: $j"
  done
  if have .codex/config.toml; then
    "$PY" -c "import tomllib,sys; tomllib.load(open(sys.argv[1],'rb'))" "$TARGET/.codex/config.toml" 2>/dev/null \
      && ok "TOML 유효: .codex/config.toml" || warn "TOML 확인 불가(파이썬 3.11+ 필요)"
  fi
fi
if have .opencode/plugins/guard.js; then
  if command -v node >/dev/null 2>&1; then
    node --check "$TARGET/.opencode/plugins/guard.js" 2>/dev/null \
      && ok "guard.js 문법 유효" || bad "guard.js 문법 오류"
  else
    warn "node 가 없어 guard.js 를 확인하지 못했다" "opencode 는 bun/node 가 필요합니다."
  fi
fi

# ── 7. 헌법 동결 / 게이트 ──────────────────────────────────────────────────
if have AGENTS.md.new || have CLAUDE.md.new; then
  # FAIL 이 아니라 WARN 이다. 이건 설치기가 Owner 편집을 지키려고 **일부러** 남긴 상태라,
  # 설치기가 스스로 만든 상태를 놓고 "설치 실패" 라고 할 수는 없다. 막는 일은 merge
  # 게이트(constitution)가 이미 fail-closed 로 한다.
  warn "헌법이 동결돼 있다 — 단계 merge 가 막힌다" "옛 헌법 + 새 절차로 돌게 됩니다. 코드는 계속 쓸 수 있고
        막히는 것은 단계 merge 게이트입니다(selfcheck --gate 의 constitution).
        해소: ./init.sh --accept-constitution $TARGET"
else
  ok "헌법 동결 없음"
fi
if [ -n "$PY" ]; then
  if ( cd "$TARGET" && "$PY" dev-agent-team/selfcheck.py --gate >/dev/null 2>&1 ); then
    ok "selfcheck --gate 통과"
  else
    GATE_OUT=$( cd "$TARGET" && "$PY" dev-agent-team/selfcheck.py --gate 2>&1 | grep '^\[gate\] FAIL' )
    warn "selfcheck --gate 가 통과하지 않는다" "${GATE_OUT:-(출력 없음)}
        **설치가 잘못된 것이 아닙니다.** --gate 는 개발 중 단계를 merge 할 때 쓰는 검사라,
        이미 코드가 있는 프로젝트에 처음 깔면 기존 코드에 대해 지적이 납니다.
        할 일: 코딩 에이전트를 열고 \"개발 시작\" 이라고 하세요. 0단계 인터뷰에서 지금 코드에
        대한 요구사항을 정리하면 R번호와 계획이 생기고 trace·full-test 가 기준을 얻습니다.
        기존 코드의 print 지적 등은 한꺼번에 고치지 말고 BACKLOG 에 쌓아 단계마다 줄이세요.
        (갓 설치한 **빈** 프로젝트에서 이게 뜨면 그때는 설치가 잘못된 것입니다.)"
  fi
fi

# ── 8. 가드 훅 실동작 (verify_hooks.sh 재사용) ─────────────────────────────
SELF_DIR=$(cd "$(dirname "$0")" && pwd)
if [ -f "$SELF_DIR/verify_hooks.sh" ]; then
  HOOK_OUT=$(bash "$SELF_DIR/verify_hooks.sh" "$TARGET" 2>&1)
  HOOK_LINE=$(printf '%s' "$HOOK_OUT" | grep '^\[hook 검증\] PASS' | tail -1)
  if printf '%s' "$HOOK_OUT" | grep -q 'FAIL 0'; then
    ok "가드 훅 실동작 (${HOOK_LINE#\[hook 검증\] })"
  else
    bad "가드 훅 검증 실패" "$(printf '%s' "$HOOK_OUT" | grep -E '^\s+FAIL:|^\[hook' | head -10)"
  fi
fi

echo "[설치 검증] PASS $PASS / FAIL $FAIL / WARN $WARN"
[ "$FAIL" -eq 0 ]
