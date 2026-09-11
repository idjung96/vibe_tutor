"""선택적 자가점검 헬퍼 (개발 도구 — 제품 런타임 코드가 아니다).

역할이 'done'을 말하기 전에 스스로 돌려 봐도 된다. 강제는 아니다.
읽기 전용이다. 파일을 고치지 않는다.

사용법(프로젝트 루트에서):
    python3 dev-agent-team/selfcheck.py                          # 언어 감지 후 전체 점검
    python3 dev-agent-team/selfcheck.py --gate                   # 단계 병합 게이트 (아래 참조)
    python3 dev-agent-team/selfcheck.py --record-full-test       # FULL 테스트 통과 상태를 기록
    python3 dev-agent-team/selfcheck.py --score                  # 산출물 점수 -> SCORE.json (아래 참조)
    python3 dev-agent-team/selfcheck.py tests/stage_1_test.py    # 특정 테스트만 수집 확인
    (Windows에 python3 가 없으면 python 으로 부른다.)

--gate 는 단계가 checker PASS를 받은 뒤 merge 전에 도는 모드다. 검사는 모두 그대로 하되
exit code는 결정적 3종(collect / print / trace)만 반영한다. security 와 size 는 각각
"후보"와 "근사"라 잘못 막을 수 있어 출력만 하고 차단하지 않는다.
게이트에서는 방금 끝난 단계도 완료로 보고 R번호 추적성을 판정한다.
게이트는 full-test 도 본다 — checker 를 FULL 로 돌리고 --record-full-test 로 기록한 뒤
코드나 테스트가 바뀌었으면 차단한다. 루프에서 선별 실행만 하고 merge 하는 것을 막는 장치다.

--score 는 코드와 문서에 축별 0~100 점을 매겨 dev-agent-team/SCORE.json 에 남긴다.
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
    ".git", "logs", "common", "tests", "dev-agent-team",
    "__pycache__", ".pytest_cache", ".venv", "venv",
    # 의존성·빌드 산출물 — 제품 코드가 아니다.
    "node_modules", "target", "vendor", "dist", "build", ".next", "coverage",
    # 에이전트 오버레이 — 하니스 설정이지 제품 코드가 아니다(.opencode/plugins/guard.js 등).
    ".claude", ".opencode", ".codex", ".agents",
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
# 각 스캔이 건수를 남긴다. 반환값(bool)은 건드리지 않는다 — 게이트 동작이 바뀌면 안 된다.
COUNTS = {}
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
    """소스를 읽는다. 못 읽으면 None."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


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
        return True
    plan = _read_plan()
    if plan is None:
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
        return plan["stages"], int(plan.get("current_stage", 1))
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
    except OSError:
        body = b""
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


def write_score(scores):
    """SCORE.json 을 쓰고 재시도 판정을 낸다. 직전 점수와 비교해야 '나아지는 중인지' 안다."""
    # 추세는 SCORE.json 안에 누적한다. TEST_LOG 에 열을 하나 더 만들지 않은 이유는,
    # 열 추가가 옛 프로젝트 마이그레이션(awk·PowerShell 양쪽)을 또 부르기 때문이다.
    # 여기에 담으면 마이그레이션 없이 같은 것을 얻는다. lead 가 회고에서 읽는다.
    prev, history = None, []
    if SCORE_PATH.is_file():
        try:
            old = json.loads(SCORE_PATH.read_text(encoding="utf-8"))
            prev = old.get("total")
            history = old.get("history") or []
        except (json.JSONDecodeError, OSError):
            prev, history = None, []

    # overall 은 '가장 나쁜 축'이라 보고용으로 좋지만, 진전 판정에는 못 쓴다 —
    # 최저가 아닌 축을 고치면 overall 이 그대로여서 개선을 안 한 것처럼 보인다.
    # 그래서 진전은 축 합계(total)로 본다. 어느 축이 나아지든 움직인다.
    overall = min(scores.values())
    total = sum(scores.values())
    below = sorted(k for k, v in scores.items() if v < SCORE_PASS)
    delta = None if prev is None else total - prev

    if not below:
        verdict = "pass"
    elif delta is not None and delta < SCORE_MIN_GAIN:
        verdict = "escalate"      # 다시 시켜도 안 오른다 — Owner에게 올린다
    else:
        verdict = "retry"

    stage = None
    if PLAN_PATH.is_file():
        plan = _read_plan()
        if plan is not None:
            stage = plan[1]

    history = (history + [{"stage": stage, "total": total, "verdict": verdict}])[-SCORE_HISTORY:]
    out = {"stage": stage, "scores": scores, "overall": overall, "total": total,
           "below": below, "prev_total": prev, "delta": delta, "verdict": verdict,
           "history": history}
    SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORE_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("[score] " + "  ".join(f"{k}={v}" for k, v in sorted(scores.items())))
    print(f"[score] 최저축={overall} (기준 {SCORE_PASS})  합계={total}"
          + (f" 직전합계={prev} 변화={delta:+d}" if delta is not None else " 직전=없음"))
    if verdict == "pass":
        print("[score] PASS — 모든 축이 기준 이상이다.")
    elif verdict == "retry":
        print(f"[score] RETRY — 기준 미달: {', '.join(below)}. 격차를 주고 다시 시킨다.")
    else:
        print(f"[score] ESCALATE — 기준 미달({', '.join(below)})인데 합계가 직전 대비 "
              f"{SCORE_MIN_GAIN}점도 오르지 않았다. 더 시키지 말고 Owner에게 올린다(C등급).")
    return out


def main():
    args = sys.argv[1:]
    gate = "--gate" in args
    record = "--record-full-test" in args
    score = "--score" in args
    rest = [a for a in args if not a.startswith("--")]
    target = rest[0] if rest else None

    langs = detect_langs()
    if not langs:
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

    print(f"[lang] {', '.join(langs)}")
    if record:
        record_full_test(langs)
        return 0

    # 검사는 어느 모드에서나 전부 돌고 전부 출력한다. 모드는 exit code만 바꾼다.
    results = {
        "collect": collect_tests(langs, target),
        "print": scan_print(langs),
        "security": scan_security(langs),
        "size": scan_size(langs),
        "trace": scan_trace(include_current=gate),
    }
    if score:
        # 점수는 아무것도 막지 않는다. 판정(pass/retry/escalate)만 남기고 exit 0.
        write_score(compute_score(langs))
        return 0

    if not gate:
        # 기본 모드는 개발 중 아무 때나 돌리는 용도라 전체 실행 신선도를 보지 않는다.
        return 0 if all(results.values()) else 1

    results["full-test"] = check_full_test(langs)
    # 게이트: 결정적 4종만 차단한다. security(후보)·size(근사)는 잘못 막을 수 있다.
    blocking = [n for n in ("collect", "print", "trace", "full-test") if not results[n]]
    if blocking:
        print(f"[gate] FAIL — 차단: {', '.join(blocking)} (security·size는 차단하지 않는다)")
        return 1
    print("[gate] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
