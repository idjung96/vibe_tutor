# team-dev-harness Windows 설치 스크립트
# 사용법: .\init.ps1 [-Profile small|large] [-Agent claude|codex|opencode|all] [-Target 대상폴더]
#         .\init.ps1 -AcceptConstitution [-Target 대상폴더]
#           헌법 동결(AGENTS.md.new/CLAUDE.md.new 가 남은 상태)을 이 명령 하나로 푼다.
# 프로파일 생략 시: 온프레미스(ANTHROPIC_BASE_URL/OPENAI_BASE_URL이 내부망)면 small, 그 외 large.
# 에이전트 생략 시: all (claude + codex + opencode).
# 요구사항: PowerShell 5.1 이상, git, (hook 검증용) Git Bash
#Requires -Version 5.1
param(
    [ValidateSet('small', 'large')]
    [string]$Profile,
    [string]$Agent = '',          # 빈 값 = 지정 안 함(재설치면 기존 구성을 따른다)
    [string]$Target = (Get-Location).Path,
    [switch]$AcceptConstitution
)
$ErrorActionPreference = 'Stop'
$Src = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = (Get-Content -Encoding UTF8 (Join-Path $Src 'HARNESS_VERSION') | Select-Object -First 1).Trim()

New-Item -ItemType Directory -Force -Path $Target | Out-Null
$Target = (Resolve-Path $Target).Path
if ($Target -eq $Src) {
    Write-Host '오류: 하니스 저장소 안에는 설치할 수 없습니다. 프로젝트 폴더를 지정하세요.'
    Write-Host '예) .\init.ps1 -Target C:\projects\my-app'
    exit 1
}

# ── 0. 재설치라면 기존 구성을 따른다 (init.sh 와 동작이 같아야 한다) ──────────
# 플래그를 생략한 재설치가 프로파일·에이전트를 새로 판별하면, small 로 깔아 둔 온프레미스
# 프로젝트가 조용히 large 로 바뀌고 codex 오버레이까지 깔린다. 명시한 플래그가 언제나 이긴다.
function Installed-Profile {
    foreach ($f in @('.claude\agents\lead.md', '.agents\skills\lead\SKILL.md',
                     '.opencode\agents\lead.md')) {
        if (Test-Path -LiteralPath (Join-Path $Target $f)) { return 'large' }
    }
    if (Test-Path -LiteralPath (Join-Path $Target 'AGENTS.md')) { return 'small' }
    return ''
}
function Installed-Agents {
    $out = @()
    if (Test-Path -LiteralPath (Join-Path $Target '.claude\settings.json')) { $out += 'claude' }
    if (Test-Path -LiteralPath (Join-Path $Target '.codex\config.toml'))    { $out += 'codex' }
    if (Test-Path -LiteralPath (Join-Path $Target 'opencode.json'))          { $out += 'opencode' }
    return ($out -join ',')
}
if (Test-Path -LiteralPath (Join-Path $Target 'AGENTS.md')) {
    if (-not $Profile) {
        $pWas = Installed-Profile
        if ($pWas) {
            $Profile = $pWas
            Write-Host "재설치: 기존 프로파일 $Profile 을(를) 유지합니다(-Profile 로 바꿀 수 있습니다)."
        }
    }
    if (-not $Agent) {
        $aWas = Installed-Agents
        if ($aWas) {
            $Agent = $aWas
            Write-Host "재설치: 기존 에이전트 구성 $Agent 을(를) 유지합니다(-Agent 로 바꿀 수 있습니다)."
        }
    }
}
if (-not $Agent) { $Agent = 'all' }

# ── 1. 에이전트 선택 ──────────────────────────────────────────
if ($Agent -eq 'all') { $Agents = @('claude', 'codex', 'opencode') }
else { $Agents = $Agent.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ } }
foreach ($a in $Agents) {
    if ($a -notin @('claude', 'codex', 'opencode')) {
        Write-Host "알 수 없는 에이전트: $a (claude|codex|opencode|all)"; exit 1
    }
}
function Has-Agent($n) { return $Agents -contains $n }

