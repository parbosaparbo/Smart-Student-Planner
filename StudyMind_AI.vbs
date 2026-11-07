Set WshShell = CreateObject("WScript.Shell")
strPath = WshShell.CurrentDirectory
WshShell.Run """" & strPath & "\.venv\Scripts\pythonw.exe"" """ & strPath & "\desktop.py""", 0, False

