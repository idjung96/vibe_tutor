"""선택적 자가점검 헬퍼 (개발 도구 — 제품 런타임 코드가 아니다).

역할이 'done'을 말하기 전에 스스로 돌려 봐도 된다. 강제는 아니다.
읽기 전용이다. 파일을 고치지 않는다.

사용법(프로젝트 루트에서):
    python3 dev-agent-team/selfcheck.py                          # 언어 감지 후 전체 점검
    python3 dev-agent-team/selfcheck.py --gate                   # 단계 병합 게이트 (아래 참조)
    python3 dev-agent-team/selfcheck.py --record-full-test       # FULL 테스트 통과 상태를 기록
    python3 dev-agent-team/selfcheck.py --score                  # 산출물 점수 -> SCORE.json (아래 참조)
    python3 dev-agent-team/selfcheck.py --constitution-diff      # 헌법 동결 시 업데이트 범위
    python3 dev-agent-team/selfcheck.py --log-summary            # 회고용 TEST_LOG 요약(추세+최근)
    python3 dev-agent-team/selfcheck.py tests/stage_1_test.py    # 특정 테스트만 수집 확인
    (Windows에 python3 가 없으면 python 으로 부른다.)

--gate 는 단계가 checker PASS를 받은 뒤 merge 전에 도는 모드다. 검사는 모두 그대로 하되
exit code는 결정적 3종(collect / print / trace)만 반영한다. security 와 size 는 각각
"후보"와 "근사"라 잘못 막을 수 있어 출력만 하고 차단하지 않는다.
게이트에서는 방금 끝난 단계도 완료로 보고 R번호 추적성을 판정한다.
게이트는 full-test 도 본다 — checker 를 FULL 로 돌리고 --record-full-test 로 기록한 뒤
코드나 테스트가 바뀌었으면 차단한다. 루프에서 선별 실행만 하고 merge 하는 것을 막는 장치다.

--score 는 코드와 문서에 축별 0~100 점을 매겨 dev-agent-team/SCORE.json 에 남긴다.
size 축은 근사치라 점수만 내고 재시도를 강제하지 않는다(--gate 가 안 막는 것과 같은 이유).
**아무것도 막지 않는다** — 막는 것은 --gate 가 한다. 점수가 정하는 것은 하나뿐이다:
다시 시켜볼 것인가(retry), 아니면 더 시켜도 안 되니 Owner에게 올릴 것인가(escalate).
직전 점수와 비교해 오르지 않으면 escalate 다. test 축은 FULL 실행 기록이 없으면 75가
상한이라, 테스트를 실제로 돌리지 않으면 기준(95)에 닿을 수 없다.

하는 일(--score 의 SCORE.json 쓰기와 --record-full-test 외에는 읽기 전용):
1. 제품 언어를 감지한다(마커 파일 우선). python / go / rust / node 를 안다.
2. 테스트 수집 확인 — python이면 pytest --collect-only. 다른 언어는 건너뛴다
   (테스트 수집·실행은 checker가 제품 언어의 러너로 매 단계 수행한다).
3. 감지된 언어의 소스에서 print 계열 사용처를 찾는다(logging-rule 위반 후보).
4. 같은 소스에서 보안 패턴을 스캔한다(하드코딩 비밀값·위험 호출).
5. R번호 추적성을 대조한다 — REQUIREMENTS -> PLAN.json covers -> 테스트 이름 -> README.
   역할들은 각자 자기 산출물 안에서만 R번호를 확인해서 끊어진 고리는 아무도 못 본다.
6. 코드 규모 임계를 검사한다(code-convention: 함수 40줄·인자 5개·중첩 3단계).
7. 헌법(AGENTS.md·CLAUDE.md)이 옛 버전에 묶여 있는지 본다 — .new 가 남아 있으면 동결이다.
   보고만 하고 차단하지 않는다(고칠 사람은 Owner 다).

3~6은 모두 결정적 검사라 작은 모델에서도 안전하게 쓸 수 있다(주관 판단 없음).
툴체인이 필요한 검사(go build / cargo check)는 느리고 네트워크·빌드 산출물을 만들어
'읽기 전용·결정적' 성격을 깨므로 하지 않는다.
"""
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    # tests/ 와 test/ 둘 다 제외한다 — dart 는 test/ 가 관례다. 테스트는 제품 코드가 아니라
    # print·size 같은 제품 규칙의 대상이 아니다(테스트 규칙은 test-design 스킬이 본다).
    ".git", "logs", "common", "tests", "test", "dev-agent-team",
    "__pycache__", ".pytest_cache", ".venv", "venv",
    # 의존성·빌드 산출물 — 제품 코드가 아니다.
    "node_modules", "target", "vendor", "dist", "build", ".next", "coverage",
    # 에이전트 오버레이 — 하니스 설정이지 제품 코드가 아니다(.opencode/plugins/guard.js 등).
    ".claude", ".opencode", ".codex", ".agents",
    # 도구가 만드는 디렉터리. 여기 있는 파일이 제품 언어를 정하면 안 된다 —
    # Flutter 의 ios/Flutter/ephemeral/flutter_lldb_helper.py 하나 때문에 Dart 프로젝트가
    # python 으로 판정돼 게이트가 통째로 막힌 적이 있다.
    "ephemeral", ".dart_tool", "Pods", "DerivedData", ".gradle", ".idea", ".vscode",
}

# 하드코딩 비밀값 의심: key/secret/token/password 등에 문자열 리터럴을 바로 대입.
# os.environ/설정에서 읽으면(= 따옴표로 시작 안 함) 걸리지 않는다. 백틱은 JS 템플릿 리터럴.
SECRET_PATTERNS = [
    r'(?i)(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key)'
    r'\s*[=:]\s*["\'`][^"\'`]+["\'`]',
]

# 사용자에게 보여주는 출력(CLI 제품)은 로그가 아니다. 그 줄에 이 표시가 있으면 print 검사에서 뺀다.
ALLOW_PRINT = "selfcheck: allow-print"

# 코드 규모 임계 — code-convention 스킬의 값과 같아야 한다.
MAX_FUNC_LINES = 40
MAX_FUNC_ARGS = 5
MAX_NESTING = 3

# R번호 추적성 대조 대상.
REQUIREMENTS_PATH = Path("dev-agent-team/REQUIREMENTS.md")
PLAN_PATH = Path("dev-agent-team/PLAN.json")
README_PATH = Path("README.md")
# 헌법 동결 탐지. 재설치가 Owner 편집을 덮지 않으려고 .new 를 남기면, 그 파일만 옛 버전에
# 묶이고 절차·역할·권한은 새 버전이 된다 — 규칙이 서로 어긋난 채로 돈다. 설치 때 한 번
# 스쳐 지나가는 알림 말고, 게이트를 돌 때마다 보이게 한다.
CONSTITUTION = [Path("AGENTS.md"), Path("CLAUDE.md")]
# 가드 스크립트. 이게 사라지면 append-only 테스트 보호도 C등급 정지도 동작하지 않는데,
# 훅 실행 실패는 도구를 막지 않으므로 **조용히** 무방비가 된다. 게이트에서 확인한다.
GUARD_FILES = [Path("dev-agent-team/hooks/protect_tests.sh"),
               Path("dev-agent-team/hooks/block_on_owner_question.sh")]
