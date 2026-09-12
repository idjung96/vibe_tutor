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


def main():
    if shutil.which("bash") is None:
        print("SKIP: bash 없음")
        return 0
    print("[설치기 테스트]")
    test_reinstall_keeps_shape()
    test_state_preserved()
    test_accept_constitution()
    print(f"\n[설치기 테스트] PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
