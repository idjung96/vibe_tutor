#!/usr/bin/env bash
# 저장소 전체 검증. 이거 하나만 돌리면 된다.
# 사용법: ./tests/run_all.sh
#
# 왜 있나: 검증이 5개 스크립트로 나뉘어 있고 각각 인자가 다르다. CLAUDE.md 가 순서를
# 산문으로 적어 두긴 했지만, 산문으로 적힌 절차는 빠뜨리기 쉽다 — 실제로 이 저장소를
# 고치는 동안 매번 손으로 골라 돌렸다. 여기서 한 번에 묶는다.
#
# 하는 일: large·small 을 임시 폴더에 설치하고(설치 자체가 verify_install 을 부른다),
# 파리티·selfcheck·설치기 테스트를 돌리고, 단일 에이전트 격리와 small+codex 거부까지 본다.
set -u
SRC=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d 2>/dev/null || mktemp -d -t harnessall)
trap 'rm -rf "$WORK"' EXIT
PASS=0; FAIL=0

step() { # 설명 / 명령...
  desc="$1"; shift
  if OUT=$("$@" 2>&1); then
    echo "  PASS: $desc"; PASS=$((PASS+1))
  else
    echo "  FAIL: $desc"; FAIL=$((FAIL+1))
    printf '%s\n' "$OUT" | grep -E '^\s+FAIL:|FAIL [1-9]|오류|Traceback' | head -8 | sed 's/^/        /'
  fi
}

echo "[전체 검증] $SRC"

# ── 1. 설치 (설치기가 끝에서 verify_install.sh 를 부른다) ──────────────────
step "large 설치 + 설치 검증"  bash "$SRC/init.sh" --profile large --agent all "$WORK/large"
step "small 설치 + 설치 검증"  bash "$SRC/init.sh" --profile small --agent claude,opencode "$WORK/small"
step "codex 단독 설치"        bash "$SRC/init.sh" --profile large --agent codex "$WORK/codex"

# ── 2. 단일 에이전트 격리 — 요청하지 않은 오버레이가 생기면 안 된다 ────────
iso() { # 대상 / 있으면 안 되는 경로들
  t="$1"; shift
  bad=""
  for p in "$@"; do [ -e "$t/$p" ] && bad="$bad $p"; done
  [ -z "$bad" ] || { echo "        생기면 안 되는 것:$bad"; return 1; }
}
step "codex 단독: claude·opencode 오버레이 없음" \
  iso "$WORK/codex" .claude opencode.json .opencode
step "small(claude,opencode): codex 오버레이 없음" \
  iso "$WORK/small" .codex

# ── 3. small 에 codex 는 거부돼야 한다 ─────────────────────────────────────
# 에러로 끝나는 것만 보면 부족하다 — 가드가 없어도 뒤늦게 설치 검증이 실패해 exit 1 이
# 되므로 통과해 버린다. 이 가드는 **아무것도 깔기 전에** 막는 것이라 그것까지 확인한다.
refuse() {
  rm -rf "$WORK/bad"
  bash "$SRC/init.sh" --profile small --agent all "$WORK/bad" >/dev/null 2>&1 && {
    echo "        설치가 성공해 버렸다"; return 1; }
  if [ -e "$WORK/bad/AGENTS.md" ]; then
    echo "        중단은 했지만 이미 파일을 깔았다(가드가 너무 늦다)"; return 1
  fi
  return 0
}
step "small + codex 는 아무것도 깔기 전에 중단" refuse

# ── 4. 파리티·단위 테스트 ──────────────────────────────────────────────────
step "init.sh ↔ init.ps1 파리티(large 렌더 대조)" \
  python3 "$SRC/tests/verify_parity.py" "$WORK/large"
step "init.sh ↔ init.ps1 파리티(small 렌더 대조)" \
  python3 "$SRC/tests/verify_parity.py" "$WORK/small"
step "selfcheck 판정 로직"  python3 "$SRC/tests/test_selfcheck.py"
step "설치기 동작"          python3 "$SRC/tests/test_install.py"

# ── 5. 재설치가 상태·구성을 건드리지 않는가(실물 한 번 더) ─────────────────
reinstall_keeps() {
  before=$(cd "$WORK/small" && ls .claude/agents | sort | tr '\n' ' ')
  bash "$SRC/init.sh" "$WORK/small" >/dev/null 2>&1
  after=$(cd "$WORK/small" && ls .claude/agents | sort | tr '\n' ' ')
  [ "$before" = "$after" ] || { echo "        before=$before"; echo "        after =$after"; return 1; }
  [ ! -e "$WORK/small/.codex" ] || { echo "        재설치가 codex 를 깔았다"; return 1; }
}
step "플래그 없는 재설치가 구성을 유지" reinstall_keeps

echo "[전체 검증] PASS $PASS / FAIL $FAIL"
[ "$FAIL" -eq 0 ]