OPENCODE_GUARD = Path(".opencode/plugins/guard.js")
TESTS_DIR = Path("tests")
# 마지막 FULL 테스트 실행의 소스 트리 해시. 기록자와 검증자가 같은 코드라 파리티 위험이 없다.
FULL_TEST_MARK = Path("dev-agent-team/.last-full-test")

# ── 점수(--score) ──────────────────────────────────────────────────────────
# 점수는 **아무것도 막지 않는다**. 막는 것은 --gate 의 결정적 4종이 한다.
# 점수가 정하는 것은 하나뿐이다 — "다시 시켜볼 것인가, 아니면 Owner에게 올릴 것인가".
SCORE_PATH = Path("dev-agent-team/SCORE.json")
SCORE_PASS = 95          # 이 값 미만인 축이 있으면 재시도 대상
SCORE_TEST_CAP = 75      # FULL 실행 기록이 없거나 낡았으면 test 축 상한.
#                          95에 닿을 수 없게 해서 "안 돌리고 done" 을 기계적으로 막는다.
SCORE_MIN_GAIN = 5       # 재시도했는데 이만큼도 안 오르면 더 시키지 않는다(막힌 것이다)
SCORE_PENALTY = {"rule": 10, "size": 5, "trace": 20, "doc": 20}   # 건당 감점
SCORE_HISTORY = 20       # SCORE.json 에 남기는 추세 길이
# 재시도를 강제하지 않는 축. --gate 가 security·size 를 "후보·근사"라 안 막는 것과 같은 이유다.
# 점수만 내고 기준 미달로 세지 않는다 — 근사치로 coder 를 계속 부르면, 특히 남의 코드를
# 인수한 프로젝트에서 이번 단계와 무관한 옛 함수 때문에 매 단계 재시도가 돈다.
# 합계(total)에는 그대로 들어가므로 고치면 진전으로는 잡힌다.
SCORE_ADVISORY = {"size"}
# 각 스캔이 건수를 남긴다. 반환값(bool)은 건드리지 않는다 — 게이트 동작이 바뀌면 안 된다.
COUNTS = {}
# 읽지 못한 소스 파일. 조용히 건너뛰면 그 안의 위반이 사라진다 — read_text 가 여기 적는다.
# 스캐너 여럿이 같은 파일을 읽으므로 dict 로 모아 파일당 한 번만 남긴다.
UNREADABLE = {}
# R번호 인식. 실제 명명 규약을 그대로 받는다:
#   "R1: 저장한다"(요구사항·README), "R1"(covers), test_r1_x / r1_saves(구분자 뒤),
#   TestR1_Save(Go 캐멀케이스 — 소문자 뒤 대문자 R).
# user1·Router1 처럼 우연히 r+숫자가 붙는 식별자는 걸리지 않는다.
R_NUM = re.compile(r"(?<![A-Za-z0-9])[rR](\d+)(?![0-9])|(?<=[a-z])R(\d+)(?![0-9])")
# 테스트 '선언' 줄만 본다. 파일 전체에서 뽑으면 변수명·주석이 섞여 거짓 양성이 난다.
TEST_DECL = re.compile(
    r"\bdef\s+test\w*"              # python
    r"|\bfunc\s+Test\w*"            # go
    r"|\bfn\s+\w+"                  # rust
    r"|\b(it|test|describe)\s*\("   # js/ts
    r"|\b(testWidgets|group)\s*\("  # dart(test 는 위 js/ts 항목이 잡는다)
)