# ── 2. 프로파일 판별: 온프레미스면 small, 그 외 large ─────────
if (-not $Profile) {
    $base = "$($env:ANTHROPIC_BASE_URL)$($env:OPENAI_BASE_URL)"
    if ($base -match '(?i)134\.75\.147\.|kims|litellm|localhost|127\.0\.0\.1|192\.168\.|(^|//)10\.|172\.(1[6-9]|2[0-9]|3[01])\.') {
        $Profile = 'small'
    }
    else {
        $Profile = 'large'
    }
}

# codex는 large 프로파일 전용(외부 대형 추론 모델). small에서 요청되면 차단한다.
if ($Profile -eq 'small' -and (Has-Agent 'codex')) {
    Write-Error "codex는 large 프로파일 전용입니다 (small 미지원). small은 --agent claude,opencode 로 실행하세요."
    exit 1
}

# 프로파일 conf 읽기 (KEY=VALUE)
$conf = @{}
Get-Content -Encoding UTF8 (Join-Path $Src "profiles\$Profile.conf") | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $k, $v = $_ -split '=', 2
    $conf[$k.Trim()] = $v.Trim().Trim('"')
}

# ── 3. 템플릿 렌더링 ──────────────────────────────────────────
# {{#IF_SMALL}}/{{#IF_LARGE}} 블록은 마커가 한 줄을 통째로 차지해야 한다.
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Render-String($SrcFile) {
    $out = New-Object System.Collections.Generic.List[string]
    $mode = ''
    foreach ($line in (Get-Content -Encoding UTF8 $SrcFile)) {
        if ($line -eq '{{#IF_SMALL}}') { $mode = if ($Profile -eq 'small') { 'keep' } else { 'skip' } }
        elseif ($line -eq '{{#IF_LARGE}}') { $mode = if ($Profile -eq 'large') { 'keep' } else { 'skip' } }
        elseif ($line -eq '{{/IF_SMALL}}' -or $line -eq '{{/IF_LARGE}}') { $mode = '' }
        elseif ($mode -eq 'skip') { }
        else {
            $l = $line -replace '\{\{PROFILE_LABEL\}\}', $conf['PROFILE_LABEL']
            $l = $l -replace '\{\{RETRY_LIMIT\}\}', $conf['RETRY_LIMIT']
            $l = $l -replace '\{\{MAX_CHECKER_CALLS\}\}', $conf['MAX_CHECKER_CALLS']
            $l = $l -replace '\{\{HARNESS_VERSION\}\}', $Version
            $out.Add($l)
        }
    }
    return ($out -join "`n") + "`n"
}
# ── conffile 방식 (init.sh 의 render_managed 와 동작이 같아야 한다) ──────────
# AGENTS.md·CLAUDE.md 는 Owner가 손댈 수 있는 문서다. 손대지 않았으면 갱신하고,
# 손댔으면 덮지 않고 .new 로 두고 알린다. 강제 장치(settings.json deny·hooks·guard.js·
# 역할·스킬)는 낡으면 안전 계약이 깨지므로 이 규칙을 쓰지 않는다.
$Script:Manifest = $null
$Script:ManifestNew = New-Object System.Collections.Generic.List[string]

# init.sh 의 sha256_of 와 같게 CR 을 지우고 해시한다. Windows 에서 git 이 줄끝을 바꿔도
# (core.autocrlf=true) Owner 편집으로 오인해 .new 를 남기지 않게 하려는 것이다.
function Sha256Of($f) {
    if (-not (Test-Path -LiteralPath $f)) { return '' }
    $bytes = [System.IO.File]::ReadAllBytes($f)
    $buf = New-Object System.Collections.Generic.List[byte]
    foreach ($b in $bytes) { if ($b -ne 13) { $buf.Add($b) } }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $hash = $sha.ComputeHash($buf.ToArray()) } finally { $sha.Dispose() }
    return (($hash | ForEach-Object { $_.ToString('x2') }) -join '')
}

function Manifest-Get($rel) {
    if (-not (Test-Path -LiteralPath $Script:Manifest)) { return $null }
    foreach ($line in (Get-Content -LiteralPath $Script:Manifest -Encoding UTF8)) {
        $parts = $line -split '\s+', 2
        if ($parts.Count -eq 2 -and $parts[1].Trim() -eq $rel) { return $parts[0] }
    }
    return $null
}

