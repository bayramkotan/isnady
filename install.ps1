# isnady installer for Windows (Windows PowerShell 5.1 and PowerShell 7)
#
#   irm https://raw.githubusercontent.com/bayramkotan/isnady/main/install.ps1 | iex
#   .\install.ps1            inside a clone of the repository: editable (developer) install of that clone
#   $env:ISNADY_INSTALL = "pypi"; .\install.ps1     the PyPI release even inside a clone
#
# Removes every earlier copy first (an older copy found first hides a newer one), installs one copy,
# makes sure its commands are on PATH, then checks the result with `iy doctor`.

# "Continue", not "Stop": in Windows PowerShell 5.1 a native program writing to a redirected stderr
# would stop the script; every step checks $LASTEXITCODE instead
$ErrorActionPreference = "Continue"
function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }
function Ask($q)  { $a = Read-Host "$q [y/N]"; return @("y", "yes", "e", "evet") -contains $a.Trim().ToLower() }

# ---------------------------------------------------------------- Python
$Py = $null; $PyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) { $Py = "py"; $PyArgs = @("-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $Py = "python" }
if (-not $Py) { Warn "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ first."; return }
# a SIMPLE function (no param block): an advanced one would take -c / -m as its own parameters
function RunPy { & $Py @PyArgs @args }
RunPy -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) { Warn "isnady needs Python 3.10 or newer ($(RunPy -V 2>&1))."; return }

$UserFlag = @("--user")
if ($env:VIRTUAL_ENV) { $UserFlag = @() }      # inside a virtual environment there is no user folder

$Mode = "pypi"; $Src = ""
if ($env:ISNADY_INSTALL -ne "pypi" -and (Test-Path pyproject.toml) -and (Select-String -Path pyproject.toml -Pattern '^name = "isnady"' -Quiet)) {
    $Mode = "dev"; $Src = (Get-Location).Path
} elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
    $Mode = "pipx"
}
Say "Python: $(RunPy -V 2>&1); mode: $Mode $Src"

# ---------------------------------------------------------------- 1. remove earlier copies
Say "Looking for earlier installations"
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    $listed = (pipx list --short 2>$null) -join "`n"
    if ($listed -match "(?m)^isnady ") { Say "Removing the pipx copy"; pipx uninstall isnady | Out-Null }
}
$UserSite = (RunPy -c "import site; print(site.getusersitepackages())").Trim()
for ($i = 0; $i -lt 4; $i++) {
    $where = (RunPy -c "import isnady, os; print(os.path.dirname(os.path.dirname(isnady.__file__)))" 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $where) { break }
    $where = "$where".Trim()
    Say "Removing isnady from $where"
    if ($where -eq $UserSite) { RunPy -m pip uninstall -y isnady | Out-Null }
    else { RunPy -s -m pip uninstall -y isnady | Out-Null }
    if ($LASTEXITCODE -ne 0) {
        Warn "Could not remove the copy in $where. If it is under Program Files, run this installer once in an administrator PowerShell."
        break
    }
}

# ---------------------------------------------------------------- 2. install one copy
switch ($Mode) {
    "dev"  { Say "Installing the clone in $Src (editable: every git pull is live)"; RunPy -m pip install -q @UserFlag -e $Src }
    "pipx" { Say "Installing with pipx"; pipx install --force isnady }
    default { Say "Installing the latest release from PyPI"; RunPy -m pip install -q @UserFlag -U isnady }
}
if ($LASTEXITCODE -ne 0) { Warn "The installation failed; see the messages above."; return }

# ---------------------------------------------------------------- 3. commands on PATH
if ($Mode -eq "pipx") { $Bin = (pipx environment --value PIPX_BIN_DIR 2>$null); if (-not $Bin) { $Bin = "$HOME\.local\bin" } }
elseif ($UserFlag.Count) { $Bin = (RunPy -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))").Trim() }
else { $Bin = (RunPy -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim() }
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not (($env:Path -split ";") -contains $Bin)) {
    Warn "$Bin is not in PATH, so the isnady commands would not be found."
    if (Ask "Add it to your user PATH?") {
        [Environment]::SetEnvironmentVariable("Path", (($UserPath, $Bin) -join ";").Trim(";"), "User")
        Say "Added. New terminals will find the commands."
    }
    $env:Path = "$Bin;$env:Path"
}

# ---------------------------------------------------------------- 4. check
Say "Checking"
& (Join-Path $Bin "iy.exe") -V
$help = (& (Join-Path $Bin "iy.exe") -h 2>$null) -join "`n"
if ($help -match "doctor") {       # iy doctor exists from 0.0.7 on
    & (Join-Path $Bin "iy.exe") doctor --offline
    if ($LASTEXITCODE -ne 0) { Warn "iy doctor reported something above; 'iy doctor --fix' can repair it." }
}
Say "Done. Start isnady with: isnady-gui   (or iy in a terminal)"
