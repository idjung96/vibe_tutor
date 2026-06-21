"""선택적 자가점검 헬퍼 (개발 도구 — 제품 런타임 코드가 아니다).

역할이 'done'을 말하기 전에 스스로 돌려 봐도 된다. 강제는 아니다.
읽기 전용이다. 파일을 고치지 않는다.

사용법(프로젝트 루트에서):
    python dev-agent-team/selfcheck.py                          # 테스트 수집 + print + 보안 점검
    python dev-agent-team/selfcheck.py tests/stage_1_test.py    # 특정 테스트만 수집 확인

하는 일(모두 읽기 전용):
1. pytest --collect-only 로 테스트가 수집되는지 본다(문법/임포트 오류 조기 발견).
2. 제품 코드에서 print( 사용처를 찾는다(logging-rule 위반 후보).
3. 보안 패턴을 스캔한다(하드코딩 비밀값·위험 호출). 정규식 기반의 결정적 검사라
   작은 모델에서도 안전하게 쓸 수 있다(주관 판단 없음).
"""
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "logs", "common", "tests", "dev-agent-team",
    "__pycache__", ".pytest_cache", ".venv", "venv",
}

# 하드코딩 비밀값 의심: key/secret/token/password 등에 문자열 리터럴을 바로 대입.
# os.environ/설정에서 읽으면(= 따옴표로 시작 안 함) 걸리지 않는다.
SECRET_PATTERNS = [
    r'(?i)(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key)'
    r'\s*[=:]\s*["\'][^"\']+["\']',
]
# 위험 호출.
DANGER_PATTERNS = [
    (r'\beval\s*\(', 'eval'),
    (r'\bexec\s*\(', 'exec'),
    (r'\bos\.system\s*\(', 'os.system'),
    (r'shell\s*=\s*True', 'subprocess shell=True'),
    (r'\bpickle\.loads?\s*\(', 'pickle 역직렬화'),
]


def collect_tests(target):
    """pytest --collect-only 로 테스트 수집 가능 여부를 확인한다."""
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


def scan_print():
    """제품 코드에서 print( 사용처를 찾는다. common/ tests/ 등은 제외한다."""
    hits = []
    for path in Path(".").rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if "print(" in line:
                hits.append(f"{path}:{num}: {stripped}")
    if hits:
        print(f"[print] {len(hits)}건 발견 (logger 사용 권장):")
        for hit in hits:
            print("  " + hit)
    else:
        print("[print] 0건")
    return not hits


def scan_security():
    """제품 코드에서 보안 위험 패턴을 찾는다. common/ tests/ 등은 제외한다."""
    hits = []
    for path in Path(".").rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if any(re.search(pat, line) for pat in SECRET_PATTERNS):
                hits.append(f"{path}:{num}: 하드코딩 비밀값 의심: {stripped}")
            for pat, name in DANGER_PATTERNS:
                if re.search(pat, line):
                    hits.append(f"{path}:{num}: 위험 호출({name}): {stripped}")
    if hits:
        print(f"[security] {len(hits)}건 발견:")
        for hit in hits:
            print("  " + hit)
    else:
        print("[security] 0건")
    return not hits


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    ok_collect = collect_tests(target)
    ok_print = scan_print()
    ok_security = scan_security()
    return 0 if (ok_collect and ok_print and ok_security) else 1


if __name__ == "__main__":
    sys.exit(main())
