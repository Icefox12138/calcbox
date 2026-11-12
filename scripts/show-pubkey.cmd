@echo off
rem Print and copy the SSH public key (Windows PowerShell 5.1 wrapper).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0show-pubkey.ps1" %*
