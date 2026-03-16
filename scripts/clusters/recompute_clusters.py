import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.services.clustering import run_clustering_for_all_anomalies


def main() -> None:
    with SessionLocal.begin() as session:
        result = run_clustering_for_all_anomalies(session)
    print(
        "clusters: stored "
        f"{result.cluster_count} cluster row(s) covering {result.member_count} anomaly membership row(s)"
    )


if __name__ == "__main__":
    main()
