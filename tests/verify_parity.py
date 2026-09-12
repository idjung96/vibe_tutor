#!/usr/bin/env python3
"""init.sh 와 init.ps1 의 파리티를 대조한다 (저장소 개발용 도구).

pwsh 가 없는 환경에서는 init.ps1 을 실행해 볼 수 없다. 그래서 이 저장소의 단골 사고는
**init.sh 만 고치고 init.ps1 을 빠뜨리는 것**이다 — 역할 하나를 추가하면 매핑이 5군데다.
이 스크립트는 그 대조를 손으로 하지 않게 자동화한다.

    python3 tests/verify_parity.py                 # 매핑·역할목록·템플릿 (설치 불필요)
    python3 tests/verify_parity.py /tmp/t1         # + 렌더 결과 바이트 비교
                                                   #   (/tmp/t1 은 init.sh 로 설치한 트리)

검사 항목
1. 역할 매핑 4종(desc/model/claude_tools/opencode_tools)이 역할마다 같은 값인가
2. 추론 강도(role_effort/Role-Effort)가 같은 상수인가
3. 역할 목록(공통 / large 추가)이 순서까지 같은가
4. 스킬 목록이 같은가
5. 역할·스킬 템플릿이 끝에 빈 줄을 두지 않는가
   — init.sh 는 $(...) 명령 치환이라 끝의 빈 줄을 전부 지우고 \\n 하나를 붙이지만,
     init.ps1 은 Get-Content + join 이라 빈 줄을 남긴다. 여기서만 두 구현이 갈린다.
6. (대상 트리를 주면) init.ps1 의미론으로 재구성한 역할 파일이 init.sh 실제 출력과
   바이트 단위로 같은가 — 매핑이 같아도 frontmatter 조립 코드가 다르면 결과가 갈린다.

fail-closed 다. 파싱에 실패하면 통과시키지 않고 FAIL 한다 — 못 읽은 것을 "같다"고
보고하는 것이 이 도구가 저지를 수 있는 가장 나쁜 실패다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "init.sh"
PS = ROOT / "init.ps1"

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")
        if detail:
            for line in str(detail).splitlines():
                print(f"        {line}")


def read(p):
    return p.read_text(encoding="utf-8")


# ── 파서 ────────────────────────────────────────────────────────────────────
def sh_case(text, fn):
    """init.sh 의 `fn() { case "$1" in ... esac; }` 를 {role: value} 로."""
    m = re.search(rf'{fn}\(\) \{{ case "\$1" in(.*?)\nesac; \}}', text, re.S)
    if m is None:
        raise LookupError(f"init.sh 에서 {fn} 을 찾지 못했다")
    out = {}
    for line in m.group(1).strip().splitlines():
        hit = re.match(r"\s*([\w|]+)\)\s*(echo|printf)\s+(.*?)\s*;;\s*$", line)
        if not hit:
            continue
        keys, kind, val = hit.group(1).split("|"), hit.group(2), hit.group(3).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if kind == "printf":
            val = val.replace("\\n", "\n")
        for k in keys:
            out[k] = val
    if not out:
        raise LookupError(f"init.sh 의 {fn} 에서 항목을 하나도 못 읽었다")
    return out


def ps_switch(text, fn):
    """init.ps1 의 `function Fn($r) { switch ($r) { 'x' { '...' } } }` 를 {role: value} 로."""
    m = re.search(rf"function {fn}\(\$r\) \{{ switch \(\$r\) \{{(.*?)\n\}} \}}", text, re.S)
    if m is None:
        raise LookupError(f"init.ps1 에서 {fn} 을 찾지 못했다")
    out = {}
    for hit in re.finditer(r"'(\w+)'\s*\{\s*(\"[^\"]*\"|'[^']*')\s*\}", m.group(1)):
        out[hit.group(1)] = hit.group(2)[1:-1].replace("`n", "\n")
    if not out:
        raise LookupError(f"init.ps1 의 {fn} 에서 항목을 하나도 못 읽었다")
    return out


def role_lists(sh, ps):
    """(공통, large추가) 를 양쪽에서 뽑는다."""
    base_sh = re.search(r'ROLES="([^"$]+)"', sh).group(1).split()
    more_sh = re.search(r'\[ "\$PROFILE" = large \] && ROLES="\$ROLES ([^"]+)"', sh).group(1).split()
    base_ps = re.findall(r"'(\w+)'", re.search(r"\$Roles = @\(([^)]+)\)", ps).group(1))
    more_ps = re.findall(r"'(\w+)'", re.search(r"\$Roles \+= @\(([^)]+)\)", ps).group(1))
    return (base_sh, more_sh), (base_ps, more_ps)


def skill_lists(sh, ps):
    s = re.search(r"for s in ([\w\- ]+); do", sh).group(1).split()
    p = re.findall(r"'([\w\-]+)'", re.search(r"foreach \(\$s in ([^)]+)\) \{", ps).group(1))
    return s, p


# ── 1~4. 매핑·목록 ──────────────────────────────────────────────────────────
def check_mappings(sh, ps):
    (base_sh, more_sh), (base_ps, more_ps) = role_lists(sh, ps)
    check("역할 목록(공통)이 순서까지 같다", base_sh == base_ps, f"sh={base_sh}\nps={base_ps}")
    check("역할 목록(large 추가)이 순서까지 같다", more_sh == more_ps, f"sh={more_sh}\nps={more_ps}")
    roles = base_sh + more_sh

    for shfn, psfn in (("role_desc", "Role-Desc"), ("role_model", "Role-Model"),
                       ("claude_tools", "Claude-Tools"), ("opencode_tools", "Opencode-Tools")):
        a, b = sh_case(sh, shfn), ps_switch(ps, psfn)
        bad = [f"{r}: sh={a.get(r)!r} ps={b.get(r)!r}" for r in roles if a.get(r) != b.get(r)]
        check(f"{shfn} ↔ {psfn} ({len(roles)}역할)", not bad, "\n".join(bad))

    e_sh = re.search(r'role_effort\(\) \{ echo "(\w+)"; \}', sh)
    e_ps = re.search(r"function Role-Effort\(\$r\) \{ '(\w+)' \}", ps)
    ok = e_sh and e_ps and e_sh.group(1) == e_ps.group(1)
    check("role_effort ↔ Role-Effort (전 역할 고정 상수)", ok,
          "" if ok else f"sh={e_sh and e_sh.group(1)} ps={e_ps and e_ps.group(1)}")

    s, p = skill_lists(sh, ps)
    check(f"스킬 목록이 같다 ({len(s)}종)", s == p, f"sh={s}\nps={p}")
    return roles


# ── 5b. 설치기 로직 파리티 (역할 매핑 밖) ───────────────────────────────────
def check_installer_logic(sh, ps):
    """재설치 구성 추론·버전 차이·헌법 채택처럼 역할 매핑이 아닌 로직도 양쪽이 같아야 한다.

    이것들은 렌더 결과에 안 나타나서 6번(바이트 비교)으로는 안 잡힌다. 손으로 대조하면
    반드시 언젠가 빠뜨린다 — 실제로 이 검사를 만들기 전까지는 매번 손으로 봤다.
    """
    # 재설치 시 프로파일을 가리는 마커 파일(large 전용 lead 역할)
    a = re.findall(r"\$TARGET/(\.[\w./-]*lead[\w./-]*)", sh)
    b = [x.replace("\\", "/") for x in
         re.findall(r"'(\.[\w.\\-]*lead[\w.\\-]*)'", ps)]
    check("프로파일 추론 마커가 같다(lead 역할 3경로)", a == b, f"sh={a}\nps={b}")

    # 에이전트를 가리는 마커 파일과 순서
    a = re.findall(r'\$TARGET/([\w./-]+)"?\s*\]\s*&&\s*out="\$out,(\w+)"', sh)
    b = [(f.replace("\\", "/"), n) for f, n in
         re.findall(r"Join-Path \$Target '([\w.\\]+)'\)\)\s*\{\s*\$out \+= '(\w+)' \}", ps)]
    check("에이전트 추론 마커와 순서가 같다", a == b, f"sh={a}\nps={b}")

    # "버전 차이가 크다" 임계값
    a = re.search(r'\[ "\$GAP" -ge (\d+) \]', sh)
    b = re.search(r"\$gap -ge (\d+)", ps)
    ok = a and b and a.group(1) == b.group(1)
    check("버전 차이 경고 임계값이 같다", ok,
          "" if ok else f"sh={a and a.group(1)} ps={b and b.group(1)}")

    # 헌법 채택이 만드는 파일 접미사
    a = sorted(set(re.findall(r'"\$1\.([\w-]+)"', sh)))
    b = sorted(set(re.findall(r'"\$File\.([\w-]+)"', ps)))
    check("헌법 채택이 다루는 파일 접미사가 같다", a == b, f"sh={a}\nps={b}")

    # 파이썬 필수 경고가 양쪽에 있는가
    check("파이썬 필수 경고가 양쪽에 있다",
          "python3/python 을 찾지" in sh and "python3/python 을 찾지" in ps)

    # PowerShell 7+ 전용 구문을 쓰지 않았는가(#Requires -Version 5.1 이다).
    # 주석은 뺀다 — "?? 는 7+ 전용" 같은 설명까지 잡으면 자기 주석에 걸린다.
    code = "\n".join(ln for ln in ps.splitlines() if not ln.lstrip().startswith("#"))
    bad = [op for op in ("??", "?.", "-Parallel") if op in code]
    check("init.ps1 이 PowerShell 5.1 호환 구문만 쓴다", not bad, f"7+ 전용: {bad}")


# ── 5. 템플릿 끝 빈 줄 ──────────────────────────────────────────────────────
def check_trailing_blank():
    bad = []
    for tmpl in sorted(ROOT.glob("templates/roles/*.tmpl")) + sorted(ROOT.glob("templates/skills/*/*.tmpl")):
        text = read(tmpl)
        if text.endswith("\n\n") or not text.endswith("\n"):
            bad.append(f"{tmpl.relative_to(ROOT)}: 끝이 {'빈 줄' if text.endswith(chr(10) * 2) else '개행 없음'}")
    check("템플릿이 끝에 빈 줄을 두지 않는다(두 구현이 갈리는 지점)", not bad, "\n".join(bad))


# ── 6. 렌더 결과 바이트 비교 ────────────────────────────────────────────────
def ps_render(src, profile, conf, version):
    """init.ps1 Render-String 의미론: Get-Content 로 줄 배열 → join "`n" + "`n"."""
    lines = read(src).split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]          # Get-Content 는 끝 개행을 줄로 만들지 않는다
    out, mode = [], ""
    for line in lines:
        if line == "{{#IF_SMALL}}":
            mode = "keep" if profile == "small" else "skip"
        elif line == "{{#IF_LARGE}}":
            mode = "keep" if profile == "large" else "skip"
        elif line in ("{{/IF_SMALL}}", "{{/IF_LARGE}}"):
            mode = ""
        elif mode == "skip":
            pass
        else:
            for key, rep in (("{{PROFILE_LABEL}}", conf["PROFILE_LABEL"]),
                             ("{{RETRY_LIMIT}}", conf["RETRY_LIMIT"]),
                             ("{{MAX_CHECKER_CALLS}}", conf["MAX_CHECKER_CALLS"]),
                             ("{{HARNESS_VERSION}}", version)):
                line = line.replace(key, rep)
            out.append(line)
    return "\n".join(out) + "\n"


def load_conf(profile):
    conf = {}
    for line in read(ROOT / f"profiles/{profile}.conf").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            conf[k] = v.strip().strip('"')
    return conf


def check_rendered(target, sh, ps, roles):
    """init.ps1 의미론으로 만든 역할 파일이 init.sh 실제 출력과 바이트 동일한가."""
    target = Path(target)
    if not (target / "AGENTS.md").is_file():
        check("대상 트리가 설치본이다", False, f"{target} 에 AGENTS.md 가 없다")
        return
    profile = "large" if (target / ".claude/agents/lead.md").is_file() else "small"
    conf = load_conf(profile)
    version = read(ROOT / "HARNESS_VERSION").strip()
    desc = ps_switch(ps, "Role-Desc")
    model = ps_switch(ps, "Role-Model")
    ctools = ps_switch(ps, "Claude-Tools")
    otools = ps_switch(ps, "Opencode-Tools")
    effort = re.search(r"function Role-Effort\(\$r\) \{ '(\w+)' \}", ps).group(1)

    present = [r for r in roles if (target / f".claude/agents/{r}.md").is_file()]
    print(f"  ({profile} 프로파일, 역할 {len(present)}종 × 3경로)")
    bad = []
    for r in present:
        body = ps_render(ROOT / f"templates/roles/{r}.md.tmpl", profile, conf, version)
        want = {
            f".claude/agents/{r}.md":
                f"---\nname: {r}\ndescription: {desc[r]}\nmodel: {model[r]}\n"
                f"effort: {effort}\ntools: {ctools[r]}\n---\n" + body,
            f".agents/skills/{r}/SKILL.md":
                f"---\nname: {r}\ndescription: {desc[r]}\n---\n" + body,
            f".opencode/agents/{r}.md":
                f"---\ndescription: {desc[r]}\nmode: subagent\ntools:\n{otools[r]}\n---\n" + body,
        }
        for rel, expected in want.items():
            path = target / rel
            if not path.is_file():
                continue                      # 그 에이전트를 안 깐 설치다
            if read(path) != expected:
                bad.append(f"{rel}: init.ps1 의미론의 결과와 다르다")
    check("역할 렌더 결과가 init.sh 출력과 바이트 동일", not bad, "\n".join(bad))


def main():
    print("[파리티 검증] init.sh ↔ init.ps1")
    sh, ps = read(SH), read(PS)
    try:
        roles = check_mappings(sh, ps)
        check_installer_logic(sh, ps)
        check_trailing_blank()
        if len(sys.argv) > 1:
            check_rendered(sys.argv[1], sh, ps, roles)
        else:
            print("  (렌더 바이트 비교는 건너뜀 — 설치 트리 경로를 인자로 주면 함께 본다)")
    except (LookupError, AttributeError, KeyError) as exc:
        # 못 읽었으면 통과시키지 않는다. "같다"고 잘못 보고하는 것이 최악이다.
        check("양쪽 스크립트를 파싱할 수 있다", False, f"{type(exc).__name__}: {exc}")

    print(f"[파리티 검증] PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
