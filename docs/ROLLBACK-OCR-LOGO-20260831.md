# Rollback — pacote OCR rápido + logo DR (31/08/2026)

## Live

- Branch: `main`
- Pacote: `5fe941b` (OCR KEEP_LOADED + logo) · docs `0196914`/`fb269b5`
- Pré-pacote (seguro): **`a887ab1`** — OCR lazy já ligado, **sem** KEEP_LOADED e **sem** logo nova

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-ocr-logo-20260831` | `a887ab1` |
| Branch backup | `main-backup-pre-ocr-logo-20260831` | `a887ab1` |
| Tag live | `live/ocr-logo-20260831` | `5fe941b` |

## Quando reverter

Só com frase explícita + senha **`99738595`** (roteiro §0.3).

Sinais: `/healthz` 502 persistente, OOM após Fotografar placa, site morto no Starter.

## Como reverter (assistente)

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-ocr-logo-20260831
git push origin main --force-with-lease
```

Render redeploya `main`. Confirmar `/healthz` → `ok`.

## Alternativa sem force

```powershell
git revert --no-edit 5fe941b
git push origin main
```

(Reverte só o feat; deixa commits de docs.)
