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
import re
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
    # 실제 설치본에는 가드 훅이 늘 있다. 게이트의 [guards] 검사가 이걸 본다.
    hooks = tmp / "dev-agent-team/hooks"
    hooks.mkdir(exist_ok=True)
    for name in ("protect_tests.sh", "block_on_owner_question.sh"):
        (hooks / name).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
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


def test_guards():
    """가드 스크립트가 사라지면 게이트가 막는가.

    훅이 실행에 실패하면(파일이 없으면) 도구 호출은 그냥 진행된다 — 안전장치가 조용히
    죽는다. 설치 검증은 설치 때만 도니 그 사이를 게이트가 봐야 한다.
    """
    print("\n[guards]")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        make_project(tmp)
        hooks = tmp / "dev-agent-team/hooks"
        run(tmp, "--record-full-test")
        rc, out = run(tmp, "--gate")
        check("가드가 있으면 [guards] OK", "[guards] OK" in out, out)

        (hooks / "protect_tests.sh").unlink()
        rc, out = run(tmp, "--gate")
        check("가드가 없으면 게이트가 막는다",
              rc == 1 and "guards" in out.split("[gate] FAIL")[-1], out)
        check("무엇이 없는지 짚는다", "protect_tests.sh" in out, out)

        (hooks / "protect_tests.sh").write_text("", encoding="utf-8")
        rc, out = run(tmp, "--gate")
        check("빈 파일도 없는 것으로 본다", "[guards] FAIL" in out, out)

        (hooks / "protect_tests.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (tmp / ".opencode/plugins").mkdir(parents=True)
        rc, out = run(tmp, "--gate")
        check("opencode 설치본이면 guard.js 도 본다",
              "[guards] FAIL" in out and "guard.js" in out, out)


def test_unreadable():
    """읽지 못한 소스를 조용히 건너뛰지 않는가.

    예전엔 건너뛰었다. 그러면 그 파일의 print 위반이 사라져 게이트가 "0건" 이라고
    보고한다 — 못 읽은 것을 깨끗하다고 말하는 것이다. CP949 로 저장된 한글 소스와
    권한 없는 파일에서 실제로 그랬다.
    """
    print("\n[읽지 못한 소스]")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        make_project(tmp)
        (tmp / "requirements.txt").write_text("", encoding="utf-8")
        run(tmp, "--record-full-test")
        rc, out = run(tmp, "--gate")
        check("정상이면 [read] OK", "[read] OK" in out, out)

        bad = tmp / "src/legacy.py"
        bad.write_bytes("print('x')\n# 한글 주석".encode("cp949"))
        rc, out = run(tmp, "--gate")
        check("CP949 소스를 읽지 못하면 게이트가 막는다",
              rc == 1 and "read" in out.split("[gate] FAIL")[-1], out)
        check("어느 파일인지 짚는다", "legacy.py" in out and "UnicodeDecodeError" in out, out)
        check("파일당 한 번만 보고한다(스캐너마다 중복 아님)",
              out.count("legacy.py: UnicodeDecodeError") == 1, out)

        bad.write_text("print('x')\n# 한글 주석", encoding="utf-8")
        rc, out = run(tmp, "--gate")
        check("UTF-8 로 고치면 숨어 있던 print 위반이 드러난다",
              "[read] OK" in out and "[print] 1건" in out, out)


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


def test_owner_lines_split():
    """애매한 줄을 조용히 버리지 않는가.

    Owner 줄인지 하네스 옛 문장인지는 어절 겹침으로 어림잡는다. 그 어림짐작이 실제 프로젝트에서
    "repos/ 에서는 어디로도 push 하지 않는다" 같은 **진짜 Owner 규칙 11줄**을 걸러 냈고,
    걸러진 줄은 어디에도 보고되지 않았다. 반대로 전부 옮기면 "Stage-Gate 는 쓰지 않는다" 처럼
    새 헌법과 충돌하는 옛 줄이 규칙으로 되살아난다. 그래서 활성화는 안 하되 **버리지도 않는다** —
    두 통으로 나눠 내고 설치기가 양쪽 다 보고한다.
    """
    new_text = "1. 로그는 파일과 표준출력에 남긴다.\nHARNESS_VERSION: 9.9.9\n"
    cur_text = ("HARNESS_VERSION: 1.0.0\n"
                "금요일에는 배포하지 않는다.\n"          # 겹치는 어절 없음 -> 확실
                "로그는 표준출력에만 남긴다.\n")          # '로그'·'표준출력' 겹침 -> 애매
    mod = load_module()
    sure, maybe = mod._owner_only_lines(cur_text, new_text, split=True)
    check("확실한 Owner 줄은 이관 목록에", "금요일에는 배포하지 않는다." in sure, sure)
    check("애매한 줄은 이관 목록에 없다", "로그는 표준출력에만 남긴다." not in sure, sure)
    check("애매한 줄이 사라지지 않는다", "로그는 표준출력에만 남긴다." in maybe, maybe)
    check("두 통을 합치면 한 줄도 빠지지 않는다",
          set(sure) | set(maybe) == {"금요일에는 배포하지 않는다.", "로그는 표준출력에만 남긴다."},
          (sure, maybe))
    check("버전 줄은 어느 쪽에도 안 들어간다",
          not any("HARNESS_VERSION" in l for l in sure + maybe), (sure, maybe))
    check("split=False 는 예전처럼 확실한 것만 준다",
          mod._owner_only_lines(cur_text, new_text) == sure)


RETRO_HDR = ["# 테스트 현황", "",
             "| 단계 | 신규 | 누적 | 전체 결과 | 재시도 | 리뷰지적 | 커밋 |",
             "|---|---|---|---|---|---|---|"]


def _retro(tmp, rows, drop_log=False):
    """TEST_LOG 를 깔고 --retro-check 를 돌려 출력을 준다."""
    os.chdir(tmp)
    Path("dev-agent-team").mkdir(exist_ok=True)
    log = Path("dev-agent-team/TEST_LOG.md")
    if drop_log:
        log.unlink(missing_ok=True)
    else:
        body = [f"| {n} (s) | 5 | 100 | PASS (flutter test 100/100 | x2회) | {r} | {v} | abc |"
                for n, r, v in rows]
        log.write_text("\n".join(RETRO_HDR + body) + "\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SELFCHECK), "--retro-check"],
                       capture_output=True, text=True)
    return r.stdout.strip()


def test_retro_check():
    """회고를 언제 돌릴지 **기계가** 정하는가.

    예전에는 lead 가 매 단계 회고하며 재발 신호가 있는지 스스로 봤다. 신호의 원인 중
    하나가 lead 자신의 결정(방향·단계 초점)이라, 그 경우 lead 는 신호를 못 본다.
    판정까지 맡기면 사각지대가 트리거를 먹는다.

    문턱은 실측으로 골랐다. 절대값("리뷰지적 3건 이상")으로 걸었더니 실제 프로젝트
    8단계 중 8단계에서 걸렸다 — 그 프로젝트는 단계당 리뷰지적 9~41건이 정상이었다.
    파일 수도 쓰지 않는다. 가장 나빴던 단계가 제품코드 3개로 가장 작았다.
    """
    print("\n[회고 트리거]")
    with tempfile.TemporaryDirectory() as tmp:
        yes = lambda out: out.startswith("[retro] YES")

        # 실제 프로젝트(195~202)를 그대로 재생한다. 198·201 에서만 걸려야 한다.
        real = [(195, 0, 21), (196, 1, 14), (197, 2, 17), (198, 3, 31),
                (199, 2, 9), (200, 1, 12), (201, 5, 41), (202, 1, 15)]
        fired = [real[i][0] for i in range(len(real))
                 if yes(_retro(tmp, real[:i + 1]))]
        check("실측 8단계 중 198·201 에서만 걸린다", fired == [198, 201], fired)

        check("재시도가 문턱(3)에 닿으면 걸린다", yes(_retro(tmp, [(1, 0, 5), (2, 3, 5)])))
        check("재시도 2회는 안 걸린다", not yes(_retro(tmp, [(1, 0, 5), (2, 0, 5), (3, 2, 5)])))
        check("리뷰지적 2단계 연속 증가면 걸린다",
              yes(_retro(tmp, [(1, 0, 5), (2, 0, 8), (3, 0, 12)])))
        check("한 번 올랐다 내리면 안 걸린다",
              not yes(_retro(tmp, [(1, 0, 5), (2, 0, 8), (3, 0, 6)])))
        check("리뷰지적이 커도 늘지 않으면 안 걸린다",
              not yes(_retro(tmp, [(1, 0, 40), (2, 0, 39), (3, 0, 38)])))

        # 기록이 없으면 '문제 없음' 이 아니라 회고한다(원칙 1).
        check("TEST_LOG 가 없으면 걸린다", yes(_retro(tmp, [], drop_log=True)))
        check("단계 행이 없으면 걸린다", yes(_retro(tmp, [])))
        check("마지막 단계 재시도 칸이 '-' 면 걸린다",
              yes(_retro(tmp, [(1, 0, 5), (2, "-", 5)])))
        check("리뷰지적 칸이 비어 추세를 못 재면 걸린다",
              yes(_retro(tmp, [(1, 0, "-"), (2, 0, "-"), (3, 0, "-")])))

        # 전체 결과 칸에 '|' 가 들어가도 칸 위치를 잃지 않는다(원칙 3).
        out = _retro(tmp, [(1, 0, 5), (2, 0, 8), (3, 0, 12)])
        check("본문에 | 가 있어도 재시도·리뷰지적 칸을 옳게 읽는다",
              "5 → 8 → 12" in out, out)

        check("단계가 적으면 추세는 안 보고 재시도만 본다",
              "추세는 아직 못 본다" in _retro(tmp, [(1, 0, 5)]), _retro(tmp, [(1, 0, 5)]))


def test_process_injection():
    """PROCESS.md 를 자르지 않으면서 주입만 줄이는가.

    PROCESS.md 는 이력이라 append-only 다. 그런데 역할 호출에 **전문**을 주고 있었다 —
    실측 프로젝트에서 P-규칙이 76개 1558줄까지 자랐고 coder 한 번에 1200줄 넘게 붙었다.
    보관과 주입을 나눈다. 줄이는 방법은 삭제가 아니라 통합이고, 통합도 새 항목으로
    적으면(P-3 이 P-1 을 대체한다) 원문은 파일에 남는다.
    """
    print("\n[PROCESS 주입]")
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("dev-agent-team").mkdir()
        Path("dev-agent-team/PROCESS.md").write_text(
            "# 절차 개정\n\n"
            "## P-1: 오래된 규칙\n대상: coder\n본문 A\n\n"
            "## P-2: 전체 규칙\n대상: 전체\n본문 B\n\n"
            "## P-3: 통합\n대상: coder\nP-1 을 대체한다.\n본문 C\n\n"
            "## P-4: tester 규칙\n대상: tester\n본문 D\n", encoding="utf-8")

        def run(*args):
            return subprocess.run([sys.executable, str(SELFCHECK), *args],
                                  capture_output=True, text=True).stdout

        coder = run("--process-active", "coder")
        check("대체된 P-1 은 주입되지 않는다", "본문 A" not in coder, coder)
        check("대체한 P-3 은 주입된다", "본문 C" in coder, coder)
        check("'전체' 대상은 모든 역할에 붙는다", "본문 B" in coder, coder)
        check("다른 역할 대상은 안 붙는다", "본문 D" not in coder, coder)

        tester = run("--process-active", "tester")
        check("tester 에는 tester 것과 전체만", "본문 D" in tester and "본문 B" in tester
              and "본문 C" not in tester, tester)

        check("원본 파일은 그대로다(이력 보존)",
              "본문 A" in Path("dev-agent-team/PROCESS.md").read_text(encoding="utf-8"))

        st = run("--process-stats")
        check("통계가 폐기된 것을 센다", "폐기·대체된 것 1개" in st, st)
        check("통계가 '전체' 대상을 따로 센다", "'대상: 전체' 1개" in st, st)
        check("권고 안이면 통합을 요구하지 않는다", "통합이 필요하다" not in st, st)

        # 규칙을 잔뜩 쌓으면 통합을 요구해야 한다.
        big = "# 절차 개정\n\n" + "".join(
            f"## P-{i}: 규칙\n대상: 전체\n" + "본문\n" * 20 + "\n" for i in range(1, 30))
        Path("dev-agent-team/PROCESS.md").write_text(big, encoding="utf-8")
        st = run("--process-stats")
        check("권고를 넘으면 통합을 요구한다", "통합이 필요하다" in st, st)
        check("삭제가 아니라 통합이라고 말한다", "삭제가 아니라 통합" in st, st)
        check("주입본에도 경고가 붙는다", "lead 에게 통합" in run("--process-active", "coder"))

        Path("dev-agent-team/PROCESS.md").unlink()
        check("PROCESS.md 가 없으면 조용하다", run("--process-active", "coder").strip() == "")


def test_direction_head():
    """DIRECTION.md 도 이력이다. 주입은 마지막 절만."""
    print("\n[DIRECTION 주입]")
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("dev-agent-team").mkdir()
        Path("dev-agent-team/DIRECTION.md").write_text(
            "# 방향\n\n## 단계 1\n옛 방향\n\n## 단계 2\n지난 방향\n\n"
            "## 단계 3\n지금 방향\n우선순위 A\n", encoding="utf-8")
        out = subprocess.run([sys.executable, str(SELFCHECK), "--direction-head"],
                             capture_output=True, text=True).stdout
        check("마지막 절만 준다", "지금 방향" in out and "우선순위 A" in out, out)
        check("앞 절은 안 준다", "옛 방향" not in out and "지난 방향" not in out, out)
        check("몇 줄을 뺐는지 알린다", "이력이라 주지 않았다" in out, out)
        check("원본은 그대로다(이력 보존)",
              "옛 방향" in Path("dev-agent-team/DIRECTION.md").read_text(encoding="utf-8"))
        Path("dev-agent-team/DIRECTION.md").unlink()
        out = subprocess.run([sys.executable, str(SELFCHECK), "--direction-head"],
                             capture_output=True, text=True).stdout
        check("없으면 그렇다고 말한다", "없다" in out, out)


def test_ledger():
    """긴 이력 문서를 자르지 않으면서 주입만 줄이는가.

    DECISIONS.md 는 실측 5424줄(338KB)까지 자랐고 critic 호출마다 통째로 들어갔다.
    그렇다고 최근 N단계만 잘라 주면 안 된다 — stage-2 의 "sqlite 를 쓴다" 같은 기초
    결정이 창 밖으로 나가면 critic 이 모순을 못 보고 통과시킨다(원칙 1).
    그래서 ADR 방식으로 **전체 제목 인덱스 + 최근 본문**을 준다.
    """
    print("\n[긴 이력 주입]")
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("dev-agent-team").mkdir()
        doc = ["# 결정 기록", "", "형식 설명 줄", ""]
        for st in (2, 3, 10, 11, 12):
            doc += [f"## [2026-01-01] stage-{st}: 결정 {st}", f"본문 {st}", ""]
        doc += ["## 날짜도 단계도 없는 절", "본문 X", ""]
        Path("dev-agent-team/DECISIONS.md").write_text("\n".join(doc), encoding="utf-8")

        def run(*a):
            return subprocess.run([sys.executable, str(SELFCHECK), *a],
                                  capture_output=True, text=True).stdout

        out = run("--ledger", "DECISIONS.md", "--keep", "2")
        check("최근 단계 본문은 준다", "본문 12" in out and "본문 11" in out, out)
        # 부분 일치로 판정하지 않는다 — 꼬리말의 "전문=3개" 같은 낱말이 본문 줄과 겹친다.
        body_lines = out.split("## 본문", 1)[1] if "## 본문" in out else ""
        check("옛 단계 본문은 빼고",
              "\n본문 2\n" not in body_lines and "\n본문 3\n" not in body_lines, out)
        check("**제목은 전부 준다**(옛 결정이 있다는 사실을 숨기지 않는다)",
              out.count("결정 2") and out.count("결정 3") and out.count("결정 10"), out)
        check("제목만 준 것은 표시한다", "(제목만)" in out, out)
        check("단계를 못 읽는 절은 본문째 준다(판정 불가 -> 빼지 않는다)",
              "본문 X" in out, out)
        check("머리말은 유지한다", "형식 설명 줄" in out, out)
        check("무엇을 얼마나 줬는지 알린다", "전문=" in out and "제목만=" in out, out)

        check("원본은 그대로다(이력 보존)",
              "본문 2" in Path("dev-agent-team/DECISIONS.md").read_text(encoding="utf-8"))

        wide = run("--ledger", "DECISIONS.md", "--keep", "100")
        wide_body = wide.split("## 본문", 1)[1]
        check("창이 넓으면 전부 본문",
              "\n본문 2\n" in wide_body and "(제목만)" not in wide, wide)
        check("예산을 넘기지 않는다",
              len(run("--ledger", "DECISIONS.md", "--keep", "100").splitlines()) <= 400)

        check("없는 문서는 그렇다고 말한다", "가 없다" in run("--ledger", "NOPE.md"))

        st = run("--ledger-stats")
        check("통계가 줄수·절수를 센다", "DECISIONS.md" in st and "절 6개" in st, st)


def test_ledger_stats_by_kind():
    """문서 종류마다 다른 잣대를 대는가 — 전부에 같은 경고를 울리면 늘 울린다.

    처음엔 "40줄 넘는 절" 경고를 모든 문서에 걸었더니 BACKLOG(목록)와 DESIGN(명세)까지
    걸렸다. 그 둘은 절이 긴 것이 정상이다. 늘 울리는 경보는 무시되고, 무시되는 검사는
    장식이다. 절 하나가 **한 건**인 문서(ledger)에만 크기를 따진다.
    """
    print("\n[문서 종류별 잣대]")
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("dev-agent-team").mkdir()
        long_sec = "## [2026-01-01] stage-9: 큰 결정\n" + "본문\n" * 60
        Path("dev-agent-team/DECISIONS.md").write_text("# 결정\n\n" + long_sec, encoding="utf-8")
        # 명세·목록·화면명세도 문턱을 넘겨 본다 — 넘어도 "조사" 라고 하면 안 된다.
        # DESIGN 은 단계순 ledger 지만 한 절이 화면 하나라 길어도 정상이다(잣대가 다르다).
        Path("dev-agent-team/DESIGN.md").write_text(
            "# 설계\n\n## 단계9: 화면 A\n" + "명세\n" * 1600, encoding="utf-8")
        Path("dev-agent-team/REQUIREMENTS.md").write_text(
            "# 요구사항\n\n## R1\n" + "요구\n" * 1600, encoding="utf-8")
        Path("dev-agent-team/BACKLOG.md").write_text(
            "# 백로그\n\n## 할 일\n" + "- [ ] B-1 일 · 출처:stage1/lead\n" * 600, encoding="utf-8")
        out = subprocess.run([sys.executable, str(SELFCHECK), "--ledger-stats"],
                             capture_output=True, text=True).stdout
        check("ledger(결정)는 큰 절을 지적한다", "조사가 섞여 있다" in out, out)
        check("spec(요구사항)은 '조사' 가 아니라 분할을 안내한다",
              "명세라 긴 것 자체는 정상" in out and "분할" in out, out)
        check("DESIGN(화면 명세)은 '조사' 가 아니라 아카이브를 안내한다",
              "화면·주제 하나라 긴 것은 정상" in out and "--ledger-archive DESIGN.md" in out, out)
        check("list(백로그)도 '조사' 가 아니다", "목록이라 긴 것 자체는 정상" in out, out)
        check("지적이 DECISIONS 한 곳에만 뜬다", out.count("조사가 섞여 있다") == 1, out)


def test_backlog_states():
    """칸반의 todo/doing/done 을 파일 셋이 아니라 **줄의 상태**로 센다."""
    print("\n[백로그 상태]")
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("dev-agent-team").mkdir()
        Path("dev-agent-team/PLAN.json").write_text(
            json.dumps({"current_stage": 30, "stages": [{"id": 1}]}), encoding="utf-8")
        Path("dev-agent-team/BACKLOG.md").write_text(
            "# 백로그\n\n## 할 일\n"
            "- [ ] B-1 묵은 일 · 출처:stage1/lead\n"      # 29단계 묵음 -> stale
            "- [ ] B-2 최근 일 · 출처:stage29/lead\n"     # 1단계 -> 안 묵음
            "- [~] B-3 하는 중 · 출처:stage28/lead · 진행:stage30\n"
            "- [x] B-4 끝난 일 · 출처:stage27/lead → stage29 처리\n"
            + "채우기\n" * 520, encoding="utf-8")
        out = subprocess.run([sys.executable, str(SELFCHECK), "--ledger-stats"],
                             capture_output=True, text=True).stdout
        check("대기·진행·완료를 센다", "열림 2개" in out and "완료 표시된 채 남은 것 1개" in out, out)
        check("오래 묵은 항목을 센다", "묵은 열린 항목이 1개" in out, out)
        check("완료분 이관을 시킨다", "BACKLOG_DONE.md 로 옮겨라" in out, out)
        check("현재 단계를 못 읽으면 묵음 판정을 하지 않는다(추측하지 않는다)",
              True)
        Path("dev-agent-team/PLAN.json").unlink()
        out2 = subprocess.run([sys.executable, str(SELFCHECK), "--ledger-stats"],
                              capture_output=True, text=True).stdout
        check("PLAN 이 없으면 묵음 지적이 사라진다", "묵은 열린 항목" not in out2, out2)
        check("그래도 대기·완료 수는 센다", "열림 2개" in out2, out2)


def test_ledger_budget_and_archive():
    """주입에 상한이 있는가, 그리고 파일 자체가 줄어드는가.

    제목 인덱스를 전부 주면 결정이 늘수록 주입도 같이 늘어 O(n) 이 된다 — 실측에서
    634줄 중 337줄(53%)이 이미 제목이었다. 예산 안에서 최근 것부터 채우고, 넘치면
    "그 이전 N건이 있다"는 한 줄로 접는다. 접어도 **있다는 사실은 숨기지 않는다.**

    파일은 --ledger-archive 로 **옮겨서** 줄인다. 지우지 않는다. 그리고 순서가 있다 —
    계속 유효한 제약을 PROJECT_RULES.md 로 승격한 **뒤에** 내려야 한다. 오래됐다고
    안 중요한 것이 아니다.
    """
    print("\n[주입 상한과 아카이브]")
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("dev-agent-team").mkdir()
        doc = ["# 결정 기록", ""]
        for st in range(1, 121):                      # 120건, 각 6줄
            doc += [f"## [2026-01-01] stage-{st}: 결정 {st}"] + [f"내용 {st}"] * 5 + [""]
        Path("dev-agent-team/DECISIONS.md").write_text("\n".join(doc), encoding="utf-8")

        def run(*a):
            return subprocess.run([sys.executable, str(SELFCHECK), *a],
                                  capture_output=True, text=True).stdout

        out = run("--ledger", "DECISIONS.md", "--keep", "200")
        check("결정 120건이어도 예산 안에 든다", len(out.splitlines()) <= 400, len(out.splitlines()))
        check("접은 건수를 알린다", "접음=" in out, out[-300:])
        check("접힌 것이 있다는 사실을 숨기지 않는다", "있다는 것만 알아 둬라" in out, out[:800])
        check("어디를 봐야 하는지 알려 준다", "PROJECT_RULES.md" in out, out[:800])

        # 절 하나가 예산보다 커도 상한을 지킨다(실측에 1447줄짜리 결정이 있었다).
        Path("dev-agent-team/DECISIONS.md").write_text(
            "# 결정\n\n## [2026-01-01] stage-9: 거대한 결정\n" + "줄\n" * 900, encoding="utf-8")
        out = run("--ledger", "DECISIONS.md")
        check("절 하나가 예산보다 커도 잘라서 상한을 지킨다",
              len(out.splitlines()) <= 430, len(out.splitlines()))
        check("잘랐다는 사실과 원문 위치를 말한다", "줄만 줬다" in out, out[-400:])

        # 아카이브: 옮기는 것이지 지우는 것이 아니다.
        Path("dev-agent-team/DECISIONS.md").write_text("\n".join(doc), encoding="utf-8")
        before = Path("dev-agent-team/DECISIONS.md").read_text(encoding="utf-8")
        r = run("--ledger-archive", "DECISIONS.md", "--keep", "10")
        now = Path("dev-agent-team/DECISIONS.md").read_text(encoding="utf-8")
        arc = Path("dev-agent-team/DECISIONS_ARCHIVE.md")
        check("파일이 실제로 줄어든다", len(now.splitlines()) < len(before.splitlines()) // 2,
              (len(before.splitlines()), len(now.splitlines())))
        check("아카이브 파일이 생긴다", arc.is_file(), r)
        heads = re.findall(r"^##\s+\[.*$", before, re.M)
        both = now + arc.read_text(encoding="utf-8")
        check("절이 하나도 사라지지 않는다", all(h in both for h in heads),
              [h for h in heads if h not in both][:3])
        check("원본에 어디로 옮겼는지 남는다", "DECISIONS_ARCHIVE.md 으로 옮겼다" in now, now[:400])
        check("무엇을 옮겼는지 제목을 보여 준다", "옮긴 것:" in r and "stage-" in r, r)
        check("규칙이 섞였으면 고정하라고 알려 준다", "[규칙]" in r, r)
        check("다시 돌려도 두 번 옮기지 않는다(멱등)",
              "옮길 것이 없다" in run("--ledger-archive", "DECISIONS.md", "--keep", "10"))
        check("아카이브 뒤 주입이 더 짧아진다",
              len(run("--ledger", "DECISIONS.md").splitlines()) < 200)
        check("단계 번호를 못 읽으면 옮기지 않는다(추측하지 않는다)",
              "옮기지 않는다" in (lambda: (Path("dev-agent-team/X.md").write_text(
                  "# X\n\n## 번호 없는 절\n내용\n", encoding="utf-8"),
                  run("--ledger-archive", "X.md"))[1])())


def test_design_head_is_pinned():
    """DESIGN 의 머리말은 접히지도 아카이브되지도 않는가.

    DESIGN.md 는 명세인 줄 알았는데 실물은 단계순 로그였다(24개 절 중 19개가 `단계N`).
    그래서 ledger 로 다룬다. 다만 토큰 체계처럼 **모든 화면에 적용되는 규칙**이 섞여 있다 —
    그게 단계 절에 있으면 그 단계가 아카이브될 때 같이 내려가 다음 designer 가 못 본다.
    그런 것은 머리말(첫 `##` 앞)에 둔다. 머리말은 언제나 통째로 간다.
    """
    print("\n[DESIGN 머리말 고정]")
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("dev-agent-team").mkdir()
        doc = ["# 화면 설계", "", "## 디자인 토큰(고정)", "AppFontSize 체계를 쓴다", ""]
        doc = doc[:2] + ["디자인 토큰: AppFontSize 체계를 쓴다(고정 규칙)", ""]
        for st in range(1, 60):
            doc += [f"## 단계{st}: 화면 {st}"] + [f"명세 {st}"] * 8 + [""]
        Path("dev-agent-team/DESIGN.md").write_text("\n".join(doc), encoding="utf-8")

        def run(*a):
            return subprocess.run([sys.executable, str(SELFCHECK), *a],
                                  capture_output=True, text=True).stdout

        out = run("--ledger", "DESIGN.md")
        check("머리말은 언제나 들어간다", "AppFontSize 체계를 쓴다" in out, out[:300])
        check("예산을 지킨다", len(out.splitlines()) <= 400, len(out.splitlines()))
        check("옛 단계 명세는 접힌다", "접음=" in out, out[-200:])

        run("--ledger-archive", "DESIGN.md", "--keep", "5")
        now = Path("dev-agent-team/DESIGN.md").read_text(encoding="utf-8")
        arc = Path("dev-agent-team/DESIGN_ARCHIVE.md").read_text(encoding="utf-8")
        check("아카이브해도 머리말은 원본에 남는다", "AppFontSize 체계를 쓴다" in now, now[:300])
        check("머리말이 아카이브로 내려가지 않는다", "AppFontSize" not in arc, arc[:300])
        check("옛 단계 명세는 아카이브로 내려간다", "명세 1" in arc and "## 단계1:" in arc)
        check("최근 단계 명세는 원본에 남는다", "## 단계59:" in now)
        check("아카이브 뒤에도 머리말은 주입된다",
              "AppFontSize 체계를 쓴다" in run("--ledger", "DESIGN.md"))


def test_pinned_sections():
    """`[규칙]` 절은 접히지도 아카이브되지도 않는가.

    "승격 먼저, 아카이브 나중" 은 절차 문장이라 지켜지지 않는다 — 이 저장소에서 P-규칙
    통합이 76개 중 2번뿐이었던 것과 같은 이유다. 그래서 구조로 막는다.
    실측 DESIGN.md 에 `§121 폰트 크기 토큰 체계(AppFontSize, 전역 타이포 정리)` 가
    단계 절에 있었다. 전역 규칙인데 그 단계가 아카이브되면 다음 designer 가 못 본다.

    판정은 **쓰는 사람이 단 표시**로 한다. 자유 텍스트에서 "전역"·"규칙" 을 찾아
    추측하지 않는다(원칙 2).
    """
    print("\n[고정 절]")
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("dev-agent-team").mkdir()
        doc = ["# 화면 설계", ""]
        doc += ["## [규칙] 단계121: 폰트 크기 토큰 체계", "AppFontSize 만 쓴다", ""]
        for st in range(1, 80):
            doc += [f"## 단계{st}: 화면 {st}"] + [f"명세 {st}"] * 8 + [""]
        Path("dev-agent-team/DESIGN.md").write_text("\n".join(doc), encoding="utf-8")

        def run(*a):
            return subprocess.run([sys.executable, str(SELFCHECK), *a],
                                  capture_output=True, text=True).stdout

        out = run("--ledger", "DESIGN.md")
        check("고정 절은 접히지 않고 본문째 들어간다", "AppFontSize 만 쓴다" in out, out[:600])
        check("접힌 것이 있어도 그렇다", "접음=" in out, out[-200:])
        check("예산은 그대로 지킨다", len(out.splitlines()) <= 430, len(out.splitlines()))

        r = run("--ledger-archive", "DESIGN.md", "--keep", "5")
        now = Path("dev-agent-team/DESIGN.md").read_text(encoding="utf-8")
        arc = Path("dev-agent-team/DESIGN_ARCHIVE.md").read_text(encoding="utf-8")
        check("고정 절은 아카이브로 내려가지 않는다", "AppFontSize 만 쓴다" not in arc, arc[:400])
        check("고정 절은 원본에 남는다", "AppFontSize 만 쓴다" in now, now[:400])
        check("단계 번호가 있어도 고정이면 안 내려간다", "단계121" in now and "단계121" not in arc)
        check("고정이 몇 건인지 알린다", "고정 1건" in r, r)
        check("옛 단계는 내려간다", "## 단계1:" in arc)

        check("아카이브 뒤에도 고정 절은 주입된다",
              "AppFontSize 만 쓴다" in run("--ledger", "DESIGN.md"))


def test_migrate_check():
    """하네스를 올린 뒤 기존 내용이 새 규약과 얼마나 어긋나는지 세는가.

    새 규약은 앞으로 쓸 것에만 적용된다. 규약이 안 맞으면 도구가 덜 먹는다 — 단계 번호가
    없으면 아카이브가 안 되고, `[규칙]` 이 없으면 지켜야 할 것이 로그와 함께 내려간다.
    **고치지는 않는다.** Owner 의 글을 설치기가 고쳐 쓰는 것은 이 저장소가 크게 데인 길이다.
    """
    print("\n[마이그레이션 점검]")
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("dev-agent-team").mkdir()
        Path("dev-agent-team/evidence").mkdir()
        Path("dev-agent-team/BACKLOG_DONE.md").write_text("# 완료\n", encoding="utf-8")

        def run():
            return subprocess.run([sys.executable, str(SELFCHECK), "--migrate-check"],
                                  capture_output=True, text=True).stdout

        # 규약을 지키는 상태 — 지적이 없어야 한다.
        Path("dev-agent-team/DECISIONS.md").write_text(
            "# 결정\n\n## [규칙] 로그는 common/logger 만 쓴다\n지킨다\n\n"
            + "".join(f"## [2026-01-01] stage-{i}: 결정\n한 줄\n\n" for i in range(1, 12)),
            encoding="utf-8")
        check("규약을 지키면 조용하다", "할 일 없음" in run(), run())

        # 규약을 어긴 상태를 주입한다.
        Path("dev-agent-team/DECISIONS.md").write_text(
            "# 결정\n\n" + "".join(f"## 번호 없는 결정 {i}\n한 줄\n\n" for i in range(1, 13))
            + "## [2026-01-01] stage-9: 긴 결정\n" + "조사\n" * 60, encoding="utf-8")
        out = run()
        check("단계 번호 없는 절을 센다", "단계 번호 없는 절 12건" in out, out)
        check("고정 절이 없다고 알린다", "고정 절이 하나도 없다" in out, out)
        check("긴 절을 센다", "40줄 넘는 절 1건" in out, out)
        check("어떻게 고치는지 알려 준다", "evidence" in out and "[규칙]" in out, out)
        check("자동으로 고치지 않았다고 분명히 말한다",
              "자동으로 고치지 않았다" in out, out)
        check("파일을 실제로 건드리지 않는다",
              "번호 없는 결정 1" in Path("dev-agent-team/DECISIONS.md").read_text(encoding="utf-8"))

        # 코드블록 안의 `##` 는 절이 아니다(템플릿의 형식 예시가 유령 절이 되던 것).
        Path("dev-agent-team/DECISIONS.md").write_text(
            "# 결정\n\n형식:\n\n```\n## [날짜] 단계N: 제목\n- 등급: A\n```\n\n"
            "## [규칙] 고정\n지킨다\n\n"
            + "".join(f"## [2026-01-01] stage-{i}: 결정\n한 줄\n\n" for i in range(1, 12)),
            encoding="utf-8")
        check("코드블록 안의 ## 를 절로 세지 않는다", "할 일 없음" in run(), run())

        # PROCESS 는 규칙 집합이라 단계 번호를 요구하지 않는다.
        Path("dev-agent-team/PROCESS.md").write_text(
            "# 절차\n\n" + "".join(f"## P-{i}: 개정\n대상: coder\n본문\n\n" for i in range(1, 9)),
            encoding="utf-8")
        out = run()
        check("PROCESS 에 단계 번호를 요구하지 않는다",
              "[PROCESS.md] 단계 번호" not in out, out)


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
    test_guards()
    test_unreadable()
    test_log_summary()
    test_owner_lines_split()
    test_retro_check()
    test_process_injection()
    test_direction_head()
    test_ledger()
    test_ledger_budget_and_archive()
    test_design_head_is_pinned()
    test_pinned_sections()
    test_migrate_check()
    test_ledger_stats_by_kind()
    test_backlog_states()
    print(f"\n[selfcheck 테스트] PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
