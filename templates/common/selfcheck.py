"""선택적 자가점검 헬퍼 (개발 도구 — 제품 런타임 코드가 아니다).

역할이 'done'을 말하기 전에 스스로 돌려 봐도 된다. 강제는 아니다.
읽기 전용이다. 파일을 고치지 않는다.

사용법:
    python -m common.selfcheck                          # 테스트 수집 + print 사용 점검
    python -m common.selfcheck tests/stage_1_test.py    # 특정 테스트만 수집 확인

하는 일(둘 다 읽기 전용):
1. pytest --collect-only 로 테스트가 수집되는지 본다(문법/임포트 오류 조기 발견).
2. 제품 코드에서 print( 사용처를 찾는다(logging-rule 위반 후보).
"""
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "logs", "common", "tests", "dev-agent-team",
    "__pycache__", ".pytest_cache", ".venv", "venv",
}


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


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    ok_collect = collect_tests(target)
    ok_print = scan_print()
    return 0 if (ok_collect and ok_print) else 1


if __name__ == "__main__":
    sys.exit(main())
