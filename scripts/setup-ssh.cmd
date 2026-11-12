@echo off
rem Windows PowerShell 5.1 wrapper: no pwsh required, and no permanent policy change.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-ssh.ps1" %*
