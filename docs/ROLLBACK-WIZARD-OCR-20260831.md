# Rollback — wizard entrada + OCR Mercosul · 31/08/2026

## Live (após este pacote)

- Branch: `main`
- Feat wizard: `b601b9b` — etapas cliente → queixa → veículo (`?v=15`)
- Feat OCR: `2aafdb0` — Mercosul 5ª=letra + Confirmar/Corrigir
- Docs: `fd80d5c`

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-wizard-ocr-20260831` | `e66b1cb` (Live anterior: primeiro contato) |
| Branch backup | `main-backup-pre-wizard-ocr-20260831` | `e66b1cb` |
| Tag live | `live/wizard-ocr-20260831` | `b601b9b` |

## Quando reverter

Só com frase explícita + senha **`99738595`** (roteiro §0.3).

Sinais: `/healthz` fora, `/m/entrada/` 500, wizard travando abertura de OS, OCR quebrado.

## Como reverter (assistente)

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-wizard-ocr-20260831
git push origin main --force-with-lease
```

Render redeploya. Sem migration nova neste pacote (wizard/OCR). Confirmar `/healthz` → `ok`.

## Alternativa sem force

```powershell
git revert --no-edit b601b9b
git revert --no-edit 2aafdb0
git push origin main
```
