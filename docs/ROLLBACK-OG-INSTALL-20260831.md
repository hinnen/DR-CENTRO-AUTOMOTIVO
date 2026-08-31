# Rollback — preview WhatsApp (.com) + `/m/instalar/` (31/08/2026)

## Live (após este pacote)

- Branch: `main`
- Conteúdo: `SocialPreviewMiddleware` (bots no `/` com og:image 200), `PUBLIC_BASE_URL`, `OG_IMAGE_VERSION=3`, página pública `/m/instalar/`

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-og-install-20260831` | `528474e` (estado Live anterior) |
| Branch backup | `main-backup-pre-og-install-20260831` | `528474e` |
| Tag live | `live/og-install-20260831` | (commit do pacote após push) |

## Quando reverter

Só com frase explícita + senha **`99738595`** (roteiro §0.3).

Sinais: `/healthz` fora, login quebrado, `/` sem redirect para humanos, 502 persistente.

## Como reverter (assistente)

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-og-install-20260831
git push origin main --force-with-lease
```

Render redeploya `main`. Confirmar:

1. `/healthz` → `ok`
2. humano em `/` → 302 `/conta/entrar/`
3. UA WhatsApp em `/` → (após rollback) volta a 302; ícone WA pode precisar rescrape

## Alternativa sem force

```powershell
git revert --no-edit <hash-do-feat-og-install>
git push origin main
```
