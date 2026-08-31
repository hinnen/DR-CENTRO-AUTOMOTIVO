# Rollback — placa Nova entrada (fonte + ignora traço) · 31/08/2026

## Live (após este pacote)

- Branch: `main`
- Conteúdo: tipografia maior no campo de placa; JS formata digitação; `find_by_plate` / `normalize_plate` ignora traço (antiga e Mercosul); CTA cadastro mais claro

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-plate-entry-20260831` | `a6c21cf` (Live anterior: OG + /m/instalar) |
| Branch backup | `main-backup-pre-plate-entry-20260831` | `a6c21cf` |
| Tag live | `live/plate-entry-20260831` | (commit do feat após push) |

## Quando reverter

Só com frase explícita + senha **`99738595`** (roteiro §0.3).

Sinais: busca de placa quebrada, Nova entrada sem resultado HTMX, `/healthz` fora.

## Como reverter (assistente)

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-plate-entry-20260831
git push origin main --force-with-lease
```

Confirmar: `/healthz` → `ok` · `/entrada/nova/` carrega · lookup por placa responde.

## Alternativa sem force

```powershell
git revert --no-edit <hash-do-feat-plate-entry>
git push origin main
```
