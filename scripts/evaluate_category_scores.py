from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime import bootstrap_repo_root
from app.db.session import fetch_category_counts
from app.services.scoring_service import score_categories


if __name__ == "__main__":
    bootstrap_repo_root()
    print("raw counts")
    rows = fetch_category_counts()
    for row in rows:
        print(dict(row))
    print("\nscored categories")
    for row in score_categories():
        print(row)
