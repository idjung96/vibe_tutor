#!/usr/bin/env python3
"""렌더된 절차(team-dev SKILL)의 무결성을 기계로 본다.

    python3 tests/test_procedure.py [설치트리]

왜 있나: 절차를 고칠 때마다 단계를 끼워 넣는데, **끼워 넣은 단계로 아무도 안 보내는 일**이
생긴다. 실제로 12b-1(완료 백로그 아카이브 이관)이 그랬다 — 정의는 있는데 12번의 출구가
12c 로 바로 뛰어서 영영 안 돌았다. 그게 막으려던 것이 바로 "백로그가 쌓이기만 하는 것"이라,
고아가 된 순간 문제가 조용히 계속된다.

또 하나: 한국어에서 파이썬 `\\b` 는 경계를 안 만든다(한글이 \\w 다). `\\bcritic\\b` 가
"critic을" 에 안 맞아 이 감사를 손으로 짤 때마다 헛돌았다. 라틴 문자 경계로 판정한다.

pytest 를 쓰지 않는다 — 이 저장소의 tests/ 는 의존성 없이 도는 것이 규칙이다.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLES = ["planner", "tester", "coder", "checker", "documenter", "designer",
         "lead", "reviewer", "critic", "security"]
STEP_RE = re.compile(r"^(\d+[a-z]?(?:-\d+[a-z]?)?)\.\s", re.M)

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")
        for line in str(detail).splitlines()[:8]:
            print(f"        {line}")


def word(token, text):
    """한글이 붙어 있어도 맞게 판정한다. `\\b` 는 한글에서 경계를 안 만든다."""
    return re.search(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text)


def steps_of(text):
    """(번호, 본문) 목록을 문서 순서대로."""
    hits = [(m.group(1), m.start()) for m in STEP_RE.finditer(text)]
    out = []
    for i, (num, pos) in enumerate(hits):
        end = hits[i + 1][1] if i + 1 < len(hits) else len(text)
        out.append((num, text[pos:end]))
    return out


def test_all(tree):
    skill = (tree / ".claude/skills/team-dev/SKILL.md").read_text(encoding="utf-8")
    sc = (tree / "dev-agent-team/selfcheck.py").read_text(encoding="utf-8")
    steps = steps_of(skill)
    nums = [n for n, _ in steps]

    print("\n[절차가 부르는 것이 실재하나]")
    flags = sorted(set(re.findall(r"selfcheck\.py\s+(--[\w-]+)", skill)))
    missing = [f for f in flags if f'"{f}"' not in sc]
    check(f"selfcheck 플래그 {len(flags)}종이 전부 구현돼 있다", not missing, missing)

    installed = sorted(p.stem for p in (tree / ".claude/agents").glob("*.md"))
    called = [r for r in ROLES
              if any(word(r, ln) for ln in skill.splitlines()
                     if re.search(r"호출|부른다|돌린다", ln))]
    check("절차가 부르는 역할이 전부 설치돼 있다",
          all(r in installed for r in called), [r for r in called if r not in installed])
    check("설치된 역할이 전부 절차에서 불린다",
          all(r in called for r in installed), [r for r in installed if r not in called])

    print("\n[단계 번호가 서로를 옳게 가리키나]")
    refs = set(re.findall(r"(\d+[a-z]?(?:-\d+[a-z]?)?)\s*번(?:으로|에|을|이|,|\s|\)|다)", skill))
    dangling = sorted(r for r in refs if r not in nums)
    check("가리키는 단계 번호가 전부 실재한다", not dangling, dangling)
    check("단계 번호가 중복되지 않는다", len(nums) == len(set(nums)),
          [n for n in nums if nums.count(n) > 1])

    print("\n[끼워 넣은 단계가 고아가 아닌가]")
    # 앞 단계가 **명시적으로 다른 번호로 점프**하면 바로 뒤 단계는 건너뛰어진다.
    # 그 단계를 아무도 가리키지 않으면 영영 안 돈다.
    # 점프에도 두 종류가 있다. **조건부**("… 없으면 7번으로 간다")는 다음 단계를 건너뛰지
    # 않는다 — 조건이 아닐 때 그대로 흘러간다. **종료**("12c로." 한 줄)만 건너뛴다.
    # 둘을 안 가르면 멀쩡한 단계가 고아로 찍히고, 오탐이 나는 검사는 곧 무시된다.
    COND = ("면", "때", "YES", "NO", "아니")
    JUMP = re.compile(r"(\d+[a-z]?(?:-\d+[a-z]?)?)\s*(?:번으로 간다|번으로|로\.)")

    def terminal_jumps(body):
        """조건 없이 딴 데로 보내는 점프만 모은다(줄 단위로 판정한다)."""
        out = set()
        for line in body.splitlines():
            for m in JUMP.finditer(line):
                head = line[:m.start()]
                if not any(c in head for c in COND):
                    out.add(m.group(1))
        return out

    orphans = []
    for i in range(1, len(steps)):
        num, _ = steps[i]
        prev_num, prev_body = steps[i - 1]
        jumps = terminal_jumps(prev_body)
        if not jumps or num in jumps:
            continue                      # 순차 진행이거나 바로 뒤를 가리킨다
        # 앞이 딴 데로 보낸다. 다른 곳에서 이 단계를 가리키는가?
        elsewhere = any(word(num, b) for n, b in steps if n != num)
        if not elsewhere:
            orphans.append(f"{num} (앞 단계 {prev_num} 이(가) {sorted(jumps)} 로 보낸다)")
    check("정의만 되고 아무도 보내지 않는 단계가 없다", not orphans, orphans)


def main():
    tree = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    tmp = None
    if tree is None:
        tmp = tempfile.mkdtemp()
        tree = Path(tmp) / "proj"
        r = subprocess.run(["bash", str(ROOT / "init.sh"), "--profile", "large",
                            "--agent", "claude", str(tree)],
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0:
            print("SKIP: 설치 실패")
            return 0
    print(f"[절차 무결성] {tree}")
    test_all(tree)
    print(f"\n[절차 무결성] PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
