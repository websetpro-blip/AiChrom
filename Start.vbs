Set s = CreateObject("WScript.Shell")
cmd = """" & "C:\\AI\\BrowserVault\\node_modules\\electron\\dist\\electron.exe" & """ " & """" & "C:\\AI\\BrowserVault" & """"
s.Run cmd, 0  ' 0 = без консольного окна
