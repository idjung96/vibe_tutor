#!/usr/bin/env bash
# 기존 테스트 파일의 수정/덮어쓰기를 차단한다. 새 테스트 파일 생성은 허용한다.
INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | python3 -c "import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('tool_input',{}).get('file_path',''))
except Exception:
    print('')" 2>/dev/null)
[ -n "$FILE" ] || exit 0
case "$FILE" in
  */tests/*_test.py|*/tests/test_*.py|tests/*_test.py|tests/test_*.py)
    if [ -f "$FILE" ]; then
      echo "기존 테스트 파일은 수정 금지다. 테스트가 틀렸다고 판단되면 C등급으로 올려 Owner에게 물어라." >&2
      exit 2
    fi
    ;;
esac
exit 0
