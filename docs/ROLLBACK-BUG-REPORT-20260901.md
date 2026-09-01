# Rollback — botão reportar bug · 01/09/2026

## Live (após este pacote)

- Branch: `main`
- Feat: `7227c5e` — FAB 🐞 global · API `/api/bug-report/` · lista admin · migrate `core.0003`
- Docs: `39be8bd`

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-bug-report-20260901` | `e403d19` (Live anterior: wizard + OCR) |
| Branch backup | `main-backup-pre-bug-report-20260901` | `e403d19` |
| Tag live | `live/bug-report-20260901` | `39be8bd` |

## Quando reverter

Só com frase explícita + senha **`99738595`** (roteiro §0.3).

Sinais: `/healthz` fora, 500 ao carregar qualquer página logada, erro na migrate `core.0003`.

## Como reverter (assistente)

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-bug-report-20260901
git push origin main --force-with-lease
```

Render redeploya. A tabela `core_bugreport` pode ficar no Postgres (inofensiva). Confirmar `/healthz` → `ok`.

## Alternativa sem force

```powershell
git revert --no-edit 39be8bd
git revert --no-edit 7227c5e
git push origin main
```
