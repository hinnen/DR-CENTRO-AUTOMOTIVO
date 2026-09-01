# Rollback — busca cliente na entrada (2º+ veículo) · 01/09/2026

## Live (após este pacote)

- Branch: `main`
- Busca cliente cadastrado na placa nova (mobile wizard + desktop cadastro veículo)
- Sem migration nova

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-client-search-20260901` | `b9eb8bd` (Live anterior: bug report) |
| Branch backup | `main-backup-pre-client-search-20260901` | `b9eb8bd` |
| Tag live | `live/client-search-20260901` | `fbd222d` |

## Quando reverter

Só com frase explícita + senha **`99738595`** (roteiro §0.3).

Sinais: `/healthz` fora, entrada mobile 500, busca cliente quebrada.

## Como reverter (assistente)

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-client-search-20260901
git push origin main --force-with-lease
```

Render redeploya. Sem migration nova. Confirmar `/healthz` → `ok`.