# 언어별 정의. marker = 루트의 마커 파일(우선 근거), ext = 스캔할 확장자,
# comment = 줄 시작 주석 접두사, printers = print 계열, danger = 위험 호출.
LANGS = {
    "python": {
        "marker": ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
        "ext": [".py"],
        "comment": ("#",),
        "printers": [r'\bprint\s*\('],
        "danger": [
            (r'\beval\s*\(', 'eval'),
            (r'\bexec\s*\(', 'exec'),
            (r'\bos\.system\s*\(', 'os.system'),
            (r'shell\s*=\s*True', 'subprocess shell=True'),
            (r'\bpickle\.loads?\s*\(', 'pickle 역직렬화'),
        ],
    },
    "go": {
        "marker": ["go.mod"],
        "ext": [".go"],
        "comment": ("//", "/*", "*"),
        "printers": [r'\bfmt\.Print(ln|f)?\s*\(', r'(?<![\w.])println\s*\('],
        "danger": [
            (r'exec\.Command\s*\(\s*"(sh|bash|cmd|powershell)"', '셸 경유 명령 실행'),
            (r'\bunsafe\.Pointer\b', 'unsafe.Pointer'),
        ],
    },
    "rust": {
        "marker": ["Cargo.toml"],
        "ext": [".rs"],
        "comment": ("//", "/*", "*"),
        "printers": [r'\b(e?println|e?print|dbg)\s*!'],
        "danger": [
            (r'\bunsafe\s*\{', 'unsafe 블록'),
            (r'Command::new\s*\(\s*"(sh|bash|cmd|powershell)"', '셸 경유 명령 실행'),
        ],
    },
    "node": {
        "marker": ["package.json"],
        "ext": [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"],
        "comment": ("//", "/*", "*"),
        "printers": [r'\bconsole\.(log|debug|info|warn|error|trace)\s*\('],
        "danger": [
            (r'(?<![\w.])eval\s*\(', 'eval'),
            (r'\bnew\s+Function\s*\(', 'new Function'),
            (r'\b(execSync|execFileSync|spawnSync)\s*\(', '셸 경유 명령 실행'),
            (r'child_process\s*\.\s*exec\w*\s*\(', '셸 경유 명령 실행'),
            (r'''require\s*\(\s*["']child_process["']''', 'child_process 사용'),
            (r'\.innerHTML\s*=', 'innerHTML 직접 대입'),
            (r'\bdangerouslySetInnerHTML\b', 'dangerouslySetInnerHTML'),
        ],
    },
    "dart": {
        "marker": ["pubspec.yaml"],
        "ext": [".dart"],
        "comment": ("//", "///", "/*", "*"),
        # debugPrint 도 Flutter 의 print 다. logger 를 쓰라는 규칙은 같다.
        "printers": [r'(?<![\w.])print\s*\(', r'\bdebugPrint\s*\('],
        "danger": [
            (r'Process\.(run|start)\s*\(\s*["\']?(sh|bash|cmd|powershell)', '셸 경유 명령 실행'),
            (r'\bdart:mirrors\b', 'dart:mirrors(런타임 리플렉션)'),
            (r'\bjsonDecode\s*\(\s*await\s', '검증 없는 원격 JSON 역직렬화 후보'),
        ],
    },
}


def detect_langs():
    """제품 언어를 감지한다. 마커 파일이 우선이고, 없으면 소스 파일 존재로 판단한다."""
    root = Path(".")
    found = []
    for name, spec in LANGS.items():
        if any((root / m).is_file() for m in spec["marker"]):
            found.append(name)
    if found:
        return found
    # 마커가 하나도 없을 때만 확장자 존재를 근거로 쓴다(약한 근거).
    for name, spec in LANGS.items():
        if any(True for _ in iter_sources(spec["ext"])):
            found.append(name)
    return found


def iter_sources(exts):
    """제품 소스 파일만 순회한다. SKIP_DIRS 아래는 제외한다."""
    for path in Path(".").rglob("*"):
        if path.suffix not in exts or not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def read_text(path):
    """소스를 읽는다. 못 읽으면 None 을 주고 **어느 파일이었는지 기록한다**.

    예전엔 조용히 건너뛰었다. 그러면 못 읽은 파일의 print 위반이 사라져 게이트가
    "0건" 이라고 보고한다 — 못 읽은 것을 깨끗하다고 말하는 것이다. CP949 로 저장된
    한글 소스나 권한이 없는 파일에서 실제로 그랬다.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        UNREADABLE[str(path)] = type(exc).__name__
        return None


def check_readable():
    """읽지 못한 소스가 있으면 게이트를 막는다. 검사하지 못한 것을 통과로 치지 않는다."""
    if not UNREADABLE:
        print("[read] OK")
        return True
    print(f"[read] FAIL — 소스 {len(UNREADABLE)}개를 읽지 못해 검사하지 못했다:")
    for path, why in sorted(UNREADABLE.items())[:10]:
        print(f"  {path}: {why}")
    print("       UTF-8 로 저장하거나 읽기 권한을 주라. 검사할 수 없는 파일을")
    print("       통과시키면 그 안의 위반은 영영 드러나지 않는다.")
    return False


def _file_code_lines(name, path, text):
    """한 파일의 코드 줄을 내놓는다. 주석 줄은 건너뛴다."""
    comment = LANGS[name]["comment"]
    for num, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if not stripped.startswith(comment):
            yield name, path, num, line, stripped


def iter_code_lines(langs):
    """(언어, 경로, 줄번호, 원문, 공백제거) 를 내놓는다. 주석 줄은 건너뛴다."""
    for name in langs:
        for path in iter_sources(LANGS[name]["ext"]):
            text = read_text(path)
            if text is not None:
                yield from _file_code_lines(name, path, text)


def collect_tests(langs, target):
    """python이면 pytest --collect-only 로 수집 가능 여부를 확인한다."""
    if "python" not in langs:
        print("[collect] SKIP (python 아님 — 테스트 수집·실행은 checker가 제품 언어 러너로 한다)")
        return True
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    if target:
        cmd.append(target)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # pytest 5 = no tests collected. 아직 테스트를 안 만든 초기 상태이지 수집 오류가 아니다.
    if proc.returncode == 5:
        print("[collect] OK (수집된 테스트 0건 — 아직 테스트가 없다)")
        return True
    ok = proc.returncode == 0
    print(f"[collect] {'OK' if ok else 'FAIL'}")
    if not ok:
        print((proc.stdout or "").strip()[-2000:])
        print((proc.stderr or "").strip()[-2000:])
    return ok


def scan_print(langs):
    """제품 코드에서 print 계열 사용처를 찾는다. common/ tests/ 등은 제외한다."""
    hits = []
    for name, path, num, line, stripped in iter_code_lines(langs):
        if ALLOW_PRINT in line:
            continue
        for pat in LANGS[name]["printers"]:
            if re.search(pat, line):
                hits.append(f"{path}:{num}: {stripped}")
                break
    COUNTS["print"] = len(hits)
    if hits:
        print(f"[print] {len(hits)}건 발견 (logger 사용 권장):")
        for hit in hits:
            print("  " + hit)
    else:
        print("[print] 0건")
    return not hits


def scan_security(langs):
    """제품 코드에서 보안 위험 패턴 후보를 찾는다. common/ tests/ 등은 제외한다."""
    hits = []
    for name, path, num, line, stripped in iter_code_lines(langs):
        if any(re.search(pat, line) for pat in SECRET_PATTERNS):
            hits.append(f"{path}:{num}: 하드코딩 비밀값 의심: {stripped}")
        for pat, label in LANGS[name]["danger"]:
            if re.search(pat, line):
                hits.append(f"{path}:{num}: 위험 호출 후보({label}): {stripped}")
    if hits:
        print(f"[security] {len(hits)}건 발견 (후보 — 사람이 확인한다):")
        for hit in hits:
            print("  " + hit)
    else:
        print("[security] 0건")
    return not hits


def _rs_in(text):
    """텍스트에서 R번호 집합을 뽑는다."""
    return {int(m.group(1) or m.group(2)) for m in R_NUM.finditer(text)}


def _test_rs():
    """tests/ 아래 테스트 '선언' 줄에서만 R번호를 뽑는다. {R번호: 건수}."""
    counts = {}
    if not TESTS_DIR.is_dir():
        return counts
    for path in TESTS_DIR.rglob("*"):
        if not path.is_file() or any(part in {"__pycache__", "node_modules"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line in text.splitlines():
            if not TEST_DECL.search(line):
                continue
            for num in _rs_in(line):
                counts[num] = counts.get(num, 0) + 1
    return counts


def scan_trace(include_current=False):
    """R번호가 REQUIREMENTS -> PLAN covers -> 테스트 -> README 로 이어지는지 대조한다.

    개발 중간에 도는 도구라 '아직 안 만든 것'을 실패로 치지 않는다.
    PLAN.json의 current_stage 를 기준으로 '이미 끝났어야 하는 것'만 실패로 본다.
    include_current 는 게이트용이다 — 방금 끝난 현재 단계도 완료로 본다.
    """
    if not REQUIREMENTS_PATH.is_file() or not PLAN_PATH.is_file():
        print("[trace] SKIP (REQUIREMENTS.md 또는 PLAN.json 없음 — 프로젝트 초기)")
        COUNTS["trace"] = 0          # 아직 잴 게 없다 — 문제 0건과 같다
        return True
    plan = _read_plan()
    if plan is None:
        # 재려다 실패했다. 이걸 '문제 0건'으로 두면 점수가 만점이 나온다 — 검사가 죽었는데
        # 깨끗하다고 보고하는 것이 이 도구가 저지를 수 있는 최악의 실패다.
        COUNTS["plan_broken"] = True
        return False
    stages, current = plan

    problems = _trace_report({
        "req_rs": _rs_in(REQUIREMENTS_PATH.read_text(encoding="utf-8")),
        "readme_rs": _rs_in(README_PATH.read_text(encoding="utf-8")) if README_PATH.is_file() else set(),
        "test_counts": _test_rs(),
        "stage_of": _stage_of(stages),
        "current": current + 1 if include_current else current,
        "all_done": current > max((int(s.get("id", 0)) for s in stages), default=0),
    })
    COUNTS["trace"] = len(problems)
    if problems:
        print(f"[trace] {len(problems)}건 문제:")
        for detail, _ in problems:
            print("  " + detail)
    return not problems


def _read_plan():
    """PLAN.json 에서 (stages, current_stage) 를 읽는다. 못 읽으면 None."""
    try:
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        stages = plan["stages"]
        # 타입까지 본다. 리스트가 아니거나 원소가 dict 가 아니면 아래에서 .get 을 부르다
        # AttributeError 로 죽는다 — 상태 파일이 망가졌을 때 크래시가 아니라 판정이 나야 한다.
        if not isinstance(stages, list) or any(not isinstance(x, dict) for x in stages):
            raise TypeError("stages 는 객체의 리스트여야 한다")
        return stages, int(plan.get("current_stage", 1))
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"[trace] FAIL (PLAN.json 을 읽을 수 없다: {exc})")
        return None


def _trace_report(ctx):
    """R번호마다 한 줄씩 찍고 문제 목록을 모은다. ctx 키는 scan_trace 참조."""
    req_rs, stage_of = ctx["req_rs"], ctx["stage_of"]
    problems = []
    for num in sorted(req_rs | set(stage_of)):
        state = {
            "sid": stage_of.get(num),
            "tests": ctx["test_counts"].get(num, 0),
            "in_readme": num in ctx["readme_rs"],
            "in_req": num in req_rs,
        }
        found = _trace_problems(num, state, ctx["current"], ctx["all_done"])
        problems.extend(found)
        note = f"  <- {found[0][1]}" if found else ""
        print(f"[trace] R{num} stage:{state['sid'] or '-'} tests:{state['tests']} "
              f"readme:{'o' if state['in_readme'] else 'x'}{note}")
    return problems


def _covers_rs(stage):
    """한 단계가 covers 하는 R번호 집합."""
    out = set()
    for item in stage.get("covers", []) or []:
        out |= _rs_in(str(item))
    return out


def _stage_of(stages):
    """R번호 -> 그 R을 covers 하는 가장 이른 단계 id."""
    out = {}
    for stage in stages:
        sid = int(stage.get("id", 0))
        for num in _covers_rs(stage):
            if num not in out or sid < out[num]:
                out[num] = sid
    return out


def _trace_problems(num, state, current, all_done):
    """R번호 하나의 문제를 [(상세, 짧은 표시)] 로 낸다. 문제가 없으면 빈 목록."""
    sid = state["sid"]
    if not state["in_req"]:
        return [(f"R{num}: PLAN covers에 있으나 REQUIREMENTS.md에 없다", "PLAN에만 있다(유령 요구사항)")]
    if sid is None:
        return [(f"R{num}: 어느 단계의 covers 에도 없다", "어느 단계도 covers 하지 않는다")]
    out = []
    if sid < current and state["tests"] == 0:
        out.append((f"R{num}: stage{sid} 는 끝났는데 테스트 이름에 R{num} 이 없다",
                    "완료된 단계인데 테스트가 없다"))
    if all_done and not state["in_readme"]:
        out.append((f"R{num}: 모든 단계가 끝났는데 README.md 에 없다",
                    "개발이 끝났는데 README에 없다"))
    return out


def _py_sizes(path, text):
    """python: 표준 ast 로 정확히 잰다."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        nargs = (len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
                 + (1 if args.vararg else 0) + (1 if args.kwarg else 0))
        lines = (node.end_lineno or node.lineno) - node.lineno + 1
        depth = _py_depth(node)
        out.append((node.lineno, node.name, lines, nargs, depth))
    return out


