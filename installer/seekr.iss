#ifndef MyAppVersion
  #define MyAppVersion "1.0.1"
#endif

#define MyAppName "SeekR"
#define MyAppPublisher "Okyanus Bora Sevik"
#define MyAppExeName "SeekR.exe"

[Setup]
AppId={{A4632DBB-3C2E-46F2-8792-C88C4B50A91A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\icons\seekr.ico
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=SeekR-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\SeekR.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SeekR"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall SeekR"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SeekR"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SeekR"; Flags: postinstall nowait skipifsilent
