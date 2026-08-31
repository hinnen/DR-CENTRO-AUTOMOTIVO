# Rollback — OCR mais rápido (warm na tela + 800px) · 31/08/2026

## Live (após este pacote)

- Branch: `main`
- Conteúdo: aquecimento OCR ao abrir `/m/entrada/` (não no boot), resize 800px, ONNX threads, passes lentos enxutos

## Checkpoint (não apagar)

| Tipo | Nome | Commit |
| ---- | ---- | ------ |
| Tag rollback | `rollback/pre-ocr-fast-20260831` | `735c962` (Live anterior: placa Nova entrada) |
| Branch backup | `main-backup-pre-ocr-fast-20260831` | `735c962` |
| Tag live | `live/ocr-fast-20260831` | (commit do feat após push) |

## Quando reverter

Só com frase explícita + senha **`99738595`** (roteiro §0.3).

Sinais: `/healthz` 502, OOM após abrir entrada mobile, OCR quebrado.

## Como reverter (assistente)

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
git fetch origin
git checkout main
git reset --hard rollback/pre-ocr-fast-20260831
git push origin main --force-with-lease
```

Confirmar: `/healthz` → `ok` · login `/m/` · Nova entrada carrega.

## Alternativa sem force

```powershell
git revert --no-edit <hash-do-feat-ocr-fast>
git push origin main
```
