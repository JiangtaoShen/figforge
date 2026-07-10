; FigForge Windows installer (Inno Setup 6.5+)
;
; Build locally:   iscc /DMyAppVersion=0.3.0 installer\FigForge.iss
; Built in CI by .github/workflows/release.yml after PyInstaller, from
; the onedir bundle in dist\FigForge.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "FigForge"
#define MyAppExeName "FigForge.exe"
#define MyAppPublisher "FigForge"
#define MyAppURL "https://github.com/JiangtaoShen/figforge"

[Setup]
AppId={{6388F3B7-F1EC-4297-9AC7-585CC0ED99E9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\figforge\resources\icon.ico
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
; per-user install by default (no UAC prompt); the dialog lets the user
; pick an all-users install into Program Files instead
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
CloseApplications=yes
OutputDir=..
OutputBaseFilename=FigForge-v{#MyAppVersion}-windows-x64-setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\FigForge\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
  Tasks: desktopicon

[Registry]
; .ffp project files open with FigForge on double-click
Root: HKA; Subkey: "Software\Classes\.ffp"; ValueType: string; \
  ValueData: "FigForge.Project"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\FigForge.Project"; ValueType: string; \
  ValueData: "FigForge Project"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\FigForge.Project\DefaultIcon"; \
  ValueType: string; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\FigForge.Project\shell\open\command"; \
  ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#MyAppName}}"; \
  Flags: nowait postinstall skipifsilent