def _child_blocks(node):
    """블록 문의 하위 statement 목록을 (깊이를 늘리는가, stmts) 로 낸다."""
    if isinstance(node, ast.If):
        out = [(True, node.body)]
        # elif 는 AST상 orelse 안의 If 지만 보기에는 같은 단계다. 깊이를 늘리지 않는다.
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            out.append((False, node.orelse))
        elif node.orelse:
            out.append((True, node.orelse))
        return out
    if isinstance(node, ast.Try):
        blocks = [node.body, node.orelse, node.finalbody] + [h.body for h in node.handlers]
        return [(True, b) for b in blocks if b]
    if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        return [(True, b) for b in (node.body, node.orelse) if b]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [(True, node.body)]
    return []


def _py_depth(func):
    """함수 본문의 최대 블록 중첩 깊이. 중첩 함수·클래스는 세지 않는다."""
    def walk(stmts, depth):
        best = depth
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for deeper, sub in _child_blocks(node):
                best = max(best, walk(sub, depth + 1 if deeper else depth))
        return best
    return walk(func.body, 0)


# 들여쓰기 기반 함수 선언 인식 (go/rust/node). gofmt·rustfmt·prettier 가 들여쓰기를 강제해
# 중괄호를 파싱하지 않고도 충분히 안정적이다. 근사임을 출력에 밝힌다.
FUNC_DECL = {
    "go": re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?(\w+)\s*\("),
    "rust": re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[(<]"),
    "node": re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
        r"(?:function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\()"
    ),
    # dart: 한 줄로 끝나는 시그니처만 잡는다(`dart format` 이 짧은 것은 한 줄로 둔다).
    # 여러 줄로 접힌 시그니처는 놓친다 — 다른 언어와 마찬가지로 근사임을 출력에 밝힌다.
    "dart": re.compile(
        r"^\s*(?:@\w+\s+)*(?:static\s+)?(?:[\w$<>,\[\]?]+\s+)?"
        r"([\w$]+)\s*\([^)]*\)\s*(?:async\*?|sync\*)?\s*(?:\{|=>)"
    ),
}


def _indent_of(line, tab=4):
    expanded = line.replace("\t", " " * tab)
    return len(expanded) - len(expanded.lstrip())


def _sig_chars(line, depth):
    """한 줄에서 시그니처 조각과 갱신된 괄호 깊이를 낸다."""
    out = ""
    for ch in line:
        if ch == "(":
            depth += 1
            if depth == 1:
                continue
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return out, 0
        if depth >= 1:
            out += ch
    return out, depth


def _signature(lines, start):
    """선언 줄부터 괄호가 닫힐 때까지의 시그니처 문자열을 잇는다."""
    sig, depth = "", 0
    for line in lines[start:start + 10]:
        piece, depth = _sig_chars(line, depth)
        sig += piece
        if depth == 0 and sig:
            break
    return sig


def _count_args(sig):
    """시그니처에서 최상위 콤마로 인자 수를 센다(제네릭·중첩 괄호는 건너뛴다)."""
    inner, parts = 0, 0
    for ch in sig:
        if ch in "([{<":
            inner += 1
        elif ch in ")]}>":
            inner -= 1
        elif ch == "," and inner == 0:
            parts += 1
    return parts + 1 if sig.strip() else 0


def _body_extent(lines, start, base, unit=4):
    """선언 레벨로 들여쓰기가 돌아올 때까지를 본문으로 본다. (마지막 줄 index, 중첩 깊이)."""
    end, max_indent = start, base
    for j in range(start + 1, len(lines)):
        if not lines[j].strip():
            continue
        indent = _indent_of(lines[j])
        if indent <= base:
            break
        end = j
        max_indent = max(max_indent, indent)
    return end, max(0, (max_indent - base) // unit - 1)


def _brace_sizes(lang, text):
    """go/rust/node: 들여쓰기로 함수 길이·중첩을, 시그니처로 인자 수를 근사한다."""
    pat = FUNC_DECL[lang]
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = pat.match(line)
        if not m:
            continue
        name = next((g for g in m.groups() if g), "?")
        base = _indent_of(line)
        nargs = _count_args(_signature(lines, i))
        end, depth = _body_extent(lines, i, base)
        out.append((i + 1, name, end - i + 1, nargs, depth))
    return out


def _size_hits(path, funcs):
    """임계를 넘은 함수만 표시 문자열로 만든다."""
    out = []
    for lineno, fname, nlines, nargs, depth in funcs:
        over = []
        if nlines > MAX_FUNC_LINES:
            over.append(f"길이 {nlines}줄>{MAX_FUNC_LINES}")
        if nargs > MAX_FUNC_ARGS:
            over.append(f"인자 {nargs}개>{MAX_FUNC_ARGS}")
        if depth > MAX_NESTING:
            over.append(f"중첩 {depth}단계>{MAX_NESTING}")
        if over:
            out.append(f"{path}:{lineno}: {fname}() — " + ", ".join(over))
    return out


def scan_size(langs):
    """코드 규모 임계 초과를 찾는다. 기준은 code-convention 스킬과 같다."""
    hits = []
    for name in langs:
        for path in iter_sources(LANGS[name]["ext"]):
            text = read_text(path)
            if text is None:
                continue
            found = _py_sizes(path, text) if name == "python" else _brace_sizes(name, text)
            hits.extend(_size_hits(path, found))
    label = (f"기준: 함수 {MAX_FUNC_LINES}줄·인자 {MAX_FUNC_ARGS}개·중첩 {MAX_NESTING}단계, "
             "python 외는 근사")
    COUNTS["size"] = len(hits)
    if hits:
        print(f"[size] {len(hits)}건 발견 ({label}):")
        for hit in hits:
            print("  " + hit)
    else:
        print(f"[size] 0건 ({label})")
    return not hits


def tree_hash(langs):
    """제품 소스 + tests/ 의 (상대경로, 내용해시)를 정렬해 하나의 해시로 만든다.

    dev-agent-team/ 등 SKIP_DIRS 는 빠지므로 상태 파일이 바뀌어도 해시는 안 변한다.
    """
    entries = []
    for name in langs:
        for path in iter_sources(LANGS[name]["ext"]):
            entries.append(_file_entry(path))
    if TESTS_DIR.is_dir():
        for path in sorted(TESTS_DIR.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                entries.append(_file_entry(path))
    digest = hashlib.sha256()
    for item in sorted(set(entries)):
        digest.update(item.encode("utf-8"))
    return digest.hexdigest()


def _file_entry(path):
    """해시 계산용 한 줄: 경로와 내용 해시."""
    try:
        body = path.read_bytes()
    except OSError as exc:
        # 빈 내용으로 해싱하면 그 파일이 바뀌어도 해시가 안 움직여 신선도 검사가 샌다.
        # 읽지 못했다는 사실 자체를 해시에 넣는다(그리고 아래 [read] 가 막는다).
        UNREADABLE[str(path)] = type(exc).__name__
        return f"{path.as_posix()}:<unreadable>"
    return f"{path.as_posix()}:{hashlib.sha256(body).hexdigest()}"


def record_full_test(langs):
    """지금 소스 상태를 'FULL 테스트를 통과한 상태'로 기록한다."""
    FULL_TEST_MARK.parent.mkdir(parents=True, exist_ok=True)
    FULL_TEST_MARK.write_text(tree_hash(langs) + "\n", encoding="utf-8")
    print(f"[full-test] 기록함 ({FULL_TEST_MARK})")
    return True


def check_full_test(langs):
    """전체 테스트를 최종 코드로 돌았는지 본다. 게이트에서만 쓴다."""
    if not PLAN_PATH.is_file():
        print("[full-test] SKIP (PLAN.json 없음 — 프로젝트 초기)")
        return True
    if not FULL_TEST_MARK.is_file():
        print("[full-test] FAIL (전체 테스트 실행 기록이 없다. checker를 FULL로 돌린 뒤 "
              "--record-full-test 로 기록하라)")
        return False
    recorded = FULL_TEST_MARK.read_text(encoding="utf-8").strip()
    if recorded != tree_hash(langs):
        print("[full-test] FAIL (전체 테스트 실행 이후 코드나 테스트가 바뀌었다. "
              "checker를 FULL로 다시 돌려라)")
        return False
    print("[full-test] OK")
    return True


def check_constitution():
    """헌법이 옛 버전에 묶여 있는지 본다.

    **버전이 뒤처진 동결은 게이트를 막는다**(_run_gate 의 blocking 에 들어간다). 그 상태의
    팀은 옛 헌법 + 새 절차·역할·권한으로 도는 것이라 규칙이 서로 어긋난다 — 느리게 가는 게
    아니라 틀리게 간다. 틀린 규칙으로 main 에 합치는 것보다 멈추는 편이 낫다.
    코드는 계속 쓸 수 있다. 막히는 건 merge 뿐이고, 해소는 --constitution-diff 로 범위를 보고
    Owner 규칙을 PROJECT_RULES.md 로 옮긴 뒤 .new 를 본파일로 옮기고 설치를 한 번 더 도는 것이다.

    같은 버전에서 Owner 가 고치기만 한 경우는 **막지 않는다** — 기능 불일치가 아니다.
    """
    frozen = []
    for path in CONSTITUTION:
        new = Path(str(path) + ".new")
        if path.is_file() and new.is_file():
            cur = _version_in(path)
            nxt = _version_in(new)
            frozen.append((path.name, cur, nxt))
    if not frozen:
        print("[constitution] OK")
        return True
    behind = False
    for name, cur, nxt in frozen:
        if cur == nxt:
            # 같은 버전에서 Owner 가 고친 것이다. 버전이 뒤처진 건 아니라 급하지 않다.
            print(f"[constitution] {name} 에 직접 수정한 내용이 있다(v{cur}, 버전은 최신).")
            print(f"               {name}.new 와 내용이 다르다. 고유 규칙은 "
                  "dev-agent-team/PROJECT_RULES.md 로 옮기는 것이 낫다.")
        else:
            behind = True
            print(f"[constitution] 동결 — {name} 는 v{cur} 인데 절차·역할·권한은 v{nxt} 다.")
            print(f"               규칙이 어긋난 채로 돌고 있다. {name}.new 를 확인하라.")
    if behind:
        COUNTS["constitution_behind"] = True
        print("               이 상태로는 merge 하지 않는다. 범위를 보려면:")
        print("               python3 dev-agent-team/selfcheck.py --constitution-diff")
    return False


def _version_in(path):
    """파일 머리의 HARNESS_VERSION 줄을 읽는다. 없으면 '?'."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:20]:
            if line.startswith("HARNESS_VERSION:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "?"


def check_guards():
    """가드 스크립트가 제자리에 있는지 본다. 없으면 merge 를 막는다.

    훅이 실행에 실패하면(파일이 없으면) 도구 호출은 그냥 진행된다 — 안전장치가 조용히
    죽는 것이다. 설치 검증은 설치 때만 돌므로, 그 사이를 여기서 본다.
    """
    missing = [str(f) for f in GUARD_FILES if not (f.is_file() and f.stat().st_size > 0)]
    if OPENCODE_GUARD.parent.is_dir() and not (
            OPENCODE_GUARD.is_file() and OPENCODE_GUARD.stat().st_size > 0):
        missing.append(str(OPENCODE_GUARD))
    if missing:
        print(f"[guards] FAIL — 가드가 없다: {', '.join(missing)}")
        print("         이 상태면 기존 테스트 보호도 Owner 질문 정지도 동작하지 않는다.")
        print("         하네스를 다시 설치해 복구하라: ./init.sh <이 폴더>")
        return False
    print("[guards] OK")
    return True


def _split_rules(text):
    """'N. ' 로 시작하는 헌법 규칙을 {번호: 본문} 으로. 이어지는 들여쓴 줄은 같은 규칙이다."""
    rules, num, buf = {}, None, []
    for line in text.splitlines():
        head = re.match(r"^(\d+)\.\s", line)
        if head:
            if num:
                rules[num] = "\n".join(buf)
            num, buf = head.group(1), [line]
        elif num is not None and (line.startswith(" ") or not line.strip()):
            buf.append(line)
        elif num is not None:
            rules[num], num, buf = "\n".join(buf), None, []
    if num:
        rules[num] = "\n".join(buf)
    return {k: re.sub(r"\s+", " ", v).strip() for k, v in rules.items()}


def _owner_only_lines(cur_text, new_text):
    """Owner 가 직접 **덧붙인** 줄만 고른다.

    단순히 ".new 에 없는 줄" 로 잡으면 옛 하네스 규칙 본문이 전부 딸려 온다 — 그건 Owner 것이
    아니라 그냥 낡은 것이고, 이미 "내용이 바뀐 규칙" 으로 따로 보고된다. 그걸
    PROJECT_RULES.md 로 옮기라고 하면 잘못 안내하는 것이다. 그래서 **번호 규칙 안의 줄은
    제외**하고, 규칙 바깥에 새로 생긴 줄만 남긴다.
    """
    def norm(ln):
        return re.sub(r"\s+", " ", ln).strip()

    in_new = {norm(ln) for ln in new_text.splitlines() if ln.strip()}
    # _split_rules 는 본문을 한 줄로 정규화하므로 원본 줄과 대조가 안 된다.
    # 규칙 소속 여부는 원문을 직접 훑어 가린다(판정 규칙은 _split_rules 와 같다).
    rule_lines, inside = set(), False
    for ln in cur_text.splitlines():
        if re.match(r"^\d+\.\s", ln):
            inside = True
        elif inside and not (ln.startswith(" ") or not ln.strip()):
            inside = False
        if inside and ln.strip():
            rule_lines.add(norm(ln))
    # 규칙 밖이어도 하네스의 '옛 문장'이 남는다(문구만 바뀐 설명 줄 등). 그건 Owner 것이
    # 아니다. .new 의 어떤 줄과 특징 어절을 여럿 공유하면 '바뀐 하네스 문장'으로 본다.
    new_sigs = [_sig_words(ln) for ln in new_text.splitlines() if ln.strip()]
    out = []
    for ln in cur_text.splitlines():
        key = norm(ln)
        if not key or key in in_new or key in rule_lines:
            continue
        if key.startswith("HARNESS_VERSION:"):
            continue
        mine = _sig_words(ln)
        if mine and any(len(mine & sig) >= 2 for sig in new_sigs):
            continue
        out.append(ln.rstrip())
    return out


def _sig_words(line):
    """한 줄의 특징 어절. 너무 흔한 조각은 빼고 3자 이상만 본다."""
    words = re.findall(r"[0-9A-Za-z_./\-]{3,}|[가-힣]{3,}", line)
    return {w for w in words if w not in ("dev-agent-team", "AGENTS.md", "CLAUDE.md")}


def _report_scope(name, cur_text, new_text):
    """규칙 단위로 무엇이 바뀌었는지 찍는다. 버전별 메타데이터를 손으로 들고 있지 않는다 —
    그런 표는 반드시 낡는다. 두 파일을 직접 비교하는 쪽이 언제나 맞다."""
    cur_r, new_r = _split_rules(cur_text), _split_rules(new_text)
    both = set(cur_r) & set(new_r)
    changed = sorted((k for k in both if cur_r[k] != new_r[k]), key=int)
    added = sorted(set(new_r) - set(cur_r), key=int)
    gone = sorted(set(cur_r) - set(new_r), key=int)
    print(f"[scope] {name}: 규칙 {len(cur_r)}개 -> {len(new_r)}개")
    print(f"[scope]   내용이 바뀐 규칙: {', '.join(changed) + '번' if changed else '없음'}")
    print(f"[scope]   새로 생긴 규칙:   {', '.join(added) + '번' if added else '없음'}")
    print(f"[scope]   번호가 사라진 것: {', '.join(gone) + '번' if gone else '없음'}")
    for num in changed:
        print(f"[scope]   - {num}번 새 내용: {new_r[num][:110]}")
    owner = _owner_only_lines(cur_text, new_text)
    if owner:
        print(f"[scope]   Owner 가 직접 넣은 것으로 보이는 줄 {len(owner)}개 "
              "— 이건 dev-agent-team/PROJECT_RULES.md 로 옮기면 다음부터 알림이 안 뜬다:")
        for ln in owner[:20]:
            print(f"[scope]     {ln}")
        if len(owner) > 20:
            print(f"[scope]     … 외 {len(owner) - 20}줄")


def constitution_diff():
    """헌법이 동결됐을 때 '무엇을 업데이트해야 하는지' 범위를 낸다."""
    found = False
    for path in CONSTITUTION:
        new = Path(str(path) + ".new")
        if not (path.is_file() and new.is_file()):
            continue
        found = True
        cur_text = path.read_text(encoding="utf-8")
        new_text = new.read_text(encoding="utf-8")
        print(f"[scope] {path.name}: v{_version_in(path)} -> v{_version_in(new)}")
        _report_scope(path.name, cur_text, new_text)
    if not found:
        print("[scope] 동결된 헌법이 없다(.new 파일 없음). 비교할 것이 없다.")
    return 0


TEST_LOG_PATH = Path("dev-agent-team/TEST_LOG.md")
LOG_TAIL = 10            # --log-summary 가 원문으로 보여 주는 최근 단계 수


def _log_rows():
    """TEST_LOG 의 데이터 행을 (단계, 전체결과, 재시도, 리뷰지적) 으로 읽는다.

    가운데 '전체 결과' 칸에는 본문 `|` 가 들어간다(실제 로그가 그렇다). 그래서 가운데를
    쪼개지 않는다 — 앞에서 3칸, 뒤에서 3칸만 세고 나머지를 통째로 결과로 본다.
    """
    if not TEST_LOG_PATH.is_file():
        return None
    rows = []
    for line in TEST_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or set(line) <= set("|- :"):
            continue
        cells = line.strip().strip("|").split("|")
        if len(cells) < 7:
            continue
        stage = cells[0].strip()
        if stage.startswith("단계"):
            continue
        retry, review = cells[-3].strip(), cells[-2].strip()
        rows.append((stage, "|".join(cells[3:-3]).strip(), retry, review))
    return rows


def _num_stats(values):
    """'-' 를 빼고 숫자만 모은다 -> (개수, 합, 평균, 빈칸수)."""
    nums = []
    blank = 0
    for v in values:
        head = re.match(r"-?\d+", v)
        if head and v.strip() != "-":
            nums.append(int(head.group()))
        else:
            blank += 1
    avg = round(sum(nums) / len(nums), 1) if nums else None
    return len(nums), sum(nums), avg, blank


def log_summary():
    """회고용 요약. TEST_LOG 전체를 읽히지 않기 위해 있다.

    단계가 쌓이면 표가 수백 행이 되고 한 칸이 수백 자다(실제로 그랬다). 회고에 필요한 건
    개별 행이 아니라 **추세**라서, 집계와 최근 몇 단계만 주면 된다.
    """
    rows = _log_rows()
    if rows is None:
        print("[log] TEST_LOG.md 가 없다.")
        return 0
    if not rows:
        print("[log] 기록된 단계가 없다.")
        return 0
    print(f"[log] 단계 {len(rows)}개")
    # 판정은 칸 **맨 앞** 단어만 본다. 칸 전체에서 찾으면 설명에 적힌 NEW_FAIL 같은 말까지
    # 세어 버린다 — 실제 로그에서 전부 PASS 인데 14개가 FAIL 로 잡혔다.
    fails = [r for r in rows if r[1].upper().startswith("FAIL")]
    print(f"[log] 판정이 FAIL 인 단계: {len(fails)}개"
          + (f" ({', '.join(r[0].split()[0] for r in fails[:8])})" if fails else ""))
    for name, idx in (("재시도", 2), ("리뷰지적", 3)):
        n, total, avg, blank = _num_stats([r[idx] for r in rows])
        shown = avg if avg is not None else "없음"
        print(f"[log] {name}: 값 있는 단계 {n}개 합계 {total} 평균 {shown}"
              + (f" / 값 없음(-) {blank}개" if blank else ""))
        if n >= 4:                      # 앞뒤 절반을 비교해 추세를 본다
            half = len(rows) // 2
            _, _, a1, _ = _num_stats([r[idx] for r in rows[:half]])
            _, _, a2, _ = _num_stats([r[idx] for r in rows[half:]])
            if a1 is not None and a2 is not None:
                print(f"[log]   전반 평균 {a1} -> 후반 평균 {a2}"
                      f" ({'늘어남' if a2 > a1 else '줄어듦' if a2 < a1 else '변화 없음'})")
    print(f"[log] 최근 {min(LOG_TAIL, len(rows))}단계:")
    for stage, result, retry, review in rows[-LOG_TAIL:]:
        print(f"[log]   {stage[:40]} | 재시도 {retry} | 리뷰지적 {review} | {result[:70]}")
    return 0


def _doc_gap():
    """끝난 단계의 R번호 중 README.md 에 없는 것의 수. 문서 평가 축이다.

    scan_trace 의 README 검사는 '모든 단계가 끝났을 때'만 문제로 친다(개발 중간에
    아직 안 쓴 문서를 실패로 치면 안 되니까). 점수는 단계마다 보므로 여기서는
    '이미 끝난 단계'의 R번호만 대상으로 따로 센다. 판정 기준을 바꾸는 게 아니라
    같은 재료로 다른 것을 재는 것이다.
    """
    if not REQUIREMENTS_PATH.is_file() or not PLAN_PATH.is_file():
        return None                      # 프로젝트 초기 — 잴 수 없다
    plan = _read_plan()
    if plan is None:
        return None
    stages, current = plan
    stage_of = _stage_of(stages)
    readme_rs = _rs_in(README_PATH.read_text(encoding="utf-8")) if README_PATH.is_file() else set()
    done = [num for num, sid in stage_of.items() if sid <= current]
    return sum(1 for num in done if num not in readme_rs)


def _axis(count, penalty):
    """건수를 0~100 점으로. 건수를 못 쟀으면(None) 만점으로 둔다 — 잴 수 없는 것으로 깎지 않는다."""
    if count is None:
        return 100
    return max(0, 100 - penalty * count)


def compute_score(langs):
    """축별 점수를 낸다. 전부 기존 스캔이 이미 잰 값에서 나온다."""
    full_ok = check_full_test(langs)
    scores = {
        "test": 100 if full_ok else SCORE_TEST_CAP,
        "rule": _axis(COUNTS.get("print"), SCORE_PENALTY["rule"]),
        "trace": _axis(COUNTS.get("trace"), SCORE_PENALTY["trace"]),
        "doc": _axis(_doc_gap(), SCORE_PENALTY["doc"]),
        "size": _axis(COUNTS.get("size"), SCORE_PENALTY["size"]),
    }
    return scores


def _read_prev_score():
    """직전 채점 결과를 읽는다 -> (합계, 판정, 추세). 파일이 없거나 깨졌으면 빈 값."""
    if not SCORE_PATH.is_file():
        return None, None, []
    try:
        old = json.loads(SCORE_PATH.read_text(encoding="utf-8"))
        return old.get("total"), old.get("verdict"), old.get("history") or []
    except (json.JSONDecodeError, OSError):
        return None, None, []


def _save_score(out):
    SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORE_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def _current_stage():
    if not PLAN_PATH.is_file():
        return None
    plan = _read_plan()
    return None if plan is None else plan[1]


def _verdict_for(below, delta, prev_verdict):
    """pass / retry / escalate 를 고른다.

    조기 탈출(escalate)은 "다시 시켰는데 안 오른다"는 뜻이다. 그러려면 **직전이 이미
    재시도였어야** 한다. 직전이 pass 였거나 첫 채점이면 방금 문제를 처음 발견한 것이므로
    한 번은 고쳐 보게 한다 — 아니면 새 결함이 나올 때마다 곧바로 Owner에게 올라간다.
    escalate 직후도 여전히 실패 시퀀스 안이다. retry 만 보면 RETRY→ESCALATE→RETRY 로
    진동해서, 막혀 있는데도 계속 다시 시키는 것처럼 보인다.
    """
    if not below:
        return "pass"
    in_retry = prev_verdict in ("retry", "escalate")
    if in_retry and delta is not None and delta < SCORE_MIN_GAIN:
        return "escalate"
    return "retry"


def _score_plan_broken(scores, prev, prev_verdict, history):
    """PLAN.json 을 못 읽으면 trace·doc 을 잴 수 없다. 그 상태를 점수로 덮지 않는다.

    고칠 수 있는 건 메인 세션·Owner 지 coder 가 아니므로 곧바로 올린다.
    """
    total = sum(scores.values())
    print("[score] ESCALATE — dev-agent-team/PLAN.json 을 읽을 수 없어 trace·doc 을 "
          "잴 수 없다. 점수를 믿지 마라. PLAN.json 부터 고쳐야 한다.")
    return _save_score({
        "stage": None, "scores": scores, "overall": 0, "total": total,
        "below": ["trace", "doc"], "prev_total": prev, "prev_verdict": prev_verdict,
        "delta": None if prev is None else total - prev,
        "verdict": "escalate", "plan_broken": True, "history": history})


def _print_score(out):
    scores, verdict, below = out["scores"], out["verdict"], out["below"]
    print("[score] " + "  ".join(
        f"{k}={v}{'*' if k in SCORE_ADVISORY else ''}" for k, v in sorted(scores.items())))
    low_adv = sorted(k for k in SCORE_ADVISORY if scores.get(k, 100) < SCORE_PASS)
    if low_adv:
        print(f"[score] * {', '.join(low_adv)} 는 근사치라 재시도를 강제하지 않는다 "
              "(--gate 가 안 막는 것과 같은 이유). BACKLOG '메모·주의'에 적어 둔다.")
    delta = out["delta"]
    print(f"[score] 최저축={out['overall']} (기준 {SCORE_PASS})  합계={out['total']}"
          + (f" 직전합계={out['prev_total']} 변화={delta:+d}" if delta is not None else " 직전=없음"))
    if verdict == "pass":
        print("[score] PASS — 모든 축이 기준 이상이다.")
    elif verdict == "retry":
        print(f"[score] RETRY — 기준 미달: {', '.join(below)}. 격차를 주고 다시 시킨다.")
    else:
        print(f"[score] ESCALATE — 기준 미달({', '.join(below)})인데 합계가 직전 대비 "
              f"{SCORE_MIN_GAIN}점도 오르지 않았다. 더 시키지 말고 Owner에게 올린다(C등급).")


def write_score(scores):
    """SCORE.json 을 쓰고 재시도 판정을 낸다. 직전 점수와 비교해야 '나아지는 중인지' 안다.

    추세는 SCORE.json 안에 누적한다. TEST_LOG 에 열을 하나 더 만들지 않은 이유는, 열 추가가
    옛 프로젝트 마이그레이션(awk·PowerShell 양쪽)을 또 부르기 때문이다. lead 가 회고에서 읽는다.

    진전은 최저축이 아니라 축 **합계**로 본다 — 최저가 아닌 축을 고치면 최저축은 그대로여서
    개선을 안 한 것처럼 보인다. 최저축은 반대로 **판정 축에서만** 고른다. 권고 축까지 넣으면
    "최저축 85인데 PASS" 처럼 읽혀 무엇이 재시도를 부르는지 흐려진다.
    """
    prev, prev_verdict, history = _read_prev_score()
    if COUNTS.get("plan_broken"):
        return _score_plan_broken(scores, prev, prev_verdict, history)

    judged = {k: v for k, v in scores.items() if k not in SCORE_ADVISORY}
    total = sum(scores.values())
    below = sorted(k for k, v in scores.items()
                   if v < SCORE_PASS and k not in SCORE_ADVISORY)
    delta = None if prev is None else total - prev
    verdict = _verdict_for(below, delta, prev_verdict)
    stage = _current_stage()

    out = {"stage": stage, "scores": scores,
           "overall": min(judged.values()) if judged else 100, "total": total,
           "below": below, "prev_total": prev, "prev_verdict": prev_verdict,
           "delta": delta, "verdict": verdict,
           "history": (history + [{"stage": stage, "total": total,
                                   "verdict": verdict}])[-SCORE_HISTORY:]}
    _save_score(out)
    _print_score(out)
    return out


def _parse_args(args):
    """(gate, record, score, target) 로 가른다."""
    rest = [a for a in args if not a.startswith("--")]
    return ("--gate" in args, "--record-full-test" in args, "--score" in args,
            rest[0] if rest else None)


def _run_without_langs(langs, gate, record, score):
    """제품 언어를 못 찾았을 때. 잴 것이 없으니 어느 모드에서도 통과시킨다."""
    print("[lang] 감지된 제품 언어 없음 — 점검을 건너뛴다.")
    print("       (python/go/rust/node 만 안다. 마커: requirements.txt·pyproject.toml /")
    print("        go.mod / Cargo.toml / package.json)")
    if record:
        record_full_test(langs)
    if gate:
        print("[gate] PASS")
    if score:
        print("[score] SKIP (제품 언어 없음 — 아직 잴 것이 없다)")
    return 0


def _run_gate(results, langs):
    """게이트: 결정적 6종만 차단한다. security(후보)·size(근사)는 잘못 막을 수 있다.

    constitution 은 검사 결과가 아니라 설치 상태지만, 틀린 규칙으로 main 에 합치는 것을
    막아야 하므로 같이 넣는다(버전이 뒤처진 동결일 때만. 같은 버전 편집은 막지 않는다).
    """
    results["full-test"] = check_full_test(langs)
    results["constitution"] = not COUNTS.get("constitution_behind")
    results["guards"] = check_guards()
    results["read"] = check_readable()
    blocking = [n for n in ("collect", "print", "trace", "full-test",
                            "constitution", "guards", "read")
                if not results[n]]
    if blocking:
        print(f"[gate] FAIL — 차단: {', '.join(blocking)} (security·size는 차단하지 않는다)")
        return 1
    print("[gate] PASS")
    return 0


def main():
    gate, record, score, target = _parse_args(sys.argv[1:])
    if "--constitution-diff" in sys.argv[1:]:
        return constitution_diff()
    if "--log-summary" in sys.argv[1:]:
        return log_summary()

    # 헌법 동결은 제품 언어와 무관하다. 언어 미감지로 조기 반환하기 전에 먼저 본다 —
    # --record-full-test 만 돌릴 때는 조용해야 하므로 그때는 건너뛴다.
    if not record:
        check_constitution()

    langs = detect_langs()
    if not langs:
        return _run_without_langs(langs, gate, record, score)

    print(f"[lang] {', '.join(langs)}")
    if record:
        record_full_test(langs)
        return 0

    # 검사는 어느 모드에서나 전부 돌고 전부 출력한다. 모드는 exit code만 바꾼다.
    # gate 와 score 는 둘 다 "방금 끝난 단계" 시점에 돈다. doc 축(_doc_gap)이 현재 단계를
    # 포함하므로 trace 도 같은 창을 써야 한다 — 안 그러면 두 축이 다른 기준으로 채점된다.
    results = {
        "collect": collect_tests(langs, target),
        "print": scan_print(langs),
        "security": scan_security(langs),
        "size": scan_size(langs),
        "trace": scan_trace(include_current=(gate or score)),
    }
    if score:
        # 점수는 아무것도 막지 않는다. 판정(pass/retry/escalate)만 남기고 exit 0.
        write_score(compute_score(langs))
        return 0
    if not gate:
        # 기본 모드는 개발 중 아무 때나 돌리는 용도라 전체 실행 신선도를 보지 않는다.
        return 0 if all(results.values()) else 1
    return _run_gate(results, langs)


if __name__ == "__main__":
    sys.exit(main())
