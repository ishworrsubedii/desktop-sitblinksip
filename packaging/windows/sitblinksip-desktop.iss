; project @ SitBlinkSip Desktop
; author  @ github/ishworrsubedii
;
; Inno Setup script for the Windows installer. Invoked by build-windows.ps1
; after PyInstaller has produced dist\SitBlinkSipDesktop\; it can also be run
; by hand with:
;
;   ISCC.exe /DMyAppVersion=0.1.0 packaging\windows\sitblinksip-desktop.iss

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#define MyAppName "SitBlinkSip Desktop"
#define MyAppId "SitBlinkSipDesktop"
#define MyAppExeName "SitBlinkSipDesktop.exe"
#define MyAppPublisher "Ishwor Subedi"
#define MyAppURL "https://github.com/ishworrsubedii/SitBlinkSip"
#define SourceDir "..\..\dist\SitBlinkSipDesktop"

; The desktop app lives in its own repo but is also vendored inside the main
; SitBlinkSip tree, so LICENSE sits one level up in one layout and three in
; the other. Show it if we can find it, and skip the license page if not,
; rather than failing the build over a path.
#define LicenseInRepo AddBackslash(SourcePath) + "..\..\LICENSE"
#define LicenseInParent AddBackslash(SourcePath) + "..\..\..\LICENSE"
#if FileExists(LicenseInRepo)
  #define ResolvedLicense LicenseInRepo
#elif FileExists(LicenseInParent)
  #define ResolvedLicense LicenseInParent
#endif

[Setup]
AppId={{9F2B1C64-6E1A-4B3D-9A2F-5C7E4D8B1A30}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
#ifdef ResolvedLicense
LicenseFile={#ResolvedLicense}
#endif
OutputDir=..\..\dist
OutputBaseFilename={#MyAppId}-{#MyAppVersion}-setup
SetupIconFile=..\icons\sitblinksip-desktop.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; The app writes only to %APPDATA% and HKCU, so it does not need to be a
; machine-wide install. Defaulting to a per-user install means no UAC prompt;
; users who want it in Program Files for everyone can still choose that.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; "x64compatible" (rather than the deprecated "x64") requires Inno Setup 6.3
; or newer. PyInstaller freezes a 64-bit interpreter, so a 32-bit install
; would produce a package that cannot run.
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller's --onedir output: the launcher plus its _internal tree.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; PyInstaller and Qt drop caches inside the install dir at runtime; without
; this the uninstaller leaves an empty-but-present folder behind.
Type: filesandordirs; Name: "{app}\_internal"

[Registry]
; "Launch on login" is a setting inside the app (it writes this value itself),
; so uninstalling has to clean it up or Windows keeps trying to start a
; program that is no longer there.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "SitBlinkSipDesktop"; Flags: dontcreatekey uninsdeletevalue
