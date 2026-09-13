#!/usr/bin/env python3
"""selfcheck.py 의 판정 로직 테스트 (저장소 개발용).

    python3 tests/test_selfcheck.py

왜 있나: `write_score()` 와 `main()` 이 40줄 기준을 넘겨 쪼개야 하는데, 그 둘은 이 세션에서
여러 번 실측으로 다듬은 판정 로직이다(권고 축, 조기 탈출 조건, 진동 방지, plan_broken).
리팩터링으로 조용히 바뀌면 알아챌 방법이 없으므로 **먼저 현재 동작을 고정**한다.

pytest 를 쓰지 않는다 — 이 저장소의 tests/ 는 의존성 없이 도는 것이 규칙이고
(verify_hooks.sh·verify_parity.py), 대상인 selfcheck.py 자체도 표준 라이브러리만 쓴다.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELFCHECK = ROOT / "templates" / "project" / "selfcheck.py"

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")
        for line in str(detail).splitlines():
            print(f"        {line}")


def load_module():
    """selfcheck.py 를 모듈로 읽는다. 경로 상수가 cwd 기준이라 호출 전에 chdir 해야 한다."""
    # templates/ 에 __pycache__ 를 남기지 않는다 — 저장소 트리를 테스트가 더럽히면 안 된다.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("selfcheck_under_test", SELFCHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── write_score: 판정 로직 ──────────────────────────────────────────────────
FULL = {"test": 100, "rule": 100, "trace": 100, "doc": 100, "size": 100}


def score_case(mod, tmp, scores, prev_state=None, plan_broken=False, plan=None):
    """SCORE.json 을 prev_state 로 깔아 두고 write_score 를 한 번 돌린다."""
    os.chdir(tmp)
    sp = Path("dev-agent-team/SCORE.json")
    sp.parent.mkdir(parents=True, exist_ok=True)
    if prev_state is None:
        sp.unlink(missing_ok=True)
    elif isinstance(prev_state, str):
        sp.write_text(prev_state, encoding="utf-8")       # 깨진 파일 주입용
    else:
        sp.write_text(json.dumps(prev_state), encoding="utf-8")
    Path("dev-agent-team/PLAN.json").unlink(missing_ok=True)
    if plan is not None:
        Path("dev-agent-team/PLAN.json").write_text(json.dumps(plan), encoding="utf-8")
    mod.COUNTS.clear()
    if plan_broken:
        mod.COUNTS["plan_broken"] = True
    return mod.write_score(dict(scores))


def test_write_score(mod, tmp):
    print("\n[write_score]")

    out = score_case(mod, tmp, FULL)
    check("첫 채점·전부 통과 -> pass", out["verdict"] == "pass" and out["delta"] is None, out)

    out = score_case(mod, tmp, {**FULL, "rule": 50})
    check("첫 채점·미달 -> retry(escalate 아님)", out["verdict"] == "retry", out)

    prev = {"total": 450, "verdict": "retry"}
    out = score_case(mod, tmp, {**FULL, "rule": 50}, prev)      # total 450 -> 변화 0
    check("재시도 중·개선 없음 -> escalate", out["verdict"] == "escalate", out)

    out = score_case(mod, tmp, {**FULL, "rule": 60}, prev)      # total 460 -> +10
    check("재시도 중·개선 있음 -> retry", out["verdict"] == "retry", out)

    out = score_case(mod, tmp, {**FULL, "rule": 50}, {"total": 500, "verdict": "pass"})
    check("직전 pass·새 결함 첫 발견 -> retry", out["verdict"] == "retry", out)

    out = score_case(mod, tmp, {**FULL, "rule": 50}, {"total": 450, "verdict": "escalate"})
    check("직전 escalate·개선 없음 -> escalate(진동 없음)", out["verdict"] == "escalate", out)

    out = score_case(mod, tmp, {**FULL, "size": 50})
    check("권고 축(size)만 미달 -> pass", out["verdict"] == "pass" and out["below"] == [], out)
    check("권고 축은 최저축에서 빠진다", out["overall"] == 100, out)
    check("권고 축도 합계에는 들어간다", out["total"] == 450, out)

    out = score_case(mod, tmp, FULL, plan_broken=True)
    check("plan_broken -> escalate", out["verdict"] == "escalate", out)
    check("plan_broken 표시와 below", out.get("plan_broken") is True
          and sorted(out["below"]) == ["doc", "trace"], out)

    out = score_case(mod, tmp, FULL, "이건 JSON 이 아니다")
    check("SCORE.json 이 깨져 있어도 죽지 않는다", out["verdict"] == "pass", out)

    long_hist = [{"stage": 1, "total": 1, "verdict": "pass"}] * (mod.SCORE_HISTORY + 5)
    out = score_case(mod, tmp, FULL, {"total": 500, "verdict": "pass", "history": long_hist})
    check(f"history 는 {mod.SCORE_HISTORY} 개로 잘린다",
          len(out["history"]) == mod.SCORE_HISTORY, len(out["history"]))

    out = score_case(mod, tmp, FULL, None, plan={"stages": [{"id": 1}], "current_stage": 3})
    check("stage 는 PLAN 의 current_stage 를 쓴다", out["stage"] == 3, out)

    written = json.loads((Path(tmp) / "dev-agent-team/SCORE.json").read_text(encoding="utf-8"))
    check("SCORE.json 에 그대로 기록된다", written["verdict"] == out["verdict"], written)


# ── main: CLI 동작 ─────────────────────────────────────────────────────────
def run(tmp, *args):
    # 실제 설치와 같은 자리에서 돌린다. 루트에 두면 selfcheck 가 자기 자신을 제품 코드로
    # 스캔한다(dev-agent-team/ 은 SKIP_DIRS 라 실제로는 그럴 일이 없다).
    r = subprocess.run([sys.executable, "dev-agent-team/selfcheck.py", *args],
                       cwd=tmp, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def make_project(tmp, lang=True):
    (tmp / "dev-agent-team").mkdir(parents=True, exist_ok=True)
    (tmp / "tests").mkdir(exist_ok=True)
    (tmp / "src").mkdir(exist_ok=True)
    (tmp / "dev-agent-team/selfcheck.py").write_bytes(SELFCHECK.read_bytes())
    if lang:
        (tmp / "go.mod").write_text("module x\n\ngo 1.21\n", encoding="utf-8")
        (tmp / "src/a.go").write_text("package main\n\nfunc F() int { return 1 }\n", encoding="utf-8")
        (tmp / "tests/a_test.go").write_text(
            'package main\n\nimport "testing"\n\nfunc TestR1_X(t *testing.T) {}\n', encoding="utf-8")
        (tmp / "README.md").write_text("# p\n- R1: 한다\n", encoding="utf-8")
        (tmp / "dev-agent-team/REQUIREMENTS.md").write_text("- R1: 한다\n", encoding="utf-8")
        (tmp / "dev-agent-team/PLAN.json").write_text(
            json.dumps({"current_stage": 1, "stages": [{"id": 1, "covers": ["R1"]}]}), encoding="utf-8")


def test_main():
    print("\n[main]")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        make_project(tmp, lang=False)
        rc, out = run(tmp, "--gate")
        check("언어 미감지 -> gate PASS, exit 0", rc == 0 and "[gate] PASS" in out, out)
        rc, out = run(tmp, "--score")
        check("언어 미감지 -> score SKIP, exit 0", rc == 0 and "[score] SKIP" in out, out)
        rc, out = run(tmp, "--record-full-test")
        check("--record-full-test 는 헌법 검사를 찍지 않는다",
              rc == 0 and "[constitution]" not in out, out)

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        make_project(tmp)
        run(tmp, "--record-full-test")
        rc, out = run(tmp, "--gate")
        check("정상 프로젝트 -> gate PASS", rc == 0 and "[gate] PASS" in out, out)
        check("헌법 정상 -> [constitution] OK", "[constitution] OK" in out, out)

        (tmp / "src/bad.go").write_text(
            'package main\n\nimport "fmt"\n\nfunc B() { fmt.Println("x") }\n', encoding="utf-8")
        rc, out = run(tmp, "--gate")
        check("print 위반 + 신선도 깨짐 -> gate FAIL", rc == 1 and "[gate] FAIL" in out, out)
        check("차단 목록에 print·full-test", "print" in out and "full-test" in out, out)
        rc, out = run(tmp, "--score")
        check("--score 는 같은 상태에서도 exit 0 (차단하지 않는다)", rc == 0, out)

        (tmp / "AGENTS.md").write_text("HARNESS_VERSION: 1.0.0\n", encoding="utf-8")
        (tmp / "AGENTS.md.new").write_text("HARNESS_VERSION: 2.0.0\n", encoding="utf-8")
        rc, out = run(tmp, "--score")
        check("헌법 동결 -> [constitution] 동결 보고", "동결" in out and "1.0.0" in out, out)
        rc, out = run(tmp, "--gate")
        check("버전 뒤처진 동결 -> 게이트가 막는다",
              rc == 1 and "constitution" in out.split("[gate] FAIL")[-1], out)
        # 같은 버전에서 편집만 한 경우는 기능 불일치가 아니므로 막지 않는다.
        (tmp / "AGENTS.md").write_text("HARNESS_VERSION: 2.0.0\n# 우리 규칙\n", encoding="utf-8")
        rc, out = run(tmp, "--gate")
        check("같은 버전 편집 -> 게이트를 막지 않는다",
              "constitution" not in out.split("[gate]")[-1], out)

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        make_project(tmp)
        (tmp / "dev-agent-team/PLAN.json").write_text("{ broken", encoding="utf-8")
        rc, out = run(tmp, "--score")
        check("PLAN 깨짐 -> escalate, 만점 아님", rc == 0 and "ESCALATE" in out, out)
        (tmp / "dev-agent-team/PLAN.json").write_text(
            json.dumps({"stages": "리스트 아님", "current_stage": 1}), encoding="utf-8")
        rc, out = run(tmp, "--score")
        check("stages 타입 오류 -> 크래시 안 함", rc == 0 and "Traceback" not in out, out)


def test_constitution_diff():
    print("\n[--constitution-diff]")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        make_project(tmp)
        rc, out = run(tmp, "--constitution-diff")
        check("동결 아님 -> 비교할 것 없다", rc == 0 and "동결된 헌법이 없다" in out, out)

        (tmp / "AGENTS.md").write_text(
            "HARNESS_VERSION: 1.0.0\n\n1. 첫째 규칙이다.\n2. 둘째 규칙이다.\n"
            "\n## 우리 팀 규칙\n금요일엔 배포하지 않는다.\n", encoding="utf-8")
        (tmp / "AGENTS.md.new").write_text(
            "HARNESS_VERSION: 2.0.0\n\n1. 첫째 규칙이다.\n2. 둘째 규칙인데 내용이 바뀌었다.\n"
            "3. 셋째 규칙이 새로 생겼다.\n", encoding="utf-8")
        rc, out = run(tmp, "--constitution-diff")
        check("버전 범위를 낸다", "v1.0.0 -> v2.0.0" in out, out)
        check("바뀐 규칙만 짚는다(2번)", "내용이 바뀐 규칙: 2번" in out, out)
        check("새로 생긴 규칙을 짚는다(3번)", "새로 생긴 규칙:   3번" in out, out)
        check("Owner 가 넣은 줄만 고른다",
              "금요일엔 배포하지 않는다." in out and "첫째 규칙이다" not in out.split("Owner")[-1], out)


def test_log_summary():
    """회고용 TEST_LOG 요약. 전체를 읽히지 않으려고 있다.

    실제 프로젝트 로그로 만들다 두 가지를 잡았다 — 판정을 칸 전체에서 찾아 설명에 적힌
    NEW_FAIL 까지 세었고(전부 PASS 인데 14개가 FAIL 로 잡혔다), 본문에 `|` 가 든 행을
    가운데까지 쪼개려다 칸이 어긋났다.
    """
    print("\n[--log-summary]")
    log = ("# 테스트 현황\n\n"
           "| 단계 | 신규 | 누적 | 전체 결과 | 재시도 | 리뷰지적 | 커밋 |\n"
           "|---|---|---|---|---|---|---|\n"
           "| 1 (a) | 3 | 3 | PASS (NEW_FAIL 1회 뒤 통과) | 1 | 0 | c1 |\n"
           "| 2 (b) | 2 | 5 | PASS (A | B 파이프 포함) | 1 | 2 | c2 |\n"
           "| 3 (c) | 1 | 6 | FAIL (진짜 실패) | 5 | 4 | c3 |\n"
           "| 4 (d) | 1 | 7 | PASS (정상) | 5 | 6 | c4 |\n")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        make_project(tmp, lang=False)
        (tmp / "dev-agent-team/TEST_LOG.md").write_text(log, encoding="utf-8")
        rc, out = run(tmp, "--log-summary")
        check("단계 수를 센다", rc == 0 and "단계 4개" in out, out)
        check("판정은 칸 맨 앞만 본다(설명의 NEW_FAIL 을 세지 않는다)",
              "FAIL 인 단계: 1개" in out, out)
        check("재시도 합계", "재시도: 값 있는 단계 4개 합계 12" in out, out)
        check("전반→후반 추세를 낸다", "전반 평균" in out and "늘어남" in out, out)
        check("최근 단계를 원문으로 보여준다", "최근 4단계" in out, out)
        check("본문에 | 가 든 행도 칸이 안 어긋난다",
              "재시도 1 | 리뷰지적 2" in out, out)

        (tmp / "dev-agent-team/TEST_LOG.md").unlink()
        rc, out = run(tmp, "--log-summary")
        check("TEST_LOG 가 없어도 죽지 않는다", rc == 0 and "없다" in out, out)


def main():
    print("[selfcheck 테스트]")
    cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as d:
            mod = load_module()
            test_write_score(mod, d)
    finally:
        os.chdir(cwd)
    test_main()
    test_constitution_diff()
    test_log_summary()
    print(f"\n[selfcheck 테스트] PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
