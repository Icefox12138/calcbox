<#
.SYNOPSIS
  One-time SSH setup for pushing to GitHub without tokens (Windows).

.DESCRIPTION
  Creates an ed25519 key if none exists, copies the public key to the clipboard,
  opens the GitHub "new SSH key" page, and points `origin` at the SSH remote.
  The private key never leaves this machine and is never printed.

.EXAMPLE
  pwsh -File scripts/setup-ssh.ps1
  pwsh -File scripts/setup-ssh.ps1 -Owner Icefox12138 -Repo calcbox
#>
param(
    [string]$Owner = "Icefox12138",
    [string]$Repo  = "calcbox"
)

$ErrorActionPreference = "Stop"
$sshDir = Join-Path $env:USERPROFILE ".ssh"
$key    = Join-Path $sshDir "id_ed25519"

# 1. key
if (-not (Test-Path $key)) {
    New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
    Write-Host "Generating $key ..."
    # -N '""' = empty passphrase (PowerShell must pass a quoted empty string)
    ssh-keygen -t ed25519 -C "$Repo@$env:COMPUTERNAME" -f $key -N '""'
} else {
    Write-Host "Using the existing key: $key"
}

# 2. public half to the clipboard
Get-Content "$key.pub" | Set-Clipboard
Write-Host ""
Write-Host "The PUBLIC key is on your clipboard. Paste it at:" -ForegroundColor Cyan
Write-Host "  https://github.com/settings/ssh/new"
Start-Process "https://github.com/settings/ssh/new"
Read-Host "Press Enter after you have saved the key on GitHub"

# 3. verify the handshake
Write-Host "Checking the connection ..."
$probe = ssh -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1
$probe | ForEach-Object { Write-Host "  $_" }
if ($probe -match "successfully authenticated") {
    Write-Host "SSH authentication works." -ForegroundColor Green
} else {
    Write-Warning "GitHub did not report a successful authentication; fix that before pushing."
}

# 4. remote
$url = "git@github.com:$Owner/$Repo.git"
git remote get-url origin 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    git remote set-url origin $url
} else {
    git remote add origin $url
}
Write-Host "origin -> $url"
Write-Host ""
Write-Host "Next: create the empty repository on GitHub (no README), then run:"
Write-Host "  git push -u origin main"
