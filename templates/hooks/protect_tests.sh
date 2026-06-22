#!/usr/bin/env bash
# 기존 테스트 파일의 수정/덮어쓰기를 차단한다. 새 테스트 파일 생성은 허용한다.
# 파일 경로 추출은 에이전트별 페이로드를 모두 커버한다:
#  - Claude: JSON tool_input.file_path (그 외 일반 키 path/filePath/filename)
#  - Codex : 셸로 실행되는 apply_patch 텍스트의 "*** Update/Delete File: 경로"
#            (Add File 은 신규 생성이라 제외). 단 codex의 전용 apply_patch 훅은
#            미발화 이슈(openai/codex#16732)가 있어, 셸 경유 편집일 때만 잡힌다.
INPUT=$(cat)
FILES=$(printf '%s' "$INPUT" | python3 -c '
import sys, json, re
raw = sys.stdin.read()
out = []
def add(p):
    if isinstance(p, str) and p.strip():
        out.append(p.strip())
# 1) JSON 필드 (Claude 및 일반 구조)
try:
    d = json.loads(raw)
    if isinstance(d, dict):
        ti = d.get("tool_input", {})
        if isinstance(ti, dict):
            for k in ("file_path", "path", "filePath", "filename"):
                add(ti.get(k, ""))
        for k in ("file_path", "path", "filePath", "filename"):
            add(d.get(k, ""))
except Exception:
    pass
# 2) Codex apply_patch 텍스트: 기존 파일 수정/삭제만 잡는다
for m in re.finditer(r"\*\*\* (?:Update|Delete) File:\s*([^\n\r\"\\]+)", raw):
    add(m.group(1))
print("\n".join(out))
' 2>/dev/null)

[ -n "$FILES" ] || exit 0
while IFS= read -r FILE; do
  [ -n "$FILE" ] || continue
  case "$FILE" in
    */tests/*_test.py|*/tests/test_*.py|tests/*_test.py|tests/test_*.py)
      if [ -f "$FILE" ]; then
        echo "기존 테스트 파일은 수정 금지다. 테스트가 틀렸다고 판단되면 C등급으로 올려 Owner에게 물어라." >&2
        exit 2
      fi
      ;;
  esac
done <<EOF
$FILES
EOF
exit 0
