# team-dev-harness Windows 설치 스크립트
# 사용법: .\init.ps1 [-Profile small|large] [-Target 대상폴더]
# 프로파일을 생략하면 ANTHROPIC_BASE_URL로 자동 판별한다.
#   온프레미스(사내 LLM) = small, 외부(Claude) = large
# 요구사항: PowerShell 5.1 이상, git, (hook 검증용) Git Bash
#Requires -Version 5.1
param(
    [ValidateSet('small', 'large')]
    [string]$Profile,
    [string]$Target = (Get-Location).Path
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

# ── 1. 프로파일 자동 판별 ──────────────────────────────────────
if (-not $Profile) {
    $base = $env:ANTHROPIC_BASE_URL
    if ([string]::IsNullOrWhiteSpace($base)) {
        $Profile = 'large'   # 기본 엔드포인트 = api.anthropic.com = 외부 Claude
    }
    elseif ($base -match '(?i)134\.75\.147\.|kims|litellm|localhost|127\.0\.0\.1|192\.168\.|(^|//)10\.|172\.(1[6-9]|2[0-9]|3[01])\.') {
        $Profile = 'small'   # 사내/내부망 엔드포인트 = 온프레미스 LLM
    }
    else {
        Write-Host '어떤 AI에 연결하나요?'
        Write-Host '1. 사내 AI (온프레미스 LLM)'
        Write-Host '2. Claude (인터넷)'
        $ans = Read-Host '번호'
        if ($ans -eq '1') { $Profile = 'small' } else { $Profile = 'large' }
    }
}

# 프로파일 conf 읽기 (KEY=VALUE)
$conf = @{}
Get-Content -Encoding UTF8 (Join-Path $Src "profiles\$Profile.conf") | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $k, $v = $_ -split '=', 2
    $conf[$k.Trim()] = $v.Trim().Trim('"')
}

# ── 2. 템플릿 렌더링 ──────────────────────────────────────────
# {{#IF_SMALL}}/{{#IF_LARGE}} 블록은 마커가 한 줄을 통째로 차지해야 한다.
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Render($SrcFile, $DstFile) {
    $dir = Split-Path -Parent $DstFile
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $out = New-Object System.Collections.Generic.List[string]
    $mode = ''
    foreach ($line in (Get-Content -Encoding UTF8 $SrcFile)) {
        if ($line -eq '{{#IF_SMALL}}') {
            $mode = if ($script:Profile -eq 'small') { 'keep' } else { 'skip' }
        }
        elseif ($line -eq '{{#IF_LARGE}}') {
            $mode = if ($script:Profile -eq 'large') { 'keep' } else { 'skip' }
        }
        elseif ($line -eq '{{/IF_SMALL}}' -or $line -eq '{{/IF_LARGE}}') {
            $mode = ''
        }
        elseif ($mode -eq 'skip') { }
        else {
            $l = $line -replace '\{\{PROFILE_LABEL\}\}', $conf['PROFILE_LABEL']
            $l = $l -replace '\{\{RETRY_LIMIT\}\}', $conf['RETRY_LIMIT']
            $l = $l -replace '\{\{MAX_CHECKER_CALLS\}\}', $conf['MAX_CHECKER_CALLS']
            $l = $l -replace '\{\{HARNESS_VERSION\}\}', $Version
            $out.Add($l)
        }
    }
    [System.IO.File]::WriteAllLines($DstFile, $out, $Utf8NoBom)
}

Write-Host "프로파일: $($conf['PROFILE_LABEL']) → $Target"

Render (Join-Path $Src 'templates\CLAUDE.md.tmpl')     (Join-Path $Target 'CLAUDE.md')
Render (Join-Path $Src 'templates\settings.json.tmpl') (Join-Path $Target '.claude\settings.json')
foreach ($a in 'planner', 'tester', 'coder', 'checker') {
    Render (Join-Path $Src "templates\agents\$a.md.tmpl") (Join-Path $Target ".claude\agents\$a.md")
}
foreach ($s in 'team-dev', 'logging-rule', 'lib-research') {
    Render (Join-Path $Src "templates\skills\$s\SKILL.md.tmpl") (Join-Path $Target ".claude\skills\$s\SKILL.md")
}

