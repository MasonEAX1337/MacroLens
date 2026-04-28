import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.repository import (
    fetch_anomaly_detail,
    fetch_dataset_anomalies,
    fetch_dataset_leading_indicators,
    fetch_dataset_timeseries,
    fetch_datasets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export MacroLens API-shaped data into static JSON files for static hosting."
    )
    parser.add_argument(
        "--output-dir",
        default="frontend/public/static-data",
        help="Directory where exported JSON files will be written.",
    )
    parser.add_argument(
        "--timeseries-limit",
        type=int,
        default=500,
        help="Maximum points to export per dataset timeseries.",
    )
    parser.add_argument(
        "--anomalies-limit",
        type=int,
        default=100,
        help="Maximum anomalies to export per dataset.",
    )
    parser.add_argument(
        "--leading-limit",
        type=int,
        default=5,
        help="Maximum leading indicator records to export per dataset.",
    )
    parser.add_argument(
        "--details-limit",
        type=int,
        default=0,
        help="Optional cap on number of anomaly detail files to export (0 means all exported anomalies).",
    )
    return parser.parse_args()


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    with SessionLocal() as session:
        datasets = fetch_datasets(session)
        datasets_json = [item.model_dump(mode="json") for item in datasets]
        dump_json(output_dir / "datasets.json", datasets_json)

        exported_detail_count = 0
        for dataset in datasets:
            dataset_id = dataset.id

            timeseries = fetch_dataset_timeseries(session, dataset_id=dataset_id, limit=args.timeseries_limit)
            anomalies = fetch_dataset_anomalies(session, dataset_id=dataset_id, limit=args.anomalies_limit)
            leading = fetch_dataset_leading_indicators(session, dataset_id=dataset_id, limit=args.leading_limit)

            dump_json(
                output_dir / "datasets" / f"{dataset_id}" / "timeseries.json",
                [item.model_dump(mode="json") for item in timeseries],
            )
            dump_json(
                output_dir / "datasets" / f"{dataset_id}" / "anomalies.json",
                [item.model_dump(mode="json") for item in anomalies],
            )
            dump_json(
                output_dir / "datasets" / f"{dataset_id}" / "leading-indicators.json",
                [item.model_dump(mode="json") for item in leading],
            )

            for anomaly in anomalies:
                if args.details_limit > 0 and exported_detail_count >= args.details_limit:
                    break
                detail = fetch_anomaly_detail(session, anomaly_id=anomaly.id)
                dump_json(
                    output_dir / "anomalies" / f"{anomaly.id}.json",
                    detail.model_dump(mode="json"),
                )
                exported_detail_count += 1

            print(
                f"Dataset {dataset_id} exported: "
                f"{len(timeseries)} points, {len(anomalies)} anomalies, {len(leading)} leading records.",
                flush=True,
            )

        print(
            f"Export complete. Wrote {len(datasets_json)} datasets and {exported_detail_count} anomaly detail files to {output_dir}.",
            flush=True,
        )


if __name__ == "__main__":
    main()
