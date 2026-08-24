"""Build and publish one synthetic Parquet generation."""

from __future__ import annotations

import json

from manufacturing_analytics.bootstrap import build_services


def main() -> None:
    services = build_services(ensure_ready=False)
    snapshot = services.refresh.refresh(
        preload_delay_seconds=services.settings.sorting_background_delay_seconds
    )
    print(
        json.dumps(
            {
                "generation_id": snapshot.generation_id,
                "published_at": snapshot.published_at,
                "statistics": snapshot.statistics,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
