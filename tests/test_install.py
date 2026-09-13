#!/usr/bin/env python3
"""init.sh 의 설치·재설치 동작 테스트 (저장소 개발용).

    python3 tests/test_install.py

왜 있나: 재설치가 **조용히 프로젝트를 재구성하던 버그**를 늦게 잡았다. 플래그 없이
`./init.sh <프로젝트>` 를 돌리면 프로파일을 새로 판별해서, small 로 깔아 둔 온프레미스
프로젝트가 large 로 바뀌고 codex 오버레이까지 깔렸다(역할 6개 -> 11개, RETRY_LIMIT 3 -> 5).
설치기는 Owner 의 프로젝트를 직접 고치는 코드라, 이런 건 눈으로 보지 말고 기계로 잡아야 한다.

pytest 를 쓰지 않는다 — 이 저장소의 tests/ 는 의존성 없이 도는 것이 규칙이다.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "init.sh"

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


def install(target, *args):
    r = subprocess.run(["bash", str(INIT), *args, str(target)],
                       capture_output=True, text=True, cwd=ROOT)
    return r.returncode, r.stdout + r.stderr


def shape(target):
    """설치 결과의 '구성'을 요약한다 — 프로파일과 에이전트가 바뀌면 여기가 움직인다."""
    t = Path(target)
    roles = sorted(p.stem for p in (t / ".claude/agents").glob("*.md")) \
        if (t / ".claude/agents").is_dir() else []
    agents = [n for n, f in (("claude", ".claude/settings.json"),
                             ("codex", ".codex/config.toml"),
                             ("opencode", "opencode.json")) if (t / f).is_file()]
    return {"roles": len(roles), "large_only": "lead" in roles, "agents": agents}


def test_reinstall_keeps_shape():
    print("\n[재설치가 구성을 바꾸지 않는다]")
    with tempfile.TemporaryDirectory() as d:
        tgt = Path(d) / "proj"
        install(tgt, "--profile", "small", "--agent", "claude,opencode")
        before = shape(tgt)
        check("small 설치 결과", before["roles"] == 6 and not before["large_only"]
              and before["agents"] == ["claude", "opencode"], before)

        rc, out = install(tgt)                       # 플래그 없이 재설치
        after = shape(tgt)
        check("플래그 없는 재설치가 프로파일을 바꾸지 않는다", before == after,
              f"before={before}\nafter={after}")
        check("무엇을 유지했는지 알린다", "기존 프로파일 small" in out, out)

        rc, out = install(tgt, "--profile", "large", "--agent", "all")
        grew = shape(tgt)
        check("명시한 플래그는 이긴다(small -> large)",
              grew["large_only"] and "codex" in grew["agents"], grew)

    with tempfile.TemporaryDirectory() as d:
        tgt = Path(d) / "fresh"
        rc, out = install(tgt)                       # 신규는 자동 판별 그대로
        check("신규 설치는 자동 판별한다(재설치 안내 없음)",
              rc == 0 and "재설치:" not in out, out)


def test_state_preserved():
    print("\n[재설치가 상태 파일을 건드리지 않는다]")
    with tempfile.TemporaryDirectory() as d:
        tgt = Path(d) / "proj"
        install(tgt, "--profile", "large", "--agent", "claude")
        state = {
            "dev-agent-team/BACKLOG.md": "\n## 할 일\n- [ ] B-1 남은 일\n",
            "dev-agent-team/DECISIONS.md": "\n- D1: sqlite\n",
            "dev-agent-team/PLAN.json": json.dumps({"current_stage": 2, "stages": []}),
            "README.md": "# 우리 제품\n",
        }
        for rel, extra in state.items():
            p = tgt / rel
            p.write_text((p.read_text(encoding="utf-8") if p.is_file() else "") + extra,
                         encoding="utf-8")
        snap = {rel: (tgt / rel).read_text(encoding="utf-8") for rel in state}
        install(tgt, "--profile", "large", "--agent", "claude")
        for rel, text in snap.items():
            check(f"{rel} 보존", (tgt / rel).read_text(encoding="utf-8") == text)


def test_accept_constitution():
    print("\n[--accept-constitution]")
    with tempfile.TemporaryDirectory() as d:
        tgt = Path(d) / "proj"
        install(tgt, "--profile", "small", "--agent", "claude,opencode")
        agents_md = tgt / "AGENTS.md"
        agents_md.write_text(agents_md.read_text(encoding="utf-8")
                             + "\n## 팀 규칙\n금요일 배포 금지\n", encoding="utf-8")
        install(tgt, "--profile", "small", "--agent", "claude,opencode")   # 동결 유발
        check("Owner 편집 -> .new 로 보류", (tgt / "AGENTS.md.new").is_file())

        before = shape(tgt)
        rc, out = install(tgt, "--accept-constitution")
        check("해소 후 .new 가 없다", not (tgt / "AGENTS.md.new").is_file(), out)
        check("이전 내용은 백업된다", (tgt / "AGENTS.md.owner-backup").is_file(), out)
        check("Owner 규칙이 PROJECT_RULES.md 로 이관된다",
              "금요일 배포 금지" in (tgt / "dev-agent-team/PROJECT_RULES.md").read_text(encoding="utf-8"), out)
        check("헌법이 새 규칙으로 바뀐다",
              "금요일 배포 금지" not in agents_md.read_text(encoding="utf-8"), out)
        check("구성(프로파일·에이전트)은 그대로다", shape(tgt) == before,
              f"before={before}\nafter={shape(tgt)}")

        rc, out = install(tgt, "--accept-constitution")
        check("동결이 아닐 때는 아무것도 하지 않는다", "갱신했습니다" not in out, out)


def test_brownfield():
    """이미 코드가 있는 프로젝트에 깔 때 Owner 파일을 건드리지 않는가.

    실제 Flutter 프로젝트에 설치했다가 두 가지를 늦게 잡았다 — common/logger.py 를 무조건
    덮어써 Owner 의 로거를 지웠고, 미렌더 마커 검사가 제품 PNG·.DS_Store 를 잡아 설치가
    실패로 끝났다. 빈 폴더에만 설치해 보면 둘 다 안 보인다.
    """
    print("\n[기존 프로젝트에 설치]")
    with tempfile.TemporaryDirectory() as d:
        tgt = Path(d) / "proj"
        for rel, text in (("common/logger.py", "# 우리 로거\ndef log(m): pass\n"),
                          ("tests/test_mine.py", "def test_mine(): assert True\n"),
                          ("README.md", "# 우리 제품\n"),
                          ("src/app.py", "x = 1\n"),
                          ("requirements.txt", "")):
            p = tgt / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        # 바이너리 제품 파일이 "{{" 바이트를 담고 있어도 설치 검증이 걸리면 안 된다.
        (tgt / "assets").mkdir()
        (tgt / "assets/icon.png").write_bytes(b"\x89PNG\r\n\x1a\n{{\x00\xff{{binary")
        snap = {rel: (tgt / rel).read_text(encoding="utf-8")
                for rel in ("common/logger.py", "tests/test_mine.py", "README.md", "src/app.py")}

        rc, out = install(tgt, "--profile", "large", "--agent", "claude")
        check("기존 프로젝트 설치가 성공한다(바이너리 오탐 없음)", rc == 0,
              "\n".join(l for l in out.splitlines() if "FAIL" in l))
        for rel, text in snap.items():
            check(f"{rel} 보존", (tgt / rel).read_text(encoding="utf-8") == text)
        check("logger.py 를 덮지 않았다고 알린다", "logger.py 가 이미 있어" in out, out)
        check("설치 검증이 마커 오탐을 내지 않는다",
              "렌더되지 않은 {{ 마커" not in out, out)


def test_test_log_migration():
    """옛 5열 TEST_LOG 가 7열로 올라가는가.

    실제 프로젝트에서 101행짜리 로그가 영원히 5열로 남아 있었다. 이유가 둘이었다 —
    멱등 가드가 **파일 전체**에서 "재시도" 를 찾았는데 그 단어가 29단계 설명에 있었고,
    행 변환이 **파이프 개수**로 판정해서 본문에 "|" 가 든 행은 통째로 빠졌다.
    """
    print("\n[TEST_LOG 5열 -> 7열]")
    old = ("# 테스트 현황\n\n"
           "| 단계 | 신규 | 누적 | 전체 결과 | 커밋 |\n"
           "|---|---|---|---|---|\n"
           "| 1 (infra) | 12 | 12 | PASS (평범한 행) | abc1111 |\n"
           "| 29 (pin) | 23 | 468 | PASS (B-65 재시도 로직 정리) | abc2222 |\n"
           "| 41 (kp) | 15 | 660 | PASS (A | B 파이프 포함) | abc3333 |\n")
    with tempfile.TemporaryDirectory() as d:
        tgt = Path(d) / "proj"
        (tgt / "dev-agent-team").mkdir(parents=True)
        (tgt / "dev-agent-team/TEST_LOG.md").write_text(old, encoding="utf-8")
        rc, out = install(tgt, "--profile", "large", "--agent", "claude")
        got = (tgt / "dev-agent-team/TEST_LOG.md").read_text(encoding="utf-8")

        check("본문에 '재시도' 가 있어도 마이그레이션이 돈다",
              "| 재시도 | 리뷰지적 |" in got, got)
        rows = [l for l in got.splitlines() if l.startswith("|") and "---" not in l]
        tails = [tuple(x.strip() for x in l.rstrip().rsplit("|", 4)[1:4]) for l in rows]
        check("헤더 마지막 3칸이 재시도·리뷰지적·커밋",
              tails[0] == ("재시도", "리뷰지적", "커밋"), tails)
        check("모든 데이터 행이 7열로 채워진다(본문에 | 가 든 행 포함)",
              all(t[:2] == ("-", "-") for t in tails[1:]) and len(tails) == 4, tails)
        check("구분선도 7칸", "|---|---|---|---|---|---|---|" in got, got)
        check("원본은 .bak 으로 남는다", (tgt / "dev-agent-team/TEST_LOG.md.bak").is_file())

        rc, out = install(tgt, "--profile", "large", "--agent", "claude")
        check("재설치해도 두 번 돌지 않는다(멱등)", "7열로 갱신" not in out, out)


def _freeze(tgt, version_line):
    """헌법을 Owner 가 편집한 것처럼 만들고, HARNESS_VERSION 줄을 원하는 값으로 바꾼다."""
    import re
    f = Path(tgt) / "AGENTS.md"
    t = re.sub(r"^HARNESS_VERSION: .*$", version_line, f.read_text(encoding="utf-8"),
               count=1, flags=re.M)
    f.write_text(t + "\n## 우리 팀 규칙\n금요일 배포 금지\n", encoding="utf-8")


def test_freeze_notice():
    """헌법 동결 안내가 실제로 나가는가 — 버전을 못 읽는 경우까지.

    실제 프로젝트에서 버전 표기가 없는 옛 헌법을 만났더니 두 가지가 한꺼번에 샜다.
    빈 값을 현재 버전으로 대체해 GAP=0 이 되니 "정상 동작하지 않는다" 경고가 아예 안 나갔고,
    파싱 안 되는 값이면 빈 값이 산술식에 들어가 set -e 가 함수를 중단시켰다 — 그러면 안내
    **전체**가 사라지고 Owner 는 bash 산술 오류 한 줄만 본다. manifest 기록까지 빠져서
    다음 설치가 헌법을 덮어쓴다. 못 읽은 것을 "차이 없음"으로 본 fail-open 이다.
    """
    print("\n[헌법 동결 안내]")
    cases = (("HARNESS_VERSION: 1.20.0", "버전 차이가 큽니다", "버전이 많이 뒤처짐"),
             ("(줄 없음)", "버전을 읽을 수 없습니다", "HARNESS_VERSION 줄이 없음"),
             ("HARNESS_VERSION: 구버전", "버전을 읽을 수 없습니다", "버전이 파싱 안 됨"))
    for line, want, label in cases:
        with tempfile.TemporaryDirectory() as d:
            tgt = Path(d) / "proj"
            install(tgt, "--profile", "large", "--agent", "claude")
            if line == "(줄 없음)":
                f = tgt / "AGENTS.md"
                f.write_text("\n".join(l for l in f.read_text(encoding="utf-8").splitlines()
                                       if not l.startswith("HARNESS_VERSION:"))
                             + "\n## 우리 팀 규칙\n금요일 배포 금지\n", encoding="utf-8")
            else:
                _freeze(tgt, line)
            rc, out = install(tgt, "--profile", "large", "--agent", "claude")
            check(f"{label}: 강한 경고가 나온다", want in out, out[:900])
            check(f"{label}: 해소 명령을 안내한다", "--accept-constitution" in out, out[:900])
            check(f"{label}: 산술 오류로 안내가 끊기지 않는다",
                  "syntax error" not in out and "unbound variable" not in out, out[:900])
            check(f"{label}: manifest 에 AGENTS.md 기록이 남는다",
                  "AGENTS.md" in (tgt / "dev-agent-team/.harness-manifest").read_text(encoding="utf-8"))


def test_freeze_is_not_install_failure():
    """헌법 동결은 설치 실패가 아니다.

    설치기가 Owner 편집을 지키려고 일부러 남긴 상태인데, 설치 검증이 FAIL 을 내고 init.sh 가
    "hook 검증 실패. 안전장치가 동작하지 않을 수 있습니다. 관리자에게 문의하세요" 로 끝냈다.
    같은 출력에 "가드 훅 실동작 PASS 26 / FAIL 0" 이 찍혀 있었다 — 오진이다.
    """
    print("\n[헌법 동결은 설치 실패가 아니다]")
    with tempfile.TemporaryDirectory() as d:
        tgt = Path(d) / "proj"
        install(tgt, "--profile", "large", "--agent", "claude")
        _freeze(tgt, "HARNESS_VERSION: 1.20.0")
        rc, out = install(tgt, "--profile", "large", "--agent", "claude")
        check("설치가 성공으로 끝난다", rc == 0, out[-900:])
        check("'설치 완료' 로 끝난다", "설치 완료" in out, out[-500:])
        check("가드 훅을 탓하지 않는다", "hook 검증 실패" not in out, out[-500:])
        check("merge 가 막힌다는 것은 알린다", "merge 가 막힌다" in out, out[-900:])


def test_verify_failure_is_named():
    """설치 검증이 실패하면 **무엇이** 걸렸는지 그대로 옮기는가(결함 주입)."""
    print("\n[검증 실패를 그대로 옮긴다]")
    with tempfile.TemporaryDirectory() as d:
        tgt = Path(d) / "proj"
        install(tgt, "--profile", "large", "--agent", "claude")
        (tgt / "opencode.json").write_text("{ 이건 JSON 이 아니다", encoding="utf-8")
        rc, out = install(tgt, "--profile", "large", "--agent", "claude")
        check("검증 실패면 설치도 실패한다", rc != 0, out[-600:])
        check("걸린 항목을 나열한다", "걸린 항목:" in out, out[-900:])
        check("실제 실패 항목이 찍힌다", "JSON 파손" in out, out[-900:])


def test_profile_downgrade_prunes_roles():
    """large -> small 로 낮추면 large 전용 역할을 치우는가.

    역할 파일은 "무조건 덮어쓰는" 강제 장치인데 덮어쓰기만 있고 치우기가 없었다. 남은
    lead.md 때문에 재설치 프로파일 추론이 계속 large 를 고르고, 설치 검증도 프로파일을
    추론하므로 **영영 감지되지 않는다**(흔적으로 판정한 대가다).
    """
    print("\n[프로파일 강등]")
    with tempfile.TemporaryDirectory() as d:
        tgt = Path(d) / "proj"
        install(tgt, "--profile", "large", "--agent", "claude,opencode")
        (tgt / ".claude/agents/mine.md").write_text("# 내가 넣은 에이전트\n", encoding="utf-8")
        rc, out = install(tgt, "--profile", "small", "--agent", "claude,opencode")
        roles = sorted(p.stem for p in (tgt / ".claude/agents").glob("*.md"))
        check("large 전용 역할이 사라진다",
              not any(r in roles for r in ("lead", "reviewer", "critic", "security", "evaluator")),
              roles)
        check("공통 6역할은 남는다",
              all(r in roles for r in ("planner", "tester", "coder", "checker",
                                       "documenter", "designer")), roles)
        check("Owner 가 넣은 에이전트는 건드리지 않는다", "mine" in roles, roles)
        check("opencode 쪽도 같이 치운다",
              not (tgt / ".opencode/agents/lead.md").is_file())
        check("무엇을 치웠는지 알린다", "역할을 치웠습니다" in out, out[:900])
        check("이후 플래그 없는 재설치가 small 을 유지한다",
              "기존 프로파일 small" in install(tgt)[1], install(tgt)[1][:400])


def main():
    if shutil.which("bash") is None:
        print("SKIP: bash 없음")
        return 0
    print("[설치기 테스트]")
    test_reinstall_keeps_shape()
    test_state_preserved()
    test_accept_constitution()
    test_brownfield()
    test_test_log_migration()
    test_freeze_notice()
    test_freeze_is_not_install_failure()
    test_verify_failure_is_named()
    test_profile_downgrade_prunes_roles()
    print(f"\n[설치기 테스트] PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
