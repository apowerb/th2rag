import os
from datetime import datetime, timezone
from pathlib import Path

# Create local storage directory
LOCAL_STORAGE_DIR = Path("./local_storage/pdfs")
LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def upload_file_locally(file_bytes: bytes, file_name: str) -> str:
    """
    Saves file bytes locally and returns the file path.
    """
    try:
        now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base, ext = os.path.splitext(file_name)
        unique_filename = f"{base}_{now}{ext}"

        file_path = LOCAL_STORAGE_DIR / unique_filename

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        return str(file_path.absolute())
    except Exception as e:
        raise Exception(f"Failed to save file '{file_name}': {e}")


def download_file_locally(file_path: str) -> bytes:
    """
    Reads file bytes from local storage.
    """
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except Exception as e:
        raise Exception(f"Failed to read file from '{file_path}': {e}")


def delete_file_locally(file_path: str) -> None:
    """
    Deletes a file from local storage.
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        raise RuntimeError(f"Failed to delete file {file_path}: {e}")