function Ver-Minor($v) {
    if ($v -match '^(\d+)\.(\d+)') { return [int]$Matches[1] * 1000 + [int]$Matches[2] }
    return $null
}
function Version-In($f) {
    if (-not (Test-Path -LiteralPath $f)) { return $null }
    $m = Select-String -LiteralPath $f -Pattern '^HARNESS_VERSION: *(.+)$' | Select-Object -First 1
    if ($m) { return $m.Matches.Groups[1].Value.Trim() }
    return $null
}
function Render-Managed($SrcFile, $DstFile, $Rel) {
    New-Item -ItemType Directory -Force -Path (Split-Path $DstFile) | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $Script:Manifest) | Out-Null
    $tmp = "$DstFile.harness-tmp"
    [System.IO.File]::WriteAllText($tmp, (Render-String $SrcFile), $Utf8NoBom)
    $newHash = Sha256Of $tmp

    if (-not (Test-Path -LiteralPath $DstFile)) {
        Move-Item -LiteralPath $tmp $DstFile -Force
    }
    else {
        $curHash = Sha256Of $DstFile
        $recorded = Manifest-Get $Rel
        if ($null -ne $recorded) {
            if ($curHash -eq $recorded) {
                Move-Item -LiteralPath $tmp $DstFile -Force          # 안 건드림 -> 갱신
            }
            elseif ($curHash -eq $newHash) {
                Remove-Item -LiteralPath $tmp -Force                 # 이미 새 내용
            }
            else {
                Move-Item -LiteralPath $tmp "$DstFile.new" -Force    # 편집함 -> 보존
                # init.sh 와 같은 안내여야 한다. 편집은 지키되 그 파일만 옛 버전에 묶이므로
                # 절차·역할·권한과 어긋난다는 것을 숫자로 말해 준다.
                $oldv = (Select-String -LiteralPath $DstFile -Pattern '^HARNESS_VERSION: *(.+)$' |
                         Select-Object -First 1).Matches.Groups[1].Value
                if (-not $oldv) { $oldv = '?' }
                Write-Host "알림: $Rel 을(를) 직접 수정한 것으로 보여 덮어쓰지 않았습니다. 새 버전은 $Rel.new 입니다."
                Write-Host "      주의: $Rel 는 v$oldv 에 묶입니다. 절차·역할·권한은 v$Version 으로 갱신되므로"
                Write-Host '      규칙이 서로 어긋난 상태로 돌게 됩니다.'
                $gap = (Ver-Minor $Version) - (Ver-Minor $oldv)
                if ($null -ne $gap -and $gap -ge 5) {
                    Write-Host ''
                    Write-Host "      *** 버전 차이가 큽니다(마이너 $gap 단계). 그 사이에 절차·역할·권한이 여러 번"
                    Write-Host '          바뀌었으므로 이 상태의 팀은 정상 동작하지 않습니다. 반드시 갱신하세요. ***'
                    Write-Host ''
                }
                Write-Host '      해결(권장) — 이 명령 하나면 됩니다:'
                Write-Host "        .\init.ps1 -AcceptConstitution -Target $Target"
                Write-Host '      직접 쓰신 규칙을 dev-agent-team/PROJECT_RULES.md 로 옮기고 새 헌법을 받아들인 뒤'
                Write-Host "      설치를 계속해 manifest 까지 맞춥니다(이전 내용은 $Rel.owner-backup 에 남습니다)."
                Write-Host '      무엇이 바뀌는지 먼저 보려면:'
                Write-Host '        python3 dev-agent-team/selfcheck.py --constitution-diff'
                Write-Host '      갱신하지 않으면 단계 merge 게이트가 constitution 으로 막힙니다.'
            }
        }
        else {
            Copy-Item -LiteralPath $DstFile "$DstFile.bak" -Force    # manifest 이전 -> 백업 후 갱신
            Move-Item -LiteralPath $tmp $DstFile -Force
            Write-Host "알림: $Rel 을(를) 갱신했습니다. 이전 내용은 $Rel.bak 에 보관했습니다."
        }
    }
    $Script:ManifestNew.Add((Sha256Of $DstFile) + '  ' + $Rel)
}

