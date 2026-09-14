<#
NUR fuer die lokale Windows-Entwicklungsumgebung -- sichert NICHT den Produktivserver.
Seit dem Produktivbetrieb (siehe CLAUDE.md "Produktivbetrieb") hat der Server sein eigenes,
unabhaengiges Backup unter /home/tobias/backup.sh (taeglich 2 Uhr UTC, 14 Tage Aufbewahrung) --
dieses Skript hier kennt den Server nicht und laeuft dort auch nicht.

Erstellt ein vollstaendiges Backup des lokalen Projekts (Code + Datenbank + hochgeladene
Dateien wie Firmenlogo, Projektdokumente, Layout-Hintergruende, der Verschluesselungs-
schluessel data\.erp_secret) unter C:\DACHKONZEPTE-ERP\Backup -- ein Ordner pro Lauf,
benannt nach VERSION und Zeitstempel.

Ausgeschlossen: .venv, __pycache__, .pytest_cache, .git (reproduzierbar bzw. irrelevant
fuer den Anwendungszustand) sowie Log-Dateien (kein Teil eines "funktionierenden
Zustands", wuerden Backups nur unnoetig aufblasen).

Wird laut CLAUDE.md nach jedem abgeschlossenen Update (jedem VERSION-Bump) ausgefuehrt.
Automatische Bereinigung (seit 1.1.5): nach jedem Lauf bleiben nur die 3 juengsten
Backup-Ordner erhalten, aeltere werden automatisch geloescht.
#>
param(
    [string]$DestinationRoot = "C:\DACHKONZEPTE-ERP\Backup",
    [int]$KeepCount = 3
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = (Get-Content (Join-Path $ProjectRoot "VERSION") -Raw).Trim()
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Destination = Join-Path $DestinationRoot "v${Version}_$Timestamp"

New-Item -ItemType Directory -Path $Destination -Force | Out-Null

robocopy $ProjectRoot $Destination /E `
    /XD ".venv" "__pycache__" ".pytest_cache" ".git" `
    /XF "*.pyc" "erp.log" "erp.log.*" "scratch_uvicorn_out.log" "scratch_uvicorn_err.log" `
    /NFL /NDL /NJH /NP | Out-Null

$RobocopyExitCode = $LASTEXITCODE
if ($RobocopyExitCode -ge 8) {
    Write-Error "Backup fehlgeschlagen (robocopy Exit-Code $RobocopyExitCode) -- Ziel: $Destination"
    exit 1
}

$SizeMB = [math]::Round((Get-ChildItem $Destination -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Output "Backup erstellt: $Destination ($SizeMB MB)"

$OldBackups = Get-ChildItem $DestinationRoot -Directory -Filter "v*_*" | Sort-Object CreationTime -Descending | Select-Object -Skip $KeepCount
foreach ($old in $OldBackups) {
    Remove-Item $old.FullName -Recurse -Force
    Write-Output "Altes Backup entfernt: $($old.FullName)"
}

exit 0
