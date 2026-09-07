"""선택적 자가점검 헬퍼 (개발 도구 — 제품 런타임 코드가 아니다).

역할이 'done'을 말하기 전에 스스로 돌려 봐도 된다. 강제는 아니다.
읽기 전용이다. 파일을 고치지 않는다.

사용법(프로젝트 루트에서):
    python dev-agent-team/selfcheck.py                          # 언어 감지 후 전체 점검
    python dev-agent-team/selfcheck.py tests/stage_1_test.py    # 특정 테스트만 수집 확인(python)

하는 일(모두 읽기 전용):
1. 제품 언어를 감지한다(마커 파일 우선). python / go / rust / node 를 안다.
2. 테스트 수집 확인 — python이면 pytest --collect-only. 다른 언어는 건너뛴다
   (테스트 수집·실행은 checker가 제품 언어의 러너로 매 단계 수행한다).
3. 감지된 언어의 소스에서 print 계열 사용처를 찾는다(logging-rule 위반 후보).
4. 같은 소스에서 보안 패턴을 스캔한다(하드코딩 비밀값·위험 호출).

3·4는 정규식 기반의 결정적 검사라 작은 모델에서도 안전하게 쓸 수 있다(주관 판단 없음).
툴체인이 필요한 검사(go build / cargo check)는 느리고 네트워크·빌드 산출물을 만들어
'읽기 전용·결정적' 성격을 깨므로 하지 않는다.
"""
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "logs", "common", "tests", "dev-agent-team",
    "__pycache__", ".pytest_cache", ".venv", "venv",
    # 의존성·빌드 산출물 — 제품 코드가 아니다.
    "node_modules", "target", "vendor", "dist", "build", ".next", "coverage",
}

# 하드코딩 비밀값 의심: key/secret/token/password 등에 문자열 리터럴을 바로 대입.
# os.environ/설정에서 읽으면(= 따옴표로 시작 안 함) 걸리지 않는다. 백틱은 JS 템플릿 리터럴.
SECRET_PATTERNS = [
    r'(?i)(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key)'
    r'\s*[=:]\s*["\'`][^"\'`]+["\'`]',
]

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
            (r'\b(execSync|child_process\.exec|\.exec)\s*\(', '셸 경유 명령 실행'),
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


def iter_code_lines(langs):
    """(언어, 경로, 줄번호, 원문, 공백제거) 를 내놓는다. 주석 줄은 건너뛴다."""
    for name in langs:
        spec = LANGS[name]
        for path in iter_sources(spec["ext"]):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for num, line in enumerate(text.splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith(spec["comment"]):
                    continue
                yield name, path, num, line, stripped


def collect_tests(langs, target):
    """python이면 pytest --collect-only 로 수집 가능 여부를 확인한다."""
    if "python" not in langs:
        print("[collect] SKIP (python 아님 — 테스트 수집·실행은 checker가 제품 언어 러너로 한다)")
        return True
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    if target:
        cmd.append(target)
    proc = subprocess.run(cmd, capture_output=True, text=True)
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
        for pat in LANGS[name]["printers"]:
            if re.search(pat, line):
                hits.append(f"{path}:{num}: {stripped}")
                break
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


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    langs = detect_langs()
    if not langs:
        print("[lang] 감지된 제품 언어 없음 — 점검을 건너뛴다.")
        print("       (python/go/rust/node 만 안다. 마커: requirements.txt·pyproject.toml /")
        print("        go.mod / Cargo.toml / package.json)")
        return 0
    print(f"[lang] {', '.join(langs)}")
    ok_collect = collect_tests(langs, target)
    ok_print = scan_print(langs)
    ok_security = scan_security(langs)
    return 0 if (ok_collect and ok_print and ok_security) else 1


if __name__ == "__main__":
    sys.exit(main())
