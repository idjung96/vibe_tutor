#!/usr/bin/env bash
# 기존 테스트 파일의 수정/덮어쓰기를 차단한다. 새 테스트 파일 생성은 허용한다.
# 언어 무관: tests/ 밑 테스트 파일을 Python과 동일하게 보호한다.
#  - python: *_test.py / test_*.py
#  - go    : *_test.go
#  - rust  : *_test.rs / test_*.rs
#  - node·ts: *.test.{js,jsx,ts,tsx,mjs,cjs} / *.spec.{...}
# 파일 경로 추출은 에이전트별 페이로드를 모두 커버한다:
#  - Claude: JSON tool_input.file_path (그 외 일반 키 path/filePath/filename)
#  - Codex : 셸로 실행되는 apply_patch 텍스트의 "*** Update/Delete File: 경로"
#            (Add File 은 신규 생성이라 제외). 단 codex의 전용 apply_patch 훅은
#            미발화 이슈(openai/codex#16732)가 있어, 셸 경유 편집일 때만 잡힌다.
#  - Bash  : tool_input.command 안에서 "쓰기 위치에 온 경로"만 뽑는다.
#            읽기·실행(cat/grep/pytest 등)은 절대 막지 않는다 — checker가 죽는다.
#            셸 파싱은 휴리스틱이라 변수 확장·명령 치환으로 우회 가능하다(과속방지턱).
# 출력은 "테스트 파일로 판정된 경로"만 — 판정 정규식·쓰기 대상 규칙은 guard.js 와 동기화한다.
INPUT=$(cat)
FILES=$(printf '%s' "$INPUT" | python3 -c '
import sys, json, re, os, shlex
raw = sys.stdin.read()
out = []
def add(p):
    if isinstance(p, str) and p.strip():
        out.append(p.strip())
# 1) JSON 필드 (Claude 및 일반 구조)
cmd = ""
try:
    d = json.loads(raw)
    if isinstance(d, dict):
        ti = d.get("tool_input", {})
        if isinstance(ti, dict):
            for k in ("file_path", "path", "filePath", "filename"):
                add(ti.get(k, ""))
            c = ti.get("command", "")
            if isinstance(c, str):
                cmd = c
        for k in ("file_path", "path", "filePath", "filename"):
            add(d.get(k, ""))
except Exception:
    pass
# 2) Codex apply_patch 텍스트: 기존 파일 수정/삭제만 잡는다
for m in re.finditer(r"\*\*\* (?:Update|Delete) File:\s*([^\n\r\"\\]+)", raw):
    add(m.group(1))
# 3) Bash 명령문: 쓰기 대상만 (guard.js 의 bashWriteTargets 와 동일 규칙)
#    tee/mv/rm/truncate/patch = 비플래그 인자 전부, cp = 마지막 인자(목적지),
#    sed = in-place 플래그가 있을 때만, dd = of= 값, 그리고 > >> 리다이렉션 대상.
WRITE_ALL = ("tee", "mv", "rm", "truncate", "patch")
SKIP_HEAD = ("sudo", "env", "command", "nohup", "time", "xargs")
def seg_targets(seg):
    res = []
    for m in re.finditer(r">>?\s*([^\s;|&<>()]+)", seg):
        res.append(m.group(1))
    body = re.sub(r"\d*>>?\s*[^\s;|&<>()]+", " ", seg)
    try:
        argv = shlex.split(body)
    except Exception:
        argv = body.split()
    while argv and ("=" in argv[0] or os.path.basename(argv[0]) in SKIP_HEAD):
        argv = argv[1:]
    if not argv:
        return res
    name = os.path.basename(argv[0])
    rest = argv[1:]
    args = [a for a in rest if not a.startswith("-")]
    if name in WRITE_ALL:
        res.extend(args)
    elif name == "cp":
        if args:
            res.append(args[-1])
    elif name == "sed":
        inplace = False
        for a in rest:
            if a == "--in-place" or a.startswith("--in-place=") or re.match(r"^-[a-zA-Z]*i", a):
                inplace = True
        if inplace:
            res.extend(args)
    elif name == "dd":
        for a in rest:
            if a.startswith("of="):
                res.append(a[3:])
    return res
if cmd:
    for seg in re.split(r"[;\n]|\|\||&&|\|", cmd):
        for t in seg_targets(seg):
            add(t)
# 4) 테스트 파일만 남긴다 (guard.js 의 isTestFile 과 동일 규칙)
TEST_RE = re.compile(
    r"(^|/)tests/([^/]*(_test\.(py|go|rs)|\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs))|test_[^/]*\.(py|rs))$"
)
for p in out:
    if TEST_RE.search(p.replace("\\", "/")):
        print(p)
' 2>/dev/null)

[ -n "$FILES" ] || exit 0
while IFS= read -r FILE; do
  [ -n "$FILE" ] || continue
  if [ -f "$FILE" ]; then
    echo "기존 테스트 파일은 수정 금지다. 테스트가 틀렸다고 판단되면 C등급으로 올려 Owner에게 물어라." >&2
    exit 2
  fi
done <<EOF
$FILES
EOF
exit 0
