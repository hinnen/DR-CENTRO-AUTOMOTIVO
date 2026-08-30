# Inicia o PostgreSQL local do projeto.
#
# Os binários foram instalados sem privilégio de administrador, então o
# PostgreSQL não roda como serviço do Windows: precisa ser iniciado depois
# de cada reinicialização da máquina.

$ErrorActionPreference = "Stop"

$PgHome = if ($env:PGHOME) { $env:PGHOME } else { "C:\Users\RenanHinnen\pgsql" }
$DataDir = Join-Path $PgHome "data"
$LogFile = Join-Path $PgHome "postgres.log"

if (-not (Test-Path (Join-Path $PgHome "bin\pg_ctl.exe"))) {
    Write-Error "PostgreSQL não encontrado em $PgHome. Defina a variável PGHOME."
}

$running = Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "PostgreSQL já está rodando na porta 5432." -ForegroundColor Yellow
    exit 0
}

# Sem -Wait: o postmaster herda o console e faria o script travar mesmo
# depois de o servidor já estar no ar. Em vez disso, aguardamos a porta.
Start-Process -FilePath (Join-Path $PgHome "bin\pg_ctl.exe") `
    -ArgumentList @("-D", "`"$DataDir`"", "-l", "`"$LogFile`"", "-o", "`"-p 5432 -h 127.0.0.1`"", "start") `
    -WindowStyle Hidden

foreach ($attempt in 1..20) {
    Start-Sleep -Seconds 1
    if (Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "PostgreSQL rodando em 127.0.0.1:5432" -ForegroundColor Green
        exit 0
    }
}

Write-Host "Falha ao iniciar. Últimas linhas do log:" -ForegroundColor Red
Get-Content $LogFile -Tail 15
exit 1
