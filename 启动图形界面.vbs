' YouTube HD downloader - GUI launcher (no console window)
' Double-click this file to open the GUI without any black console window.
Set fso = CreateObject("Scripting.FileSystemObject")
Set ws = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

' Prefer full-path pythonw.exe (GUI without console); fall back to PATH
pyw = ws.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe"
If Not fso.FileExists(pyw) Then pyw = "pythonw"

ws.Run """" & pyw & """ """ & dir & "\yt_downloader_gui.py""", 0, False
