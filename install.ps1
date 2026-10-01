# isnady installer and updater for Windows (Windows PowerShell 5.1 and PowerShell 7)
#
#   irm https://raw.githubusercontent.com/bayramkotan/isnady/main/install.ps1 | iex
#   .\install.ps1 in an administrator PowerShell   install or update for every user of this computer
#   .\install.ps1 inside a clone of the repository  editable install of that clone
#
# isnady may be installed anywhere: for all users (Program Files), for one user, in any virtual
# environment, with pipx, or editable from a clone. Nothing is removed or moved: every copy found is
# UPDATED WHERE IT IS (with the Windows administrator prompt when needed). When there is no copy yet,
# it is installed the way this script is run.

# "Continue", not "Stop": in Windows PowerShell 5.1 a native program writing to a redirected stderr
# would stop the script; every step checks $LASTEXITCODE instead
$ErrorActionPreference = "Continue"
function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }
function Ask($q)  { $a = Read-Host "$q [y/N]"; return @("y", "yes", "e", "evet") -contains "$a".Trim().ToLower() }

# ---------------------------------------------------------------- Python
$Py = $null; $PyArgs = @()
if ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV\Scripts\python.exe")) { $Py = "$env:VIRTUAL_ENV\Scripts\python.exe" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $Py = "py"; $PyArgs = @("-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $Py = "python" }
if (-not $Py) { Warn "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ first."; return }
# a SIMPLE function (no param block): an advanced one would take -c / -m as its own parameters
function RunPy { & $Py @PyArgs @args }
RunPy -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) { Warn "isnady needs Python 3.10 or newer ($(RunPy -V 2>&1))."; return }
$PyExe = "$(RunPy -c "import sys; print(sys.executable)")".Trim()
$InVenv = "$(RunPy -c "import sys; print(1 if sys.prefix != sys.base_prefix else 0)")".Trim() -eq "1"
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
$Clone = ""
if ($env:ISNADY_INSTALL -ne "pypi" -and (Test-Path pyproject.toml) -and (Select-String -Path pyproject.toml -Pattern '^name = "isnady"' -Quiet)) {
    $Clone = (Get-Location).Path
}
Say "Python: $PyExe ($(RunPy -V 2>&1))$(if ($Clone) { "; clone: $Clone" })"

# ---------------------------------------------------------------- every copy this Python can see
$Lister = @'
import json, site, sys
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlparse
user = Path(site.getusersitepackages())
dirs = []
for p in sys.path + list(getattr(site, "getsitepackages", lambda: [])()) + [str(user)]:
    if p and Path(p).is_dir() and Path(p) not in dirs:
        dirs.append(Path(p))
seen = set()
for d in dirs:
    for dist in metadata.distributions(path=[str(d)]):
        if (dist.metadata["Name"] or "").lower() != "isnady" or (str(d), dist.version) in seen:
            continue
        seen.add((str(d), dist.version))
        where = str(d)
        try:
            info = json.loads(dist.read_text("direct_url.json") or "{}")
        except ValueError:
            info = {}
        if info.get("dir_info", {}).get("editable"):
            kind, where = "editable", unquote(urlparse(info["url"]).path)
            if len(where) > 2 and where[0] == "/" and where[2] == ":":
                where = where[1:]
            where = str(Path(where))
        elif "pipx" in str(d):
            kind = "pipx"
        elif str(d).startswith(str(user)):
            kind = "user"
        elif sys.prefix != sys.base_prefix and str(d).startswith(sys.prefix):
            kind = "venv"
        else:
            kind = "system"
        print(f"{kind}|{where}|{dist.version}")
'@
$ListerFile = Join-Path ([IO.Path]::GetTempPath()) "isnady_list_copies.py"
[IO.File]::WriteAllText($ListerFile, $Lister, (New-Object System.Text.UTF8Encoding $false))
$Copies = @(RunPy $ListerFile 2>$null | Where-Object { $_ -match "\|" })
Remove-Item $ListerFile -ErrorAction SilentlyContinue

function Update-Copy($kind, $where, $version) {
    switch ($kind) {
        "user"     { Say "Updating the copy for this user ($where, $version)"; RunPy -m pip install -q --user -U isnady }
        "venv"     { Say "Updating the copy in this virtual environment ($where, $version)"; RunPy -m pip install -q -U isnady }
        "pipx"     { Say "Updating the pipx copy ($version)"; pipx upgrade isnady }
        "editable" {
            if ($Clone -and ((Resolve-Path $where -ErrorAction SilentlyContinue).Path -eq $Clone)) { return }   # reinstalled below
            Say "Refreshing the editable install of $where ($version); update that clone with git pull"
            $scope = @(); if (-not $InVenv) { $scope = @("--user") }
            RunPy -m pip install -q @scope -e $where
        }
        "system"   {
            Say "Updating the copy for all users ($where, $version)"
            RunPy -s -m pip install -q -U isnady 2>$null
            if ($LASTEXITCODE -ne 0) {
                # under Program Files only an administrator may write; Windows asks through its own prompt
                Warn "isnady $version is installed for all users in $where; updating it there needs administrator rights."
                if (Ask "Update it there now? (Windows will show a prompt)") {
                    Start-Process -FilePath $PyExe -ArgumentList "-s", "-m", "pip", "install", "-U", "isnady" -Verb RunAs -Wait
                } else {
                    Warn "Not updated; it stays at $version."
                }
            }
        }
    }
}

foreach ($line in $Copies) {
    $kind, $where, $version = "$line".Trim().Split("|")
    Update-Copy $kind $where $version
}
if ($Clone) {
    Say "Installing the clone in $Clone (editable: every git pull is live)"
    $scope = @(); if (-not $InVenv) { $scope = @("--user") }
    RunPy -m pip install -q @scope -e $Clone
} elseif ($Copies.Count -eq 0) {
    # nothing yet: install the way this script is run
    if ($InVenv) { Say "Installing into this virtual environment"; RunPy -m pip install -q -U isnady }
    elseif ($IsAdmin) { Say "Installing for all users"; RunPy -m pip install -q -U isnady }
    elseif (Get-Command pipx -ErrorAction SilentlyContinue) { Say "Installing with pipx"; pipx install isnady }
    else { Say "Installing for this user"; RunPy -m pip install -q --user -U isnady }
}

# ---------------------------------------------------------------- commands on PATH, then a check
if (-not $InVenv -and -not $IsAdmin) {
    $Bin = "$(RunPy -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))")".Trim()
    if ((Test-Path (Join-Path $Bin "iy.exe")) -and -not (($env:Path -split ";") -contains $Bin)) {
        Warn "$Bin is not in PATH, so the isnady commands would not be found."
        if (Ask "Add it to your user PATH?") {
            $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
            [Environment]::SetEnvironmentVariable("Path", (($UserPath, $Bin) -join ";").Trim(";"), "User")
            Say "Added. New terminals will find the commands."
        }
        $env:Path = "$Bin;$env:Path"
    }
}
Say "Checking"
if (Get-Command iy -ErrorAction SilentlyContinue) {
    iy -V
    $help = (iy -h 2>$null) -join "`n"
    if ($help -match "doctor") { iy doctor --offline }
}
Say "Done. Start isnady with: isnady-gui   (or iy in a terminal)"
