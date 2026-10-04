; Windows installer of isnady (Inno Setup 6). Built by packaging/build_app.py:
;   iscc /DMyAppVersion=0.1.1 /DSourceDir=dist\isnady /DOutputDir=dist-app packaging\isnady.iss
; Installs for the current user by default (no administrator needed); the installer offers all users too.
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\isnady"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist-app"
#endif

[Setup]
AppId={{6B7C4E2A-3F1D-4C8E-9A51-1D2E3F4A5B6C}
AppName=isnady
AppVersion={#MyAppVersion}
AppPublisher=Bayram Kotan
AppPublisherURL=https://github.com/bayramkotan/isnady
AppSupportURL=https://github.com/bayramkotan/isnady/issues
DefaultDirName={autopf}\isnady
DefaultGroupName=isnady
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#OutputDir}
OutputBaseFilename=isnady-{#MyAppVersion}-windows-setup
SetupIconFile=isnady.ico
UninstallDisplayIcon={app}\isnady.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\isnady"; Filename: "{app}\isnady.exe"
Name: "{group}\{cm:UninstallProgram,isnady}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\isnady"; Filename: "{app}\isnady.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\isnady.exe"; Description: "{cm:LaunchProgram,isnady}"; Flags: nowait postinstall skipifsilent