function Render($SrcFile, $DstFile) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DstFile) | Out-Null
    [System.IO.File]::WriteAllText($DstFile, (Render-String $SrcFile), $Utf8NoBom)
}
function Write-Text($DstFile, $Text) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DstFile) | Out-Null
    [System.IO.File]::WriteAllText($DstFile, $Text, $Utf8NoBom)
}
function Emit-Skills($Base) {
    foreach ($s in 'team-dev', 'logging-rule', 'lib-research', 'code-convention', 'test-design', 'ui-design') {
        Render (Join-Path $Src "templates\skills\$s\SKILL.md.tmpl") (Join-Path $Target "$Base\$s\SKILL.md")
    }
}
function Role-Desc($r) { switch ($r) {
    'planner' { '요구사항을 단계로 나눈다. 결정을 내린다. Owner 질문을 만든다.' }
    'tester'  { '단계 목표를 받아 테스트케이스를 작성한다.' }
    'coder'   { '테스트를 통과시키는 코드를 작성한다.' }
    'checker' { '테스트 전체를 실행하고 PASS/FAIL을 판정한다.' }
    'documenter' { '완성된 코드로 README와 사용법 문서를 만든다.' }
    'designer' { 'UI/화면의 설계 명세(디자인 토큰·컴포넌트·접근성·반응형)를 만든다.' }
    'reviewer' { '코드와 테스트코드를 규칙에 비추어 검토하고 지적한다.' }
    'lead' { '개발 방향·우선순위를 정하고 백로그를 그루밍하며, 단계·최종 회고로 절차 개선안을 낸다.' }
    'critic' { '결정과 계획에 반론을 펴고 고위험·모호성을 가린다.' }
    'security' { '코드의 보안 위험(비밀·인젝션·위험 호출)을 점검한다.' }
    'evaluator' { '산출물이 요구한 것을 했는지 축별로 점수와 격차를 낸다.' }
} }
function Role-Model($r) { switch ($r) {
    'coder' { 'opus' }
    'checker' { 'sonnet' }
    'documenter' { 'sonnet' }
    'tester' { 'opus' }
    'designer' { 'opus' }
    'planner' { 'opus' }
    'lead' { 'opus' }
    'reviewer' { 'opus' }
    'security' { 'opus' }
    'critic' { 'opus' }
    'evaluator' { 'opus' }
} }
# 추론 강도는 전 역할 high 고정 — 역할별로 낮추지 않는다.
function Role-Effort($r) { 'high' }
function Claude-Tools($r) { switch ($r) {
    'planner' { 'Read, Write, Grep' } 'tester' { 'Read, Write' }
    'coder'   { 'Read, Write, Edit, Bash' } 'checker' { 'Bash, Read' }
    'documenter' { 'Read, Write, Edit, Bash' }
    'designer' { 'Read, Write' }
    'reviewer' { 'Read, Grep' }
    'lead' { 'Read, Grep' }
    'critic' { 'Read, Grep' }
    'security' { 'Read, Grep' }
    'evaluator' { 'Read, Grep' }
} }
function Opencode-Tools($r) { switch ($r) {
    'planner' { "  write: true`n  edit: false`n  bash: false" }
    'tester'  { "  write: true`n  edit: false`n  bash: false" }
    'coder'   { "  write: true`n  edit: true`n  bash: true" }
    'checker' { "  write: false`n  edit: false`n  bash: true" }
    'documenter' { "  write: true`n  edit: true`n  bash: true" }
    'designer' { "  write: true`n  edit: false`n  bash: false" }
    'reviewer' { "  write: false`n  edit: false`n  bash: false" }
    'lead' { "  write: false`n  edit: false`n  bash: false" }
    'critic' { "  write: false`n  edit: false`n  bash: false" }
    'security' { "  write: false`n  edit: false`n  bash: false" }
    'evaluator' { "  write: false`n  edit: false`n  bash: false" }
} }

