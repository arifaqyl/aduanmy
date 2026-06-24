from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime import bootstrap_repo_root
from app.services.ingest_service import run_ingest


if __name__ == "__main__":
    bootstrap_repo_root()
    print(run_ingest())
