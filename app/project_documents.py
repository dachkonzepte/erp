import os
from pathlib import Path

from .document_storage import can_preview_type, is_image_type, make_stored_filename  # noqa: F401 -- Re-Export für Bestandscode
from .models import ProjectDocument
from .paths import data_dir

PROJECT_ROOT = Path(os.getenv("DACHKONZEPTE_PROJECT_FILE_ROOT", data_dir() / "project_files"))
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def project_directory(project_id: int) -> Path:
    path = PROJECT_ROOT / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def document_path(document: ProjectDocument) -> Path:
    return PROJECT_ROOT / str(document.project_id) / document.stored_filename