# ── 3. 공통 파일과 디렉토리 ───────────────────────────────────
foreach ($d in '.claude\hooks', 'common', 'tests', 'logs', 'docs\libs', 'answered') {
    New-Item -ItemType Directory -Force -Path (Join-Path $Target $d) | Out-Null
}
Copy-Item (Join-Path $Src 'templates\hooks\*.sh')         (Join-Path $Target '.claude\hooks\') -Force
Copy-Item (Join-Path $Src 'templates\common\logger.py')   (Join-Path $Target 'common\logger.py') -Force
Copy-Item (Join-Path $Src 'templates\docs\OWNER_GUIDE.md') (Join-Path $Target 'OWNER_GUIDE.md') -Force
Copy-Item (Join-Path $Src 'templates\docs\DEBUG_GUIDE.md') (Join-Path $Target 'DEBUG_GUIDE.md') -Force
foreach ($pair in @(
        @('templates\project\DECISIONS.md', 'DECISIONS.md'),
        @('templates\project\TEST_LOG.md', 'TEST_LOG.md'),
        @('templates\project\docs-libs-INDEX.md', 'docs\libs\INDEX.md'))) {
    $dst = Join-Path $Target $pair[1]
    if (-not (Test-Path $dst)) { Copy-Item (Join-Path $Src $pair[0]) $dst }
}
if ($Profile -eq 'large' -and -not (Test-Path (Join-Path $Target 'NOTES.md'))) {
    [System.IO.File]::WriteAllLines((Join-Path $Target 'NOTES.md'),
        @('# 단계 밖 발견사항 (한 줄씩)', ''), $Utf8NoBom)
}
foreach ($k in 'logs\.gitkeep', 'answered\.gitkeep') {
    New-Item -ItemType File -Force -Path (Join-Path $Target $k) | Out-Null
}

# ── 4. AGENTS.md 호환 링크 (권한 없으면 복사로 대체) ──────────
$agents = Join-Path $Target 'AGENTS.md'
if (Test-Path $agents) { Remove-Item $agents -Force }
try {
    New-Item -ItemType SymbolicLink -Path $agents -Target 'CLAUDE.md' | Out-Null
}
catch {
    Copy-Item (Join-Path $Target 'CLAUDE.md') $agents
    Write-Host '참고: 심볼릭 링크 권한이 없어 AGENTS.md를 복사본으로 만들었습니다.'
    Write-Host '      (개발자 모드를 켜면 링크로 생성됩니다. 복사본은 init.ps1 재실행 시 갱신됩니다.)'
}

# ── 5. git 초기화 ─────────────────────────────────────────────
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
        git -c user.name=harness -c user.email=harness@local commit -qm "[harness] init (profile=$Profile, v$Version)"
    }
    finally { Pop-Location }
}

# ── 6. hook 실동작 검증 (Git Bash 필요) ───────────────────────
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
    & $bash "$srcU/tests/verify_hooks.sh" "$tgtU"
    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host '경고: hook 검증 실패. 안전장치가 동작하지 않을 수 있습니다.'
        Write-Host '이 상태로 사용하지 말고 관리자에게 문의하세요.'
        exit 1
    }
}
else {
    Write-Host '경고: Git Bash를 찾지 못해 hook 검증을 건너뛰었습니다.'
    Write-Host '      Claude Code Windows 버전은 Git Bash가 필요하므로 먼저 설치하세요.'
    Write-Host '      설치 후 검증: bash tests/verify_hooks.sh <프로젝트경로>'
}

Write-Host ''
Write-Host "설치 완료 (v$Version, $Profile)."
Write-Host "다음: $Target 에서 Claude Code를 열고 '개발 시작'이라고 입력하세요."
Write-Host "초보자 안내: $Target\OWNER_GUIDE.md"