# TEST_LOG.md 5열 -> 7열 마이그레이션 (v1.22.0에서 재시도·리뷰지적 열이 생겼다).
# init은 기존 상태 파일을 덮지 않으므로 옛 프로젝트는 재설치해도 5열로 남는다.
# 모두 7열로 올라간 뒤에는 이 함수를 지워도 된다. init.sh 의 migrate_test_log 와 동작이 같아야 한다.
function Migrate-TestLog($f) {
    if (-not (Test-Path $f)) { return }
    $lines = Get-Content -LiteralPath $f -Encoding UTF8
    # 옛 5열 헤더가 있고 새 열이 아직 없을 때만 건드린다(멱등).
    $oldHeader = '^\|\s*단계\s*\|\s*신규\s*\|\s*누적\s*\|\s*전체 결과\s*\|\s*커밋\s*\|$'
    if (-not ($lines | Where-Object { $_ -match $oldHeader })) { return }
    if ($lines | Where-Object { $_ -match '재시도' }) { return }
    Copy-Item -LiteralPath $f "$f.bak"
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        # 파이프가 정확히 6개인 줄만 마지막 칸(커밋) 앞에 두 칸을 끼운다. 나머지 줄은 원문 유지.
        if ($line.StartsWith('|') -and (($line.ToCharArray() | Where-Object { $_ -eq '|' }).Count -eq 6)) {
            $a = $line -split '\|'
            $head = $a[1] + '|' + $a[2] + '|' + $a[3] + '|' + $a[4]
            $sep = $head -replace '[-| :]', ''
            if ($a[1] -match '단계' -and $a[5] -match '커밋') {
                # 헤더 앞에 새 열 설명을 넣는다(위 가드 덕에 아직 없는 것이 보장된다).
                $out.Add('- 재시도: 이 단계에서 checker를 다시 부른 횟수(NEW_FAIL·REGRESSION 재시도 포함).')
                $out.Add('- 리뷰지적: 이 단계에서 받은 코드·보안 리뷰 지적 건수. 리뷰 단계가 없으면 `-`.')
                $out.Add('')
                $mid = ' 재시도 | 리뷰지적 '
            }
            elseif ($sep -eq '') { $mid = '---|---' }
            else { $mid = ' - | - ' }
            $out.Add('|' + $head + '|' + $mid + '|' + $a[5] + '|')
        }
        else { $out.Add($line) }
    }
    # 이 파일의 관행대로 BOM 없는 UTF-8 + LF 로 쓴다. Set-Content 는 PS5.1에서 BOM을 붙이고,
    # WriteAllLines 는 CRLF 를 써서 init.sh 의 awk 출력(LF)과 어긋난다.
    [System.IO.File]::WriteAllText($f, ($out -join "`n") + "`n", $Utf8NoBom)
    Write-Host 'TEST_LOG.md를 7열로 갱신했습니다 (원본: dev-agent-team/TEST_LOG.md.bak).'
}

# 역할 목록: designer는 양 프로파일 공통(UI 단계에서만 호출).
# lead·reviewer·critic·security는 large 프로파일에서만 깐다.
$Roles = @('planner', 'tester', 'coder', 'checker', 'documenter', 'designer')
if ($Profile -eq 'large') { $Roles += @('lead', 'reviewer', 'critic', 'security', 'evaluator') }

Write-Host "프로파일: $($conf['PROFILE_LABEL']) / 에이전트: $($Agents -join ' ') → $Target"

