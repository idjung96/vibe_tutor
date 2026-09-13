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
    print(f"\n[설치기 테스트] PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
