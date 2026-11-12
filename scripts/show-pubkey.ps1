<#
.SYNOPSIS
  Print (and copy) the PUBLIC key GitHub wants, never the private one.

.DESCRIPTION
  Reads ~/.ssh/<KeyName>.pub, prints it, copies it to the clipboard and shows the
  fingerprint so you can confirm GitHub stored the same key. If the .pub file is
  missing or empty it is derived from the private key with "ssh-keygen -y".

.EXAMPLE
  scripts\show-pubkey.cmd
  scripts\show-pubkey.cmd -KeyName id_rsa
#>
param(
    [string]$KeyName = "id_ed25519"
)

$ErrorActionPreference = "Stop"
$sshDir = Join-Path $env:USERPROFILE ".ssh"
$key    = Join-Path $sshDir $KeyName
$pub    = "$key.pub"

if (-not (Test-Path $key) -and -not (Test-Path $pub)) {
    foreach ($candidate in @("id_ed25519", "id_rsa")) {
        if (Test-Path (Join-Path $sshDir $candidate)) { $KeyName = $candidate; break }
    }
    $key = Join-Path $sshDir $KeyName
    $pub = "$key.pub"
}

if (-not (Test-Path $key) -and -not (Test-Path $pub)) {
    Write-Warning "No key found under $sshDir. Run scripts\setup-ssh.cmd first."
    exit 1
}

if (-not (Test-Path $pub) -or (Get-Item $pub).Length -eq 0) {
    Write-Host "Deriving the public key from $key ..."
    try {
        ssh-keygen -y -f $key | Set-Content -Path $pub -Encoding ascii
    } catch {
        Write-Warning "Could not derive the public key: $($_.Exception.Message)"
        exit 1
    }
}

$text = (Get-Content $pub -Raw).Trim()
if (-not $text) {
    Write-Warning "The public key file is empty."
    exit 1
}

Write-Host ""
Write-Host "=== COPY THIS LINE (and only this) ===" -ForegroundColor Cyan
Write-Host $text
Write-Host "=== end ===" -ForegroundColor Cyan
Write-Host ""
$text | Set-Clipboard
Write-Host "Copied to the clipboard." -ForegroundColor Green
Write-Host ""
Write-Host ("Fingerprint: " + (ssh-keygen -l -f $pub))
Write-Host "Paste it at https://github.com/settings/ssh/new (SSH keys, not GPG)."
