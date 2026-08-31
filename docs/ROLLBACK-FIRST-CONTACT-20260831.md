# Rollback — primeiro contato mobile (`/m/`) · 31/08/2026

## Live (após este pacote)

- Branch: `main`
- Feat: `e66b1cb` — queixa, nome no retorno, Normal/Urgente, `brought_by_name`, forms reordenados
- Docs: `c68908a`

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-first-contact-20260831` | `25137d0` (Live anterior: OCR-fast) |
| Branch backup | `main-backup-pre-first-contact-20260831` | `25137d0` |
| Tag live | `live/first-contact-20260831` | `e66b1cb` |

## Quando reverter

Só com frase explícita + senha **`99738595`** (roteiro §0.3).

Sinais: `/healthz` fora, `/m/entrada/` 500, migrate falhou, OS sem abrir.

## Como reverter (assistente)

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-first-contact-20260831
git push origin main --force-with-lease
```

Render redeploya. A coluna `brought_by_name` pode ficar no Postgres (inofensiva). Confirmar `/healthz` → `ok`.

## Alternativa sem force

```powershell
git revert --no-edit e66b1cb
git push origin main
```
