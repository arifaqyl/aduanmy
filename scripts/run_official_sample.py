from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime import bootstrap_repo_root
from app.collectors.official.client import collect_official_sample


if __name__ == "__main__":
    bootstrap_repo_root()
    print({"count": len(collect_official_sample())})
