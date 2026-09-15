[Setup]
AppName=Doremi
AppVersion=VERSION_PLACEHOLDER
SourceDir=..\..
AppPublisher=Eirom16
AppPublisherURL=https://github.com/Eirom16/doremi
AppSupportURL=https://github.com/Eirom16/doremi/issues
AppUpdatesURL=https://github.com/Eirom16/doremi/releases
DefaultDirName={autopf}\Doremi
DefaultGroupName=Doremi
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=dist\installer
OutputBaseFilename=Doremi-VERSION_PLACEHOLDER-Setup
SetupIconFile=assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "Crear acceso directo en el menú inicio"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\Doremi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Doremi"; Filename: "{app}\Doremi.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\Desinstalar Doremi"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Doremi"; Filename: "{app}\Doremi.exe"; Tasks: desktopicon
Name: "{userstartmenu}\Doremi"; Filename: "{app}\Doremi.exe"; Tasks: startmenuicon

[Run]
Filename: "{app}\Doremi.exe"; Description: "{cm:LaunchProgram,Doremi}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Doremi"
