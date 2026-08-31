"""Leitura de placas brasileiras (Mercosul e antiga).

Usa ``platerec`` (ONNX treinado em placas BR). O OCR genérico no celular
(Tesseract.js) falhava em fotos reais do pátio.

Placas cinza antigas falham com mais facilidade na deteccao (EXIF deitado,
limiar alto, contraste baixo) — por isso tentamos variantes antes de desistir.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from io import BytesIO

from django.core.exceptions import ValidationError
from PIL import Image, ImageEnhance, ImageOps

from apps.vehicles.models import PLATE_MERCOSUL_RE, PLATE_OLD_RE, normalize_plate

logger = logging.getLogger(__name__)

# Prefixo de regiao que o platerec devolve, ex.: "[br]REI5G32"
_REGION_PREFIX = re.compile(r"^\[[a-z]{2}\]", re.IGNORECASE)

# Letras que o modelo troca por digito em placa antiga (5a posicao).
_OLD_DIGIT_LOOKALIKES = frozenset("ILO")

_DIGIT_FROM_LETTER = str.maketrans(
    {
        "O": "0",
        "D": "0",
        "Q": "0",
        "I": "1",
        "L": "1",
        "S": "5",
        "B": "8",
        "Z": "2",
        "G": "6",
        "A": "4",
    }
)
_LETTER_FROM_DIGIT = str.maketrans(
    {
        "0": "O",
        "1": "I",
        "5": "S",
        "8": "B",
        "2": "Z",
        "4": "A",
        "6": "G",
    }
)

_DETECT_THRESHOLDS = (0.4, 0.25, 0.15)
# Para na primeira deteccao com confianca alta (evita 2º/3º limiar).
_CONF_EARLY_EXIT = 0.42
_OCR_MAX_SIDE = 1280


def _ocr_enabled() -> bool:
    from django.conf import settings

    return bool(getattr(settings, "ENABLE_PLATE_OCR", False))


@lru_cache(maxsize=1)
def _engine():
    if not _ocr_enabled():
        raise ValidationError(
            "Leitura automática da placa está desligada neste ambiente.",
            code="ocr_disabled",
        )

    try:
        from platerec import Platerec
    except ImportError as exc:
        raise ValidationError(
            "OCR de placa indisponível neste ambiente (platerec não instalado).",
            code="ocr_unavailable",
        ) from exc

    return Platerec(providers=["CPUExecutionProvider"])


def release_engine() -> None:
    """Libera o modelo ONNX da memória (Starter ~512 MB)."""
    _engine.cache_clear()


def warmup_engine() -> None:
    """Carrega o modelo ONNX no boot (só se PLATE_OCR_WARMUP=1)."""
    _engine()


def _strip_region(raw: str) -> str:
    return _REGION_PREFIX.sub("", (raw or "").strip())


def _fix_mercosul(plate: str) -> str:
    if len(plate) != 7:
        return plate
    chars = list(plate)
    for idx in (0, 1, 2, 4):
        if chars[idx].isdigit():
            chars[idx] = chars[idx].translate(_LETTER_FROM_DIGIT)
    for idx in (3, 5, 6):
        if chars[idx].isalpha():
            chars[idx] = chars[idx].translate(_DIGIT_FROM_LETTER)
    return "".join(chars)


def _fix_old(plate: str) -> str:
    if len(plate) != 7:
        return plate
    chars = list(plate)
    for idx in (0, 1, 2):
        if chars[idx].isdigit():
            chars[idx] = chars[idx].translate(_LETTER_FROM_DIGIT)
    for idx in (3, 4, 5, 6):
        if chars[idx].isalpha():
            chars[idx] = chars[idx].translate(_DIGIT_FROM_LETTER)
    return "".join(chars)


def _candidates_from_raw(raw: str) -> list[str]:
    base = normalize_plate(_strip_region(raw))
    if not base:
        return []
    out = [base, _fix_mercosul(base), _fix_old(base)]
    # Janelas de 7 se veio lixo colado.
    if len(base) > 7:
        for i in range(len(base) - 6):
            chunk = base[i : i + 7]
            out.extend([chunk, _fix_mercosul(chunk), _fix_old(chunk)])
    # Dedup preservando ordem
    seen = set()
    ordered = []
    for item in out:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _score(plate: str) -> int:
    # Mercosul e antiga no mesmo nivel — a confianca + desempate decidem.
    if PLATE_MERCOSUL_RE.match(plate) or PLATE_OLD_RE.match(plate):
        return 100
    return -1


def _prefer_old_over_mercosul(candidates: list[str]) -> list[str]:
    """Se a 5a letra parece digito (I/L/O), placa antiga costuma ser a correta."""
    mercosul_hits = [c for c in candidates if PLATE_MERCOSUL_RE.match(c)]
    old_hits = [c for c in candidates if PLATE_OLD_RE.match(c)]
    if not (mercosul_hits and old_hits):
        return candidates

    for merc in mercosul_hits:
        if len(merc) != 7 or merc[4] not in _OLD_DIGIT_LOOKALIKES:
            continue
        fixed_old = _fix_old(merc)
        if fixed_old in old_hits and PLATE_OLD_RE.match(fixed_old):
            return [fixed_old] + [c for c in candidates if c != merc]
    return candidates


def _pick_best(words: list[str], confidences: list[float] | None = None) -> tuple[str, float]:
    best_plate = ""
    best_score = -1.0
    best_conf = 0.0
    confidences = confidences or [0.0] * len(words)

    for word, conf in zip(words, confidences):
        candidates = _prefer_old_over_mercosul(_candidates_from_raw(word))

        for candidate in candidates:
            score = _score(candidate)
            ranked = score * 10 + float(conf or 0)
            if score > 0 and ranked > best_score:
                best_score = ranked
                best_plate = candidate
                best_conf = float(conf or 0)

    return best_plate, best_conf


def _resize_for_ocr(image: Image.Image, max_side: int = _OCR_MAX_SIDE) -> Image.Image:
    w, h = image.size
    scale = min(1.0, max_side / max(w, h))
    if scale >= 1.0:
        return image
    return image.resize(
        (max(1, int(w * scale)), max(1, int(h * scale))),
        Image.Resampling.LANCZOS,
    )


def _detect_read(engine, image: Image.Image, conf_threshold: float) -> dict:
    """detect_read do platerec com limiar configuravel (default interno e 0.4)."""
    words: list[str] = []
    words_confidences: list[float] = []
    boxes = []

    output = engine.platedet.inference(
        image,
        return_types=["pil", "boxes"],
        conf_threshold=conf_threshold,
    )
    if not output:
        return {"boxes": [], "words": [], "words_confidences": []}

    boxes_payload = output.get("boxes") or {}
    boxes = boxes_payload.get("boxes")
    if boxes is None:
        boxes = []
    pil_payload = output.get("pil") or {}
    crops = pil_payload.get("images") or []
    for crop in crops:
        pred = engine.read(crop)
        words.append(pred.get("word") or "")
        words_confidences.append(float(pred.get("confidence") or 0))

    return {
        "boxes": boxes,
        "words": words,
        "words_confidences": words_confidences,
    }


def _try_image(engine, image: Image.Image, *, thorough: bool = False) -> tuple[str, float, list[str]]:
    all_words: list[str] = []
    all_confs: list[float] = []
    thresholds = _DETECT_THRESHOLDS if thorough else _DETECT_THRESHOLDS[:2]

    for threshold in thresholds:
        result = _detect_read(engine, image, threshold)
        words = list(result.get("words") or [])
        confs = list(result.get("words_confidences") or [])
        all_words.extend(words)
        all_confs.extend(confs)
        plate, confidence = _pick_best(words, confs)
        if plate and (not thorough or confidence >= _CONF_EARLY_EXIT):
            return plate, confidence, words

    if thorough:
        try:
            direct = engine.read(image)
            word = direct.get("word") or ""
            conf = float(direct.get("confidence") or 0)
            all_words.append(word)
            all_confs.append(conf)
            plate, confidence = _pick_best([word], [conf])
            if plate:
                return plate, confidence, all_words
        except Exception:
            logger.exception("Fallback platerec.read falhou")

    plate, confidence = _pick_best(all_words, all_confs)
    return plate, confidence, all_words


def _fast_variants(image: Image.Image) -> list[Image.Image]:
    """Original + contraste — cobre a maioria das fotos bem enquadradas."""
    contrast = ImageEnhance.Contrast(image).enhance(1.6)
    return [image, contrast]


def _slow_variants(image: Image.Image) -> list[Image.Image]:
    """Rotacoes e nitidez — so quando o passe rapido falha."""
    variants: list[Image.Image] = []
    for degrees in (90, 270, 180):
        variants.append(image.rotate(degrees, expand=True))

    contrast = ImageEnhance.Contrast(image).enhance(1.6)
    variants.append(ImageEnhance.Sharpness(contrast).enhance(1.4))

    w, h = image.size
    if max(w, h) < 900:
        variants.append(image.resize((w * 2, h * 2), Image.Resampling.LANCZOS))

    return variants


def _image_variants(image: Image.Image) -> list[Image.Image]:
    """Mantido para testes; producao usa fast + slow em sequencia."""
    return _fast_variants(image) + _slow_variants(image)


def read_plate_from_image(image: Image.Image) -> dict:
    """Detecta e le a placa. Devolve ``{plate, confidence, raw}`` ou erro."""
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        image = image.convert("RGB")

    image = _resize_for_ocr(image)

    try:
        try:
            engine = _engine()
        except ValidationError:
            raise
        except Exception:
            logger.exception("Falha ao iniciar platerec")
            raise ValidationError("Não foi possível analisar a foto da placa.")

        raw_words: list[str] = []
        plate = ""
        confidence = 0.0

        try:
            for variant in _fast_variants(image):
                plate, confidence, words = _try_image(engine, variant, thorough=False)
                raw_words.extend(words)
                if plate:
                    break

            if not plate:
                for variant in _slow_variants(image):
                    plate, confidence, words = _try_image(engine, variant, thorough=True)
                    raw_words.extend(words)
                    if plate:
                        break
        except ValidationError:
            raise
        except Exception:
            logger.exception("Falha ao rodar platerec")
            raise ValidationError("Não foi possível analisar a foto da placa.")

        if not plate:
            raise ValidationError(
                "Não deu para ler a placa. Aproxime a câmera e tente de novo, ou digite."
            )

        # Dedup raw para debug leve
        seen = set()
        unique_raw = []
        for word in raw_words:
            if word and word not in seen:
                seen.add(word)
                unique_raw.append(word)

        return {
            "plate": plate,
            "confidence": round(confidence, 4),
            "raw": unique_raw,
        }
    finally:
        # Starter: não deixar ONNX residente entre fotos (evita 502 por memória).
        release_engine()


def read_plate_from_upload(upload) -> dict:
    """Le placa a partir de um UploadedFile do Django."""
    from django.conf import settings

    max_mb = int(getattr(settings, "MAX_UPLOAD_SIZE_MB", 10))
    max_bytes = max_mb * 1024 * 1024
    size = getattr(upload, "size", None)
    if size is not None and size > max_bytes:
        raise ValidationError(f"A foto da placa deve ter no máximo {max_mb} MB.")

    try:
        upload.seek(0)
        # Lê no máximo o limite + 1 byte para arquivos sem size confiável.
        payload = upload.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ValidationError(f"A foto da placa deve ter no máximo {max_mb} MB.")
        image = Image.open(BytesIO(payload))
        image.load()
    except ValidationError:
        raise
    except Exception as error:
        raise ValidationError("Arquivo de imagem inválido.") from error
    finally:
        try:
            upload.seek(0)
        except Exception:
            pass
    return read_plate_from_image(image)
