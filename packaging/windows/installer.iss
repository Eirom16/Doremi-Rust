; Doremi — Windows installer (Inno Setup 6).
; FASE F0B-2B.
;
; Per-user install, no elevation, Windows x64.
;
; PATHS: this script lives in packaging\windows but compiles from ANY working
; directory. All repo paths are absolute via the ISPP preprocessor
; (SourcePath = directory of THIS script, always available in Inno Setup 6):
;   iscc packaging\windows\installer.iss
; Do NOT use bare relative paths here: [Setup] file directives resolve
; against the script directory while SourceDir governs [Files], so relative
; paths break depending on the compiler's CWD (seen empirically: "system
; cannot find the path specified" for SetupIconFile with SourceDir=..\..).
#define RepoRoot SourcePath + "\\..\\.."
;
; Version stamping: CI runs packaging/windows/stamp_installer_version.py
; (reads pyproject.toml) before compiling, so AppVersion and
; OutputBaseFilename always match the tagged build. The committed values
; below are the current release (2.1.4).
;
; Architecture directives: Inno Setup >= 6.3 deprecated the "x64"
; identifier (compiler warns and substitutes "x64os"). This script uses
; "x64compatible" (x64 Windows + ARM64 Windows 11 via emulation), as
; recommended by JRSoftware docs for x64 app installers:
;   https://jrsoftware.org/ishelp/topic_archidentifiers.htm
;   https://jrsoftware.org/ishelp/topic_setup_architecturesinstallin64bitmode.htm
; CI pins Inno Setup 6 (choco innosetup; observed 6.7.1) which accepts these
; directives (no arch warnings in the build log).
;
; AppId: first stable identity for Doremi (no AppId existed before F0B-2B;
; git history shows installer.iss never carried one, so there is no legacy
; identity to preserve). This GUID MUST stay stable across future updates
; or Windows will treat upgrades as separate products.
;   AppId = {b2285fdf-22de-411a-93b2-4ce4d8a5fa8a}
;
; DATA PROTECTION: this script intentionally contains NO [UninstallDelete]
; section. A previous draft deleted "{localappdata}\Doremi", which could
; destroy user data (and AppDirs does not even use %LOCALAPPDATA%: real
; user data lives under XDG paths, see src/doremi/config/paths.py).
; The uninstaller removes only files it installed under {app}.

[Setup]
AppId={{b2285fdf-22de-411a-93b2-4ce4d8a5fa8a}}
AppName=Doremi
AppVersion=2.1.4
AppVerName=Doremi v2.1.4
VersionInfoVersion=2.1.4.0
AppPublisher=Eirom16
AppPublisherURL=https://github.com/Eirom16/Doremi-Rust
AppSupportURL=https://github.com/Eirom16/Doremi-Rust/issues
AppUpdatesURL=https://github.com/Eirom16/Doremi-Rust/releases
DefaultDirName={autopf}\Doremi
DefaultGroupName=Doremi
AllowNoIcons=yes
LicenseFile={#RepoRoot}\LICENSE
OutputDir={#RepoRoot}\dist\installer
OutputBaseFilename=Doremi-v2.1.4-Setup
SetupIconFile={#RepoRoot}\assets\icon.ico
UninstallDisplayIcon={app}\Doremi.exe
UninstallDisplayName=Doremi
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=yes
UsePreviousAppDir=yes
DirExistsWarning=yes
DisableProgramGroupPage=auto

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#RepoRoot}\dist\Doremi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "{#RepoRoot}\packaging\windows\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Doremi"; Filename: "{app}\Doremi.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\Desinstalar Doremi"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Doremi"; Filename: "{app}\Doremi.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\Doremi.exe"; Description: "{cm:LaunchProgram,Doremi}"; Flags: nowait postinstall skipifsilent
