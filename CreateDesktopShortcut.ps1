$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\AiChrome.lnk")
$Shortcut.TargetPath = "$PSScriptRoot\StartAiChrome.bat"
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.IconLocation = "$PSScriptRoot\aichrome.ico"
$Shortcut.Save()
Write-Host "Desktop shortcut created successfully!"