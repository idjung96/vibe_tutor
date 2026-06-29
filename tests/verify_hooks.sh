#!/usr/bin/env bash
# hook 실동작 검증. "죽은 안전장치" 방지용.
# 사용법: ./tests/verify_hooks.sh [프로젝트디렉토리]
set -u
TARGET="${1:-$(pwd)}"
export CLAUDE_PROJECT_DIR="$TARGET"
H="$TARGET/dev-agent-team/hooks"
PASS=0; FAIL=0

check() { # 설명 기대코드 실제코드
  if [ "$2" -eq "$3" ]; then
    echo "  PASS: $1"; PASS=$((PASS+1))
  else
    echo "  FAIL: $1 (기대 exit $2, 실제 $3)"; FAIL=$((FAIL+1))
  fi
}

echo "[hook 검증] $TARGET"

# 1. 답 없는 OWNER_QUESTION → 차단(2)
mkdir -p "$TARGET/dev-agent-team"
printf '질문: 테스트\n답: 번호를 적고 저장하세요.\n' > "$TARGET/dev-agent-team/OWNER_QUESTION.md"
echo '{}' | "$H/block_on_owner_question.sh" >/dev/null 2>&1
check "미답변 질문이 있으면 차단" 2 $?

# 2. 답이 적히면 → 허용(0)
printf '질문: 테스트\n답: 2\n' > "$TARGET/dev-agent-team/OWNER_QUESTION.md"
echo '{}' | "$H/block_on_owner_question.sh" >/dev/null 2>&1
check "답이 적히면 허용" 0 $?
rm -f "$TARGET/dev-agent-team/OWNER_QUESTION.md"

# 3. 질문 파일이 없으면 → 허용(0)
echo '{}' | "$H/block_on_owner_question.sh" >/dev/null 2>&1
check "질문 파일이 없으면 허용" 0 $?

# 4. 기존 테스트 파일 수정 → 차단(2)
mkdir -p "$TARGET/tests"
T="$TARGET/tests/stage_0_verify_test.py"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 5. 새 테스트 파일 생성 → 허용(0)
printf '{"tool_input":{"file_path":"%s/tests/stage_99_new_test.py"}}' "$TARGET" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "새 테스트 생성 허용" 0 $?

# 6. 테스트 외 파일 → 허용(0)
printf '{"tool_input":{"file_path":"%s/src/app.py"}}' "$TARGET" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "일반 파일 허용" 0 $?

# 7. (codex) apply_patch 로 기존 테스트 수정 → 차단(2)
T="$TARGET/tests/stage_0_verify_test.py"
touch "$T"
printf '{"tool_input":{"command":"apply_patch","input":"*** Begin Patch\\n*** Update File: %s\\n@@\\n-a\\n+b\\n*** End Patch\\n"}}' "$T" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "codex apply_patch 기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 8. (codex) apply_patch 로 새 테스트 생성(Add File) → 허용(0)
printf '{"tool_input":{"command":"apply_patch","input":"*** Begin Patch\\n*** Add File: %s/tests/stage_98_new_test.py\\n+x\\n*** End Patch\\n"}}' "$TARGET" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "codex apply_patch 새 테스트 생성 허용" 0 $?

# 9. (go) 기존 *_test.go 수정 → 차단(2)
T="$TARGET/tests/calc_test.go"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "go 기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 10. (go) 새 *_test.go 생성 → 허용(0)
printf '{"tool_input":{"file_path":"%s/tests/new_test.go"}}' "$TARGET" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "go 새 테스트 생성 허용" 0 $?

# 11. (rust) 기존 *_test.rs 수정 → 차단(2)
T="$TARGET/tests/calc_test.rs"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "rust 기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 12. (node) 기존 *.test.js 수정 → 차단(2)
T="$TARGET/tests/calc.test.js"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "node 기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 13. (ts) 새 *.spec.ts 생성 → 허용(0)
printf '{"tool_input":{"file_path":"%s/tests/calc.spec.ts"}}' "$TARGET" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "ts 새 테스트 생성 허용" 0 $?

# 14. (회귀) tests/conftest.py 같은 비-테스트 파일 → 허용(0)
T="$TARGET/tests/conftest.py"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "tests/ 안 비-테스트 파일 허용" 0 $?
rm -f "$T"

echo "[hook 검증] PASS $PASS / FAIL $FAIL"
[ "$FAIL" -eq 0 ]
