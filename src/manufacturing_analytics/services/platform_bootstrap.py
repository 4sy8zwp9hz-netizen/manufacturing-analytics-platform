"""Initialize synthetic sources and publish the first analytical generation."""

from pathlib import Path

from manufacturing_analytics.pipeline.generation_store import GenerationStore
from manufacturing_analytics.pipeline.refresh import RefreshPipeline
from manufacturing_analytics.pipeline.sources import SyntheticSourceFactory, source_adapters


def ensure_platform_data(root: Path) -> tuple[GenerationStore, RefreshPipeline]:
    source_paths = SyntheticSourceFactory(root / "sources").create()
    store = GenerationStore(root / "generations")
    pipeline = RefreshPipeline(source_adapters(source_paths), store)
    if store.current_path() is None:
        pipeline.refresh()
    return store, pipeline