# ── 4. 공통 파일 (모든 에이전트) ──────────────────────────────
$Script:Manifest = Join-Path $Target 'dev-agent-team\.harness-manifest'
# ── 4-0. 헌법 동결 해소 (-AcceptConstitution) — init.sh 와 동작이 같아야 한다 ──────
function Accept-Constitution($File, $Name) {
    if (-not (Test-Path -LiteralPath "$File.new")) { return }
    $oldv = Version-In $File; $newv = Version-In "$File.new"
    $ownerLines = @()
    $sc = Join-Path $Target 'dev-agent-team\selfcheck.py'
    # ?? 는 PowerShell 7+ 전용이다. 이 스크립트는 #Requires -Version 5.1 이라 쓰면 안 된다.
    $py = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
    if ((Test-Path -LiteralPath $sc) -and $py) {
        Push-Location $Target
        try {
            $out = & $py.Source 'dev-agent-team/selfcheck.py' '--constitution-diff' 2>$null
            $ownerLines = @($out | Where-Object { $_ -match '^\[scope\]     ' } |
                            ForEach-Object { $_ -replace '^\[scope\]     ', '' })
        } finally { Pop-Location }
    }
    if ($ownerLines.Count -gt 0) {
        $pr = Join-Path $Target 'dev-agent-team\PROJECT_RULES.md'
        $add = "`n## $Name 에서 옮겨온 규칙 (하네스 v$newv 업데이트 시 자동 이관)`n" +
               "<!-- 헌법을 좁히는 방향으로만 작동합니다. 안전장치는 무효화하지 못합니다. -->`n" +
               (($ownerLines -join "`n") + "`n")
        $cur = if (Test-Path -LiteralPath $pr) { [System.IO.File]::ReadAllText($pr) } else { '' }
        [System.IO.File]::WriteAllText($pr, $cur + $add, $Utf8NoBom)
        Write-Host "알림: $Name 에 직접 쓰신 규칙을 dev-agent-team/PROJECT_RULES.md 로 옮겼습니다:"
        $ownerLines | ForEach-Object { Write-Host "        $_" }
    }
    Copy-Item -LiteralPath $File "$File.owner-backup" -Force
    Move-Item -LiteralPath "$File.new" $File -Force
    Write-Host "알림: $Name 를 v$oldv -> v$newv 로 갱신했습니다(이전 내용은 $Name.owner-backup)."
}
if ($AcceptConstitution) {
    Accept-Constitution (Join-Path $Target 'AGENTS.md') 'AGENTS.md'
    Accept-Constitution (Join-Path $Target 'CLAUDE.md') 'CLAUDE.md'
}

