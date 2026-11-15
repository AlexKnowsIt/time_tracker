; Inno-Setup-Skript für die Windows-App. Aufruf (Projektordner):
;   iscc /DAppVersion=1.2.3 desktop\zeiterfassung.iss
; Voraussetzung: PyInstaller-Ergebnis in dist\Zeiterfassung. Ausgabe: out\Zeiterfassung-Setup-1.2.3.exe
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B0B6F0A-4F7B-4C7E-9E0A-5A3C1D2E7F41}
AppName=Zeiterfassung
AppVersion={#AppVersion}
AppPublisher=alexknowsit
AppPublisherURL=https://github.com/alexknowsit/time_tracker
DefaultDirName={autopf}\Zeiterfassung
DefaultGroupName=Zeiterfassung
UninstallDisplayIcon={app}\Zeiterfassung.exe
OutputDir=..\out
OutputBaseFilename=Zeiterfassung-Setup-{#AppVersion}
SetupIconFile=zeiterfassung.ico
Compression=lzma2
SolidCompression=yes
; Installation nur für den aktuellen Nutzer, keine Administratorrechte nötig
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
InfoAfterFile=hinweis.txt

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop erstellen"; Flags: unchecked

[Files]
Source: "..\dist\Zeiterfassung\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Zeiterfassung"; Filename: "{app}\Zeiterfassung.exe"
Name: "{autodesktop}\Zeiterfassung"; Filename: "{app}\Zeiterfassung.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Zeiterfassung.exe"; Description: "Zeiterfassung starten"; Flags: nowait postinstall skipifsilent

[Code]
// Die Deinstallation löscht bewusst nur das Programm, nicht die Daten.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    MsgBox('Ihre Daten bleiben erhalten und liegen weiter in:' + #13#10 +
      ExpandConstant('{localappdata}\Zeiterfassung') + #13#10 + #13#10 +
      'Löschen Sie diesen Ordner, wenn Sie sie nicht mehr brauchen.',
      mbInformation, MB_OK);
end;
