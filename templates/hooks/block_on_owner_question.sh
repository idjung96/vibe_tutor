#!/usr/bin/env bash
# OWNER_QUESTION.md에 답이 없으면 도구 사용을 차단한다.
# 답("답: 숫자")이 적히면 자동으로 풀린다. Read는 막지 않는다(matcher에서 제외됨).
DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
Q="$DIR/OWNER_QUESTION.md"
cat > /dev/null 2>&1 || true   # stdin(JSON) 소비
[ -f "$Q" ] || exit 0
if grep -qE '^답:[[:space:]]*[0-9]' "$Q"; then
  exit 0
fi
echo "Owner 답변 대기 중. OWNER_QUESTION.md의 '답:'에 번호가 적힐 때까지 작업을 멈추고 Owner에게 안내하라." >&2
exit 2