Render-Managed (Join-Path $Src 'templates\AGENTS.md.tmpl') (Join-Path $Target 'AGENTS.md') 'AGENTS.md'
foreach ($d in 'common', 'tests', 'logs', 'dev-agent-team\libs', 'dev-agent-team\guides', 'dev-agent-team\answered', 'dev-agent-team\hooks') {
    New-Item -ItemType Directory -Force -Path (Join-Path $Target $d) | Out-Null
}
Copy-Item (Join-Path $Src 'templates\common\logger.py') (Join-Path $Target 'common\logger.py') -Force
Copy-Item (Join-Path $Src 'templates\project\selfcheck.py') (Join-Path $Target 'dev-agent-team\selfcheck.py') -Force
Copy-Item (Join-Path $Src 'templates\hooks\*.sh')       (Join-Path $Target 'dev-agent-team\hooks\') -Force
# 가드 훅의 줄끝을 대상 프로젝트의 git 에서도 고정한다(init.sh 와 동작이 같아야 한다).
# 없으면 Owner 가 커밋한 뒤 Windows 에서 클론할 때 .sh 가 CRLF 가 되어 정지 메커니즘이 깨진다.
$ga = Join-Path $Target '.gitattributes'
$gaSrc = Join-Path $Src 'templates\project\gitattributes'
if (-not (Test-Path -LiteralPath $ga)) {
    Copy-Item $gaSrc $ga -Force
}
elseif (-not (Select-String -LiteralPath $ga -Pattern 'team-dev-harness-eol-guard' -SimpleMatch -Quiet)) {
    # Owner 파일은 덮지 않고 필요한 줄만 끝에 덧붙인다(뒤 규칙이 이긴다).
    $cur = [System.IO.File]::ReadAllText($ga)
    $adds = [System.IO.File]::ReadAllText($gaSrc)
    [System.IO.File]::WriteAllText($ga, $cur + "`n" + $adds, $Utf8NoBom)
    Write-Host '알림: .gitattributes 끝에 가드 훅 줄끝 고정 규칙을 추가했습니다.'
}

Copy-Item (Join-Path $Src 'templates\docs\OWNER_GUIDE.md') (Join-Path $Target 'dev-agent-team\guides\OWNER_GUIDE.md') -Force
Copy-Item (Join-Path $Src 'templates\docs\DEBUG_GUIDE.md') (Join-Path $Target 'dev-agent-team\guides\DEBUG_GUIDE.md') -Force
foreach ($pair in @(
        @('templates\project\DECISIONS.md', 'dev-agent-team\DECISIONS.md'),
        @('templates\project\PROJECT_RULES.md', 'dev-agent-team\PROJECT_RULES.md'),
        @('templates\project\TEST_LOG.md', 'dev-agent-team\TEST_LOG.md'),
        @('templates\project\docs-libs-INDEX.md', 'dev-agent-team\libs\INDEX.md'),
        @('templates\project\BACKLOG.md', 'dev-agent-team\BACKLOG.md'))) {
    $dst = Join-Path $Target $pair[1]
    if (-not (Test-Path $dst)) { Copy-Item (Join-Path $Src $pair[0]) $dst }
}
Migrate-TestLog (Join-Path $Target 'dev-agent-team\TEST_LOG.md')
if ($Profile -eq 'large' -and -not (Test-Path (Join-Path $Target 'dev-agent-team\DIRECTION.md'))) {
    Copy-Item (Join-Path $Src 'templates\project\DIRECTION.md') (Join-Path $Target 'dev-agent-team\DIRECTION.md')
}
foreach ($k in 'logs\.gitkeep', 'dev-agent-team\answered\.gitkeep') {
    New-Item -ItemType File -Force -Path (Join-Path $Target $k) | Out-Null
}

# ── 5. Claude Code 오버레이 ───────────────────────────────────
if (Has-Agent 'claude') {
    Render-Managed (Join-Path $Src 'templates\CLAUDE.md.tmpl') (Join-Path $Target 'CLAUDE.md') 'CLAUDE.md'
    Render (Join-Path $Src 'templates\settings.json.tmpl') (Join-Path $Target '.claude\settings.json')
    Emit-Skills '.claude\skills'
    foreach ($r in $Roles) {
        $body = Render-String (Join-Path $Src "templates\roles\$r.md.tmpl")
        $model = Role-Model $r
        $effort = Role-Effort $r
        $fm = "---`nname: $r`ndescription: $(Role-Desc $r)`n"
        if ($model) { $fm += "model: $model`n" }
        if ($effort) { $fm += "effort: $effort`n" }
        $fm += "tools: $(Claude-Tools $r)`n---`n"
        Write-Text (Join-Path $Target ".claude\agents\$r.md") ($fm + $body)
    }
}

# ── 6. Codex 오버레이 ─────────────────────────────────────────
if (Has-Agent 'codex') {
    Render (Join-Path $Src 'templates\codex\config.toml.tmpl') (Join-Path $Target '.codex\config.toml')
    Copy-Item (Join-Path $Src 'templates\codex\hooks.json')    (Join-Path $Target '.codex\hooks.json') -Force
    Emit-Skills '.agents\skills'
    foreach ($r in $Roles) {
        $body = Render-String (Join-Path $Src "templates\roles\$r.md.tmpl")
        $fm = "---`nname: $r`ndescription: $(Role-Desc $r)`n---`n"
        Write-Text (Join-Path $Target ".agents\skills\$r\SKILL.md") ($fm + $body)
    }
}

# ── 7. opencode 오버레이 ──────────────────────────────────────
if (Has-Agent 'opencode') {
    Render (Join-Path $Src 'templates\opencode\opencode.json.tmpl') (Join-Path $Target 'opencode.json')
    New-Item -ItemType Directory -Force -Path (Join-Path $Target '.opencode\plugins') | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $Target '.opencode\agents') | Out-Null
    Copy-Item (Join-Path $Src 'templates\opencode\plugins\guard.js') (Join-Path $Target '.opencode\plugins\guard.js') -Force
    if (-not (Test-Path (Join-Path $Target '.agents\skills\team-dev'))) { Emit-Skills '.agents\skills' }
    foreach ($r in $Roles) {
        $body = Render-String (Join-Path $Src "templates\roles\$r.md.tmpl")
        $fm = "---`ndescription: $(Role-Desc $r)`nmode: subagent`ntools:`n$(Opencode-Tools $r)`n---`n"
        Write-Text (Join-Path $Target ".opencode\agents\$r.md") ($fm + $body)
    }
}

# manifest 확정. 이번에 렌더하지 않은 항목(에이전트 구성을 바꿔 설치한 경우)은 그대로
# 이어간다 — 안 그러면 다음 설치 때 "기록 없음"으로 보여 불필요한 .bak 이 생긴다.
if ($Script:ManifestNew.Count -gt 0) {
    $seen = @{}
    foreach ($l in $Script:ManifestNew) { $seen[($l -split '\s+', 2)[1].Trim()] = $true }
    if (Test-Path -LiteralPath $Script:Manifest) {
        foreach ($l in (Get-Content -LiteralPath $Script:Manifest -Encoding UTF8)) {
            $parts = $l -split '\s+', 2
            if ($parts.Count -eq 2 -and -not $seen.ContainsKey($parts[1].Trim())) {
                $Script:ManifestNew.Add($l)
            }
        }
    }
    [System.IO.File]::WriteAllText($Script:Manifest, ($Script:ManifestNew -join "`n") + "`n", $Utf8NoBom)
}

