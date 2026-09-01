# Rollback — fix busca cliente mobile (`name="q"`) · 01/09/2026

## Live (após este pacote)

- HTMX mobile envia parâmetro `q` para `/clientes/buscar/`
- Fallback `client_search_q` na view (compatibilidade)
- Sem migration nova

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-mobile-search-fix-20260901` | `d888d80` |
| Pacote junto | Versão top bar `V: 0.0.1` já em `main` desde `5c5f33c` |

## Como reverter só o hotfix

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-mobile-search-fix-20260901
git push origin main --force-with-lease
```

Confirmar `/healthz` → `ok` · busca mobile volta a não achar (regressão conhecida).
