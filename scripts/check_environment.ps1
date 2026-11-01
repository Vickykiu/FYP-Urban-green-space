$ErrorActionPreference = 'Continue'
Write-Host 'Petaling GIS development prerequisites'
foreach ($gisName in @('python', 'node', 'npm.cmd', 'git', 'psql', 'gdalinfo', 'code.cmd')) {
    $gisExecutable = Get-Command $gisName -ErrorAction SilentlyContinue
    if ($gisExecutable) {
        Write-Host ('FOUND  {0}: {1}' -f $gisName, $gisExecutable.Source)
    } else {
        Write-Host ('CHECK  {0}: not on PATH (it may still be installed)' -f $gisName)
    }
}
$gisServices = Get-Service -Name '*postgres*' -ErrorAction SilentlyContinue
if ($gisServices) { $gisServices | Select-Object Name, Status | Format-Table }
else { Write-Host 'CHECK  No PostgreSQL Windows service detected.' }
Write-Host 'See README.md for native Windows setup and project commands.'

