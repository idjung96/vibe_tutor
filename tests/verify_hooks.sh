#!/usr/bin/env bash
# hook 실동작 검증. "죽은 안전장치" 방지용.
# 사용법: ./tests/verify_hooks.sh [프로젝트디렉토리]
set -u
TARGET="${1:-$(pwd)}"
REAL_H="$TARGET/dev-agent-team/hooks"

# 검증은 대상 프로젝트를 건드리지 않는다. 훅을 임시 샌드박스에 복사해 거기서만 돌린다.
# (예전엔 $TARGET 에 직접 써서 재설치할 때마다 tests/conftest.py·calc_test.go 같은 실제
#  파일과 dev-agent-team/OWNER_QUESTION.md 를 덮어쓰고 지웠다 — C등급 정지 상태까지 사라졌다.)
SANDBOX=$(mktemp -d 2>/dev/null || mktemp -d -t harnessverify)
trap 'rm -rf "$SANDBOX"' EXIT
mkdir -p "$SANDBOX/dev-agent-team/hooks" "$SANDBOX/tests" "$SANDBOX/src"
cp "$REAL_H"/*.sh "$SANDBOX/dev-agent-team/hooks/" 2>/dev/null || {
  echo "  FAIL: 가드 훅을 찾지 못했습니다 ($REAL_H)"; exit 1; }
chmod +x "$SANDBOX/dev-agent-team/hooks/"*.sh 2>/dev/null || true

export CLAUDE_PROJECT_DIR="$SANDBOX"
H="$SANDBOX/dev-agent-team/hooks"
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
mkdir -p "$SANDBOX/dev-agent-team"
printf '질문: 테스트\n답: 번호를 적고 저장하세요.\n' > "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"
echo '{}' | "$H/block_on_owner_question.sh" >/dev/null 2>&1
check "미답변 질문이 있으면 차단" 2 $?

# 2. 답이 적히면 → 허용(0)
printf '질문: 테스트\n답: 2\n' > "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"
echo '{}' | "$H/block_on_owner_question.sh" >/dev/null 2>&1
check "답이 적히면 허용" 0 $?
rm -f "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"

# 3. 질문 파일이 없으면 → 허용(0)
echo '{}' | "$H/block_on_owner_question.sh" >/dev/null 2>&1
check "질문 파일이 없으면 허용" 0 $?

# 4. 기존 테스트 파일 수정 → 차단(2)
mkdir -p "$SANDBOX/tests"
T="$SANDBOX/tests/stage_0_verify_test.py"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 5. 새 테스트 파일 생성 → 허용(0)
printf '{"tool_input":{"file_path":"%s/tests/stage_99_new_test.py"}}' "$SANDBOX" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "새 테스트 생성 허용" 0 $?

# 6. 테스트 외 파일 → 허용(0)
printf '{"tool_input":{"file_path":"%s/src/app.py"}}' "$SANDBOX" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "일반 파일 허용" 0 $?

# 7. (codex) apply_patch 로 기존 테스트 수정 → 차단(2)
T="$SANDBOX/tests/stage_0_verify_test.py"
touch "$T"
printf '{"tool_input":{"command":"apply_patch","input":"*** Begin Patch\\n*** Update File: %s\\n@@\\n-a\\n+b\\n*** End Patch\\n"}}' "$T" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "codex apply_patch 기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 8. (codex) apply_patch 로 새 테스트 생성(Add File) → 허용(0)
printf '{"tool_input":{"command":"apply_patch","input":"*** Begin Patch\\n*** Add File: %s/tests/stage_98_new_test.py\\n+x\\n*** End Patch\\n"}}' "$SANDBOX" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "codex apply_patch 새 테스트 생성 허용" 0 $?

# 9. (go) 기존 *_test.go 수정 → 차단(2)
T="$SANDBOX/tests/calc_test.go"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "go 기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 10. (go) 새 *_test.go 생성 → 허용(0)
printf '{"tool_input":{"file_path":"%s/tests/new_test.go"}}' "$SANDBOX" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "go 새 테스트 생성 허용" 0 $?

# 11. (rust) 기존 *_test.rs 수정 → 차단(2)
T="$SANDBOX/tests/calc_test.rs"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "rust 기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 12. (node) 기존 *.test.js 수정 → 차단(2)
T="$SANDBOX/tests/calc.test.js"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "node 기존 테스트 수정 차단" 2 $?
rm -f "$T"

# 13. (ts) 새 *.spec.ts 생성 → 허용(0)
printf '{"tool_input":{"file_path":"%s/tests/calc.spec.ts"}}' "$SANDBOX" \
  | "$H/protect_tests.sh" >/dev/null 2>&1
check "ts 새 테스트 생성 허용" 0 $?

# 14. (회귀) tests/conftest.py 같은 비-테스트 파일 → 허용(0)
T="$SANDBOX/tests/conftest.py"
touch "$T"
printf '{"tool_input":{"file_path":"%s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "tests/ 안 비-테스트 파일 허용" 0 $?
rm -f "$T"

# 15. (bash) 리다이렉션으로 기존 테스트 덮어쓰기 → 차단(2)
T="$SANDBOX/tests/stage_0_verify_test.py"
touch "$T"
printf '{"tool_input":{"command":"echo x > %s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "bash 리다이렉션 기존 테스트 덮어쓰기 차단" 2 $?

# 16. (bash) sed -i 로 기존 테스트 수정 → 차단(2)
printf '{"tool_input":{"command":"sed -i s/a/b/ %s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "bash sed -i 기존 테스트 수정 차단" 2 $?

# 17. (bash 회귀) 테스트 실행 + 다른 곳으로 리다이렉션 → 허용(0)
#     여기서 막히면 checker가 죽는다.
printf '{"tool_input":{"command":"pytest %s > /tmp/out"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "bash 테스트 실행·리다이렉션 허용" 0 $?

# 18. (bash 회귀) 테스트 파일 조회 → 허용(0)
printf '{"tool_input":{"command":"cat %s"}}' "$T" | "$H/protect_tests.sh" >/dev/null 2>&1
check "bash 테스트 파일 조회 허용" 0 $?
rm -f "$T"

# 19. (Windows 회귀) 설치된 훅이 LF 인가.
#     Git for Windows 기본값(autocrlf=true)으로 클론하면 .sh 가 CRLF가 되고,
#     init.ps1 이 그대로 복사해 모든 생성 프로젝트로 전파된다. CRLF면 bash가
#     block_on_owner_question 이 exit 255 로 실행 실패하는데, 그 값은 "차단"(exit 2)으로
#     해석되지 않아 결국 통과된다(정지 무력화). CRLF 스크립트를 정상 동작시킬 방법은
#     없으므로 .gitattributes 로 예방하고(21번) 여기서 그 상태를 탐지한다.
CR_FOUND=0
for hk in "$REAL_H/block_on_owner_question.sh" "$REAL_H/protect_tests.sh"; do
  if LC_ALL=C grep -q "$(printf '\r')" "$hk" 2>/dev/null; then
    echo "    CRLF 발견: $hk"
    CR_FOUND=1
  fi
done
check "설치된 가드 훅이 LF 줄끝" 0 $CR_FOUND

# 20. (Windows 회귀) 파이썬 추출이 실패하면 통과시키지 않고 차단하는가(fail-closed).
#     예전엔 추출 실패가 exit 0 이라 기존 테스트 수정이 조용히 허용됐다.
#     PATH 를 재구성하거나 심볼릭 링크를 만들면 Git Bash 에서 깨지므로(심링크가 복사로
#     처리돼 bash.exe 가 DLL 을 못 찾는다), 실패하는 python 스텁을 PATH 앞에 놓는다.
STUB="$SANDBOX/dev-agent-team/.pystub"
mkdir -p "$STUB"
for n in python3 python; do
  printf '#!/bin/sh\nexit 1\n' > "$STUB/$n"
  chmod +x "$STUB/$n"
done
T2="$SANDBOX/tests/stage_9_test.py"
mkdir -p "$SANDBOX/tests"; printf 'def test_r9():\n    assert True\n' > "$T2"
printf '{"tool_name":"Write","tool_input":{"file_path":"tests/stage_9_test.py","content":"x"}}' \
  | ( cd "$SANDBOX" && PATH="$STUB:$PATH" bash "$H/protect_tests.sh" ) >/dev/null 2>&1
check "파이썬 추출 실패 시 차단(fail-closed)" 2 $?
rm -f "$T2"; rm -rf "$STUB"

# 20a. 질문 본문에 예시로 적힌 "답: 2" 가 정지를 풀어 버리지 않는가.
#      가드가 아무 "답:" 줄이나 보면, planner 가 안내로 적은 예시 한 줄이 그 자리에서
#      정지를 해제한다 — C등급 안전장치의 fail-open 이다. 마지막 "답:" 줄만 본다.
EX_BAD=0
printf '# 질문\n아래처럼 적으세요:\n답: 2\n답:\n' > "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"
printf '{"tool_name":"Edit","tool_input":{"file_path":"x.py"}}' \
  | ( cd "$SANDBOX" && bash "$H/block_on_owner_question.sh" ) >/dev/null 2>&1
[ "$?" = "2" ] || { echo "    예시 줄이 정지를 풀었다"; EX_BAD=1; }
printf '# 질문\n번호를 적고 저장하세요(예: 2).\n답: 1\n' > "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"
printf '{"tool_name":"Edit","tool_input":{"file_path":"x.py"}}' \
  | ( cd "$SANDBOX" && bash "$H/block_on_owner_question.sh" ) >/dev/null 2>&1
[ "$?" = "0" ] || { echo "    실제 답인데 안 풀렸다"; EX_BAD=1; }
check "질문 본문의 예시 '답: N' 이 정지를 풀지 않는다" 0 $EX_BAD
rm -f "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"

# 20b. 중첩 테스트와 dart 도 보호되는가.
#      정규식이 [^/]* 라 tests/sub/... 가 통째로 샜다(모든 언어). dart 는 test/utils/ 처럼
#      중첩이 관례라 이걸 놓치면 Dart 프로젝트의 테스트가 거의 다 무방비다.
mkdir -p "$SANDBOX/tests/sub" "$SANDBOX/test/utils"
printf 'x\n' > "$SANDBOX/tests/sub/deep_test.go"
printf 'x\n' > "$SANDBOX/test/utils/score_test.dart"
printf 'x\n' > "$SANDBOX/tests/helper.txt"
NEST_BAD=0
guard_rc() { # $1=경로 -> exit code
  printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$1" \
    | ( cd "$SANDBOX" && bash "$H/protect_tests.sh" ) >/dev/null 2>&1
  echo $?
}
[ "$(guard_rc tests/sub/deep_test.go)" = "2" ]    || { echo "    중첩 go 테스트가 안 막힌다"; NEST_BAD=1; }
[ "$(guard_rc test/utils/score_test.dart)" = "2" ] || { echo "    중첩 dart 테스트가 안 막힌다"; NEST_BAD=1; }
[ "$(guard_rc tests/helper.txt)" = "0" ]           || { echo "    테스트가 아닌 파일을 막는다"; NEST_BAD=1; }
check "중첩 테스트와 dart(test/·tests/ 하위)도 보호" 0 $NEST_BAD
rm -rf "$SANDBOX/tests/sub" "$SANDBOX/test" "$SANDBOX/tests/helper.txt"

# 21. (Windows 회귀) 대상 프로젝트의 .gitattributes 가 가드 훅 줄끝을 고정하는가.
#     19번이 "이미 CRLF 가 된 상태"를 잡는다면, 이건 "앞으로 CRLF 가 되지 않게" 하는
#     예방 장치가 실제로 깔렸는지를 본다. 이게 없으면 Owner 가 이 프로젝트를 커밋한 뒤
#     Windows 에서 클론하는 순간 훅이 깨지고, 설치 때만 도는 19번은 그걸 못 잡는다.
GA_FILE="$TARGET/.gitattributes"
GA_MISSING=1
if [ -f "$GA_FILE" ] && grep -q 'team-dev-harness-eol-guard' "$GA_FILE"; then GA_MISSING=0; fi
check ".gitattributes 가 가드 훅 줄끝을 고정" 0 $GA_MISSING

# 22~23. (opencode) guard.js 가 .sh 와 같은 판정을 내리는가.
#     "세 경로 동기화"는 계약인데 지금까지 21항목이 전부 .sh 만 봤다 — opencode 사용자에게는
#     guard.js 가 유일한 가드인데 실동작을 아무도 확인하지 않았다. 같은 입력을 양쪽에 넣고
#     판정이 갈리는지 본다. 갈리면 둘 중 하나가 조용히 죽어 있다는 뜻이다.
GUARD="$TARGET/.opencode/plugins/guard.js"
if [ ! -f "$GUARD" ]; then
  echo "  SKIP: guard.js 없음(opencode 미설치 — codex/claude 전용 설치다)"
elif ! command -v node >/dev/null 2>&1; then
  echo "  SKIP: node 없음 — guard.js 실동작을 확인할 수 없다(opencode는 bun/node가 필요하다)"
else
  # .js 는 CommonJS 로 읽히므로 .mjs 로 복사해 ESM 으로 import 한다.
  cp "$GUARD" "$SANDBOX/guard.mjs"
  mkdir -p "$SANDBOX/tests" "$SANDBOX/src"
  printf 'def test_r1_x():\n    assert True\n' > "$SANDBOX/tests/stage_1_test.py"
  printf 'print(1)\n' > "$SANDBOX/src/app.py"
  mkdir -p "$SANDBOX/test/utils" "$SANDBOX/tests/sub"
  printf 'x\n' > "$SANDBOX/test/utils/score_test.dart"
  printf 'x\n' > "$SANDBOX/tests/sub/deep_test.go"
  rm -f "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"

  # 케이스: 경로|기대(2=차단,0=허용). .sh 와 guard.js 양쪽에 같은 입력을 준다.
  CASES="tests/stage_1_test.py:2 src/app.py:0 tests/helper.txt:0 tests/new_stage_9_test.py:0 test/utils/score_test.dart:2 tests/sub/deep_test.go:2"
  MISMATCH=0
  for case in $CASES; do
    fp="${case%:*}"; want="${case##*:}"
    printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$fp" \
      | ( cd "$SANDBOX" && bash "$H/protect_tests.sh" ) >/dev/null 2>&1
    sh_rc=$?
    js_rc=$(cd "$SANDBOX" && node --input-type=module -e '
      const dir = process.argv[1], fp = process.argv[2];
      const { TeamGuard } = await import(dir + "/guard.mjs");
      const h = await TeamGuard({ directory: dir });
      try { await h["tool.execute.before"]({ tool: "edit" }, { args: { filePath: fp } }); console.log(0); }
      catch (e) { console.log(2); }
    ' "$SANDBOX" "$fp" 2>/dev/null)
    [ "$sh_rc" = "$want" ] && [ "$js_rc" = "$want" ] || {
      echo "    불일치: $fp 기대=$want sh=$sh_rc js=$js_rc"; MISMATCH=1; }
  done
  check "guard.js 와 protect_tests.sh 의 테스트 보호 판정이 같다(6케이스)" 0 $MISMATCH

  # 미답변 Owner 질문에서 guard.js 도 막는가 (정지 메커니즘의 opencode 쪽 절반)
  printf '# 질문\n1. a\n2. b\n' > "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"
  Q_RC=$(cd "$SANDBOX" && node --input-type=module -e '
    const dir = process.argv[1];
    const { TeamGuard } = await import(dir + "/guard.mjs");
    const h = await TeamGuard({ directory: dir });
    try { await h["tool.execute.before"]({ tool: "bash" }, { args: { command: "ls" } }); console.log(0); }
    catch (e) { console.log(2); }
  ' "$SANDBOX" 2>/dev/null)
  check "guard.js 가 미답변 Owner 질문에서 차단" 2 "${Q_RC:-99}"
  printf '답: 1\n' >> "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"
  A_RC=$(cd "$SANDBOX" && node --input-type=module -e '
    const dir = process.argv[1];
    const { TeamGuard } = await import(dir + "/guard.mjs");
    const h = await TeamGuard({ directory: dir });
    try { await h["tool.execute.before"]({ tool: "bash" }, { args: { command: "ls" } }); console.log(0); }
    catch (e) { console.log(2); }
  ' "$SANDBOX" 2>/dev/null)
  check "guard.js 가 '답: 번호' 기입 후 해제" 0 "${A_RC:-99}"
  rm -f "$SANDBOX/dev-agent-team/OWNER_QUESTION.md"
fi

echo "[hook 검증] PASS $PASS / FAIL $FAIL"
[ "$FAIL" -eq 0 ]
