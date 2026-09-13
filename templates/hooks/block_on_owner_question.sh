#!/usr/bin/env bash
# dev-agent-team/OWNER_QUESTION.md에 답이 없으면 도구 사용을 차단한다.
# 답("답: 숫자")이 적히면 자동으로 풀린다. Read는 막지 않는다(matcher에서 제외됨).
# 판정은 **마지막** "답:" 줄만 본다. 아무 "답:" 줄이나 보면, 질문 본문에 예시로 적힌
# "답: 2" 한 줄이 정지를 그 자리에서 풀어 버린다(실제로 그렇게 샜다). 답을 적는 칸은
# 파일의 마지막 "답:" 줄이다 — planner 가 그렇게 쓴다.
DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
Q="$DIR/dev-agent-team/OWNER_QUESTION.md"
cat > /dev/null 2>&1 || true   # stdin(JSON) 소비
[ -f "$Q" ] || exit 0
LAST=$(grep -E '^답:' "$Q" | tail -1)
if printf '%s' "$LAST" | grep -qE '^답:[[:space:]]*[0-9]'; then
  exit 0
fi
echo "Owner 답변 대기 중. dev-agent-team/OWNER_QUESTION.md의 '답:'에 번호가 적힐 때까지 작업을 멈추고 Owner에게 안내하라." >&2
exit 2