# ── 8. git 초기화 ─────────────────────────────────────────────
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host '경고: git이 없습니다. https://git-scm.com 에서 Git for Windows를 설치하세요.'
    Write-Host '      (Claude Code Windows 버전도 Git Bash가 필요합니다.)'
    exit 1
}
if (-not (Test-Path (Join-Path $Target '.git'))) {
    Push-Location $Target
    try {
        git init -q
        [System.IO.File]::WriteAllLines((Join-Path $Target '.gitignore'),
            @('logs/app.log', '__pycache__/', '.pytest_cache/'), $Utf8NoBom)
        git add -A
        git -c user.name=harness -c user.email=harness@local commit -qm "[harness] init (profile=$Profile, agents=$($Agents -join ' '), v$Version)"
    }
    finally { Pop-Location }
}

# ── 8b. 파이썬 필수 확인 (init.sh 와 같은 안내여야 한다) ─────────────────
if (-not (Get-Command python3 -ErrorAction SilentlyContinue) -and
    -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host ''
    Write-Host '경고: python3/python 을 찾지 못했습니다.'
    Write-Host '      이 하네스는 만들려는 제품의 언어와 무관하게 파이썬이 필요합니다:'
    Write-Host '        - dev-agent-team/hooks/protect_tests.sh 가 훅 입력에서 경로를 뽑을 때'
    Write-Host '        - dev-agent-team/selfcheck.py (단계 merge 게이트·산출물 점수)'
    Write-Host '      가드는 확인이 불가능하면 통과시키지 않고 막습니다(fail-closed).'
    Write-Host '      파이썬 없이는 파일 편집이 전부 차단됩니다. 먼저 파이썬을 설치하세요.'
    Write-Host ''
}

# ── 9. 설치 검증 (Git Bash 필요) — verify_install.sh 가 verify_hooks.sh 를 품는다 ──
$bash = $null
$cmd = Get-Command bash -ErrorAction SilentlyContinue
if ($cmd) { $bash = $cmd.Source }
else {
    foreach ($p in "$env:ProgramFiles\Git\bin\bash.exe", "$env:ProgramFiles\Git\usr\bin\bash.exe",
        "${env:ProgramFiles(x86)}\Git\bin\bash.exe") {
        if ($p -and (Test-Path $p)) { $bash = $p; break }
    }
}
if ($bash) {
    $srcU = $Src -replace '\\', '/'
    $tgtU = $Target -replace '\\', '/'
    & $bash "$srcU/tests/verify_install.sh" "$tgtU"
    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host '경고: hook 검증 실패. 안전장치가 동작하지 않을 수 있습니다.'
        Write-Host '이 상태로 사용하지 말고 관리자에게 문의하세요.'
        exit 1
    }
}
else {
    Write-Host '경고: Git Bash를 찾지 못해 설치 검증을 건너뛰었습니다.'
    Write-Host '      Claude Code Windows 버전은 Git Bash가 필요하므로 먼저 설치하세요.'
    Write-Host '      설치 후 검증: bash tests/verify_install.sh <프로젝트경로>'
}

Write-Host ''
Write-Host "설치 완료 (v$Version, $Profile, [$($Agents -join ' ')])."
Write-Host "다음: $Target 에서 코딩 에이전트를 열고 '개발 시작'이라고 입력하세요."
Write-Host "초보자 안내: $Target\dev-agent-team\guides\OWNER_GUIDE.md"
if (Has-Agent 'codex') { Write-Host "Codex 주의: ~/.codex/config.toml 에 이 프로젝트를 trusted로 등록해야 .codex 설정이 적용됩니다." }
if (Has-Agent 'opencode') { Write-Host "opencode 주의: 가드레일 플러그인은 .opencode\plugins\guard.js 로 자동 로드됩니다(bun/node 필요)." }
