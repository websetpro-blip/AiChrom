# Создание ярлыка AiChrome на рабочем столе
$WshShell = New-Object -comObject WScript.Shell
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shortcut = $WshShell.CreateShortcut("$Desktop\AiChrome.lnk")
$Shortcut.TargetPath = "C:\Python313\pythonw.exe"
$Shortcut.Arguments = "C:\AI\AiChrome\AiChrome.pyw"
$Shortcut.WorkingDirectory = "C:\AI\AiChrome"
$Shortcut.IconLocation = "C:\AI\AiChrome\aichrome.ico"
$Shortcut.Description = "AiChrome - Менеджер антидетект браузеров"
$Shortcut.Save()

Write-Host "Ярлык создан на рабочем столе: $Desktop\AiChrome.lnk" -ForegroundColor Green
Write-Host ""
Write-Host "Теперь можно запускать AiChrome с рабочего стола!" -ForegroundColor Cyan
pause
