# Rollback — versão na top bar · 01/09/2026

## Live (após este pacote)

- Branch: `main`
- `APP_VERSION` na top bar desktop + `/m/` (default `0.0.1`)
- Sem migration nova

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-app-version-20260901` | `0c42632` (Live anterior: busca cliente) |
| Branch backup | `main-backup-pre-app-version-20260901` | `0c42632` |
| Tag live | `live/app-version-20260901` | `5c5f33c` |

## Como reverter

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-app-version-20260901
git push origin main --force-with-lease
```

Sem migration. Confirmar `/healthz` → `ok`.
