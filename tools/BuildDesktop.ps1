$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    # A failed attempt must not leave a previous successful build receipt in place.
    $receipt = Join-Path $root 'artifacts/desktop-build-evidence.json'
    if (Test-Path -LiteralPath $receipt) {
        if ((Resolve-Path -LiteralPath $receipt).Path -ne $receipt) { throw 'Unexpected receipt path' }
        Remove-Item -LiteralPath $receipt -Force
    }
    New-Item -ItemType Directory -Path (Join-Path $root 'artifacts') -Force | Out-Null
    python -c "import sys,json; from pathlib import Path; sys.path.insert(0,'tools'); from generate_manifest import source_hashes; Path('artifacts/desktop-build-inputs.json').write_text(json.dumps(source_hashes(Path.cwd(),'desktop')),encoding='utf-8')"
    if ($LASTEXITCODE) { throw 'Desktop input snapshot failed' }
    python tools/check_protocol.py
    if ($LASTEXITCODE) { throw 'Protocol check failed' }
    python -m pytest backend/tests -q
    if ($LASTEXITCODE) { throw 'Python checks failed' }
    Push-Location web
    try {
        npm ci
        if ($LASTEXITCODE) { throw 'Frontend install failed' }
        npm test
        if ($LASTEXITCODE) { throw 'Frontend tests failed' }
        npm run build
        if ($LASTEXITCODE) { throw 'Frontend build failed' }
    } finally { Pop-Location }
    python -m PyInstaller --clean --noconfirm --distpath artifacts/desktop-release --workpath artifacts/desktop-build DesktopHMI.spec
    if ($LASTEXITCODE) { throw 'Desktop packaging failed' }
    $package = Join-Path $root 'artifacts/desktop-release/FM_GPTPRO'
    if (!(Test-Path -LiteralPath "$package/FM_GPTPRO.exe" -PathType Leaf) -or
        !(Test-Path -LiteralPath "$package/_internal" -PathType Container)) {
        throw 'Incomplete PyInstaller package; App was not updated'
    }
    # Stage a complete directory, then swap it into the launcher location.
    $app = Join-Path $root 'App'
    $stage = Join-Path $root 'artifacts/desktop-deploy-stage'
    $backup = Join-Path $root 'artifacts/desktop-deploy-previous'
    foreach ($target in @($stage, $backup)) {
        if (Test-Path -LiteralPath $target) {
            if ((Resolve-Path -LiteralPath $target).Path -ne $target) { throw 'Unexpected deployment path' }
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
    Copy-Item -LiteralPath $package -Destination $stage -Recurse
    if (Test-Path -LiteralPath $app) {
        if ((Resolve-Path -LiteralPath $app).Path -ne $app) { throw 'Unexpected App path' }
        Move-Item -LiteralPath $app -Destination $backup
    }
    try {
        Move-Item -LiteralPath $stage -Destination $app
    } catch {
        if ((Test-Path -LiteralPath $backup) -and !(Test-Path -LiteralPath $app)) {
            Move-Item -LiteralPath $backup -Destination $app
        }
        throw
    }
    python -c "import sys,json; from pathlib import Path; from datetime import datetime,timezone; sys.path.insert(0,'tools'); from generate_manifest import source_hashes,digest; root=Path.cwd(); inputs=json.loads((root/'artifacts/desktop-build-inputs.json').read_text(encoding='utf-8')); assert inputs == source_hashes(root,'desktop'), 'Sources changed during build; rerun build'; record={'success':True,'completed_at':datetime.now(timezone.utc).isoformat(),'sources':inputs,'executable_sha256':digest(root/'App/FM_GPTPRO.exe'),'steps':['protocol_check','python_tests','frontend_tests','frontend_build','pyinstaller','deploy_app'],'smoke':'not_run'}; (root/'artifacts/desktop-build-evidence.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')"
    if ($LASTEXITCODE) { throw 'Desktop evidence generation failed' }
    Write-Host 'Desktop deployed: App/FM_GPTPRO.exe (keep App/_internal beside it)'
    Write-Host 'Build receipt: artifacts/desktop-build-evidence.json; packaged smoke was not run.'
    Write-Host 'Generate MANIFEST.json only after all intended validation steps are complete.'
} finally { Pop-Location }
