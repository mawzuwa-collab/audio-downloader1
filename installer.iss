; installer.iss
; ---------------------------------------------------------------
; Inno Setup Skript zur Erstellung eines Windows-Installers.
; Voraussetzung: Inno Setup (https://jrsoftware.org/isinfo.php)
; und ein vorheriger PyInstaller-Build (dist/AudioDownloader.exe)
;
; Kompilieren mit:  iscc installer.iss
; ---------------------------------------------------------------

#define MyAppName "Audio Downloader"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AudioDownloader Project"
#define MyAppExeName "AudioDownloader.exe"

[Setup]
AppId={{B3F1E2A4-7C5D-4E9A-9F1B-2D6C8E4A1234}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=AudioDownloader_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Symbol erstellen"; GroupDescription: "Zusätzliche Symbole:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; ffmpeg separat mitliefern, falls vorhanden:
Source: "ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} starten"; Flags: nowait postinstall skipifsilent
