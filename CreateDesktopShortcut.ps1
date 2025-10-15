param(
    [string]$AppName = "AiChrome",
    [string]$ExePath = "C:\AI\AiChrome\dist\AiChrome\AiChrome.exe",
    [string]$IconPath = "C:\AI\AiChrome\assets\icon.ico"
)

$WshShell = New-Object -comObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "$AppName.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = Split-Path $ExePath
$Shortcut.Description = "AiChrome v1.2 - Browser Profile Manager with Anti-Detection"
$Shortcut.IconLocation = $IconPath
$Shortcut.Save()

Write-Host "Shortcut created: $ShortcutPath"
Write-Host "Application: $AppName"
Write-Host "Path: $ExePath"
Write-Host "Icon: $IconPath"