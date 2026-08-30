# Para o PostgreSQL local do projeto.

$ErrorActionPreference = "Stop"

$PgHome = if ($env:PGHOME) { $env:PGHOME } else { "C:\Users\RenanHinnen\pgsql" }
$DataDir = Join-Path $PgHome "data"

if (-not (Test-Path (Join-Path $PgHome "bin\pg_ctl.exe"))) {
    Write-Error "PostgreSQL não encontrado em $PgHome. Defina a variável PGHOME."
}

Start-Process -FilePath (Join-Path $PgHome "bin\pg_ctl.exe") `
    -ArgumentList @("-D", "`"$DataDir`"", "-m", "fast", "stop") `
    -NoNewWindow -Wait

Start-Sleep -Seconds 2

if (Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "A porta 5432 ainda responde." -ForegroundColor Yellow
} else {
    Write-Host "PostgreSQL parado." -ForegroundColor Green
}
