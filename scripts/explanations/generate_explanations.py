import argparse
import sys
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.explanations import load_anomaly_ids, run_explanation_for_anomaly


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate MacroLens explanations from stored anomaly evidence.")
    parser.add_argument(
        "--anomaly-id",
        type=int,
        default=None,
        help="Generate an explanation only for the specified anomaly id.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Generate explanations for at most this many anomalies.",
    )
    parser.add_argument(
        "--start-after-id",
        type=int,
        default=None,
        help="Skip anomaly ids at or above this id when resuming a descending-id full refresh.",
    )
    parser.add_argument(
        "--provider",
        choices=["rules_based", "openai", "deepseek", "gemini"],
        default=None,
        help="Temporarily override EXPLANATION_PROVIDER for this run.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-anomaly progress output.",
    )
    return parser.parse_args()


def iter_target_anomaly_ids(args: argparse.Namespace) -> Iterator[int]:
    with SessionLocal() as session:
        anomaly_ids = [args.anomaly_id] if args.anomaly_id is not None else load_anomaly_ids(session)

    if args.start_after_id is not None:
        anomaly_ids = [anomaly_id for anomaly_id in anomaly_ids if anomaly_id < args.start_after_id]
    if args.limit is not None:
        anomaly_ids = anomaly_ids[: args.limit]

    yield from anomaly_ids


def main() -> None:
    args = parse_args()
    original_provider = settings.explanation_provider
    if args.provider is not None:
        settings.explanation_provider = args.provider

    total_count = 0
    processed_count = 0
    try:
        target_ids = list(iter_target_anomaly_ids(args))
        for anomaly_id in target_ids:
            with SessionLocal.begin() as session:
                count = run_explanation_for_anomaly(session, anomaly_id)
            total_count += count
            processed_count += 1
            if not args.quiet:
                print(
                    f"explanations: anomaly {anomaly_id} stored {count} row(s) "
                    f"({processed_count}/{len(target_ids)})",
                    flush=True,
                )
    finally:
        settings.explanation_provider = original_provider

    print(f"explanations: stored {total_count} row(s) across {processed_count} anomaly/anomalies")


if __name__ == "__main__":
    main()
