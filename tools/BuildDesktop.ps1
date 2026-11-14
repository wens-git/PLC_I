$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
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
    python -m PyInstaller --noconfirm --distpath artifacts/desktop-release --workpath artifacts/desktop-build DesktopHMI.spec
    if ($LASTEXITCODE) { throw 'Desktop packaging failed' }
    Write-Host 'Desktop: artifacts/desktop-release/FM_GPTPRO/FM_GPTPRO.exe'
} finally { Pop-Location }
