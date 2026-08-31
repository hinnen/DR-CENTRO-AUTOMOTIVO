"""Importação e exportação Excel de cadastros."""

from pathlib import Path
from tempfile import NamedTemporaryFile

from .common import read_spreadsheet
from .sheets import ImportSummary, build_export_workbook, import_workbook

__all__ = [
    "ImportSummary",
    "build_export_workbook",
    "import_uploaded_file",
    "read_spreadsheet",
]


def import_uploaded_file(*, upload, actor) -> ImportSummary:
    suffix = Path(upload.name or "planilha.xlsx").suffix or ".xlsx"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in upload.chunks():
            tmp.write(chunk)
        path = Path(tmp.name)
    try:
        sheets = read_spreadsheet(path)
        return import_workbook(sheets=sheets, actor=actor)
    finally:
        path.unlink(missing_ok=True)
