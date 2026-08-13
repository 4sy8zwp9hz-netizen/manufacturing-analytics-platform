from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from manufacturing_analytics.analytics.platform_service import YieldPlatformService
from manufacturing_analytics.data.platform_repository import PlatformRepository
from manufacturing_analytics.pipeline.generation_store import GenerationStore
from manufacturing_analytics.pipeline.identity import IdentityResolver
from manufacturing_analytics.pipeline.refresh import RefreshPipeline, ScheduledRefresh
from manufacturing_analytics.pipeline.sources import SyntheticSourceFactory, source_adapters


@pytest.fixture
def platform(tmp_path: Path):
    paths = SyntheticSourceFactory(tmp_path / "sources").create()
    store = GenerationStore(tmp_path / "generations")
    pipeline = RefreshPipeline(source_adapters(paths), store)
    result = pipeline.refresh()
    repository = PlatformRepository(store)
    return pipeline, store, repository, result


def test_cross_source_identity_reconciliation_and_explicit_edge_cases(tmp_path: Path) -> None:
    paths = SyntheticSourceFactory(tmp_path / "sources").create()
    aliases = source_adapters(paths)["genealogy"].extract()
    resolver = IdentityResolver(aliases)

    resolved = resolver.resolve("SUBSTRATE_SERIAL", "SUB-700001")
    missing = resolver.resolve("SUBSTRATE_SERIAL", "NOT-KNOWN")
    ambiguous = resolver.resolve("SUBSTRATE_SERIAL", "AMBIGUOUS-SUBSTRATE")

    assert resolved.status == "RESOLVED"
    assert resolved.canonical_wafer == "WAF-000001"
    assert missing.status == "UNRESOLVED" and missing.canonical_wafer is None
    assert ambiguous.status == "AMBIGUOUS" and ambiguous.canonical_wafer is None


def test_transformations_classify_duplicates_revisions_late_data_and_missing_ids(
    platform,
) -> None:
    _, _, repository, _ = platform
    with repository.connect() as connection:
        issue_types = {
            row[0] for row in connection.execute("SELECT issue_type FROM transformation_issues")
        }

    assert {
        "DUPLICATE_RECORD",
        "REVISED_RECORD",
        "LATE_ARRIVAL",
        "FALLBACK_IDENTITY",
        "UNRESOLVED_IDENTITY",
    } <= issue_types


def test_stage_denominators_exclusions_failure_families_and_lineage(platform) -> None:
    _, _, repository, _ = platform
    stages = {row["stage_code"]: row for row in repository.stage_metrics({})}

    assert stages["PROCESS_COMPLETION"]["denominator"] == 60
    assert stages["PROCESS_COMPLETION"]["good"] == 57
    assert stages["CHIP_TEST"]["denominator"] == 57 * 49
    assert stages["CHIP_TEST"]["excluded"] == 3 * 49
    assert stages["SORTING"]["denominator"] == 57 * 49

    with repository.connect() as connection:
        qualification = connection.execute(
            "SELECT COUNT(*) FROM stage_population WHERE stage_code='QUALIFICATION' "
            "AND exclusion_reason='NON_PRODUCTION_POPULATION'"
        ).fetchone()[0]
        lineage_count = connection.execute("SELECT COUNT(*) FROM analytical_lineage").fetchone()[0]
        population_count = connection.execute("SELECT COUNT(*) FROM stage_population").fetchone()[0]
        families = connection.execute(
            "SELECT COUNT(DISTINCT failure_family) FROM stage_population "
            "WHERE failure_family IS NOT NULL"
        ).fetchone()[0]

    assert qualification == 60
    assert lineage_count == population_count
    assert families >= 4


def test_failed_refresh_keeps_previous_known_good_generation(platform) -> None:
    pipeline, store, repository, _ = platform
    previous = store.current_generation_id()

    with pytest.raises(RuntimeError, match="Injected refresh failure"):
        pipeline.refresh(fail_after="transform")

    assert store.current_generation_id() == previous
    assert repository.metadata()["generation_id"] == previous
    assert not list(store.root.glob("*.building.sqlite"))


def test_successful_refresh_atomically_switches_generation(platform) -> None:
    pipeline, store, repository, _ = platform
    previous = store.current_generation_id()
    result = pipeline.refresh()

    assert result["generation_id"] != previous
    assert store.current_generation_id() == result["generation_id"]
    assert repository.metadata()["publication_status"] == "VALIDATED"


def test_scheduled_refresh_runs_only_when_due(platform) -> None:
    pipeline, _, _, _ = platform
    scheduler = ScheduledRefresh(pipeline, timedelta(hours=1))
    now = datetime(2026, 1, 1, tzinfo=UTC)

    first = scheduler.run_if_due(now)
    skipped = scheduler.run_if_due(now + timedelta(minutes=30))
    second = scheduler.run_if_due(now + timedelta(hours=1))

    assert first is not None
    assert skipped is None
    assert second is not None


def test_dashboard_metrics_match_the_underlying_analytical_population(platform) -> None:
    _, _, repository, _ = platform
    dashboard = YieldPlatformService(repository).dashboard({"product": "ORION-A"})
    chip_stage = next(row for row in dashboard["stages"] if row["stage_code"] == "CHIP_TEST")
    rows = repository.population("CHIP_TEST", {"product": "ORION-A"})

    included = [row for row in rows if row["is_denominator"]]
    assert chip_stage["denominator"] == len(included)
    assert chip_stage["good"] == sum(row["is_good"] for row in included)
    assert repository.wafer_trace("WAF-000001")["records"]


def test_trend_supports_date_week_and_month_without_dynamic_user_sql(platform) -> None:
    _, _, repository, _ = platform

    assert repository.trend({}, "date")
    assert repository.trend({}, "week")
    assert repository.trend({}, "month")
    with pytest.raises(ValueError, match="time_grain"):
        repository.trend({}, "month; DROP TABLE stage_population")
