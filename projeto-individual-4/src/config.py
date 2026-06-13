from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
DB_PATH = DATA_DIR / "conjuntura.db"
DEFAULT_DB_URL = f"sqlite:///{DB_PATH}"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
