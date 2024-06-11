import asyncio

from .resource_processor import ResourceProcessor
from .meta_describer import MetaDescriber
from .dataset_embedder import DatasetEmbedder
from .dataset_indexer import DatasetIndexer
from ...common.datatypes import Dataset, DataCatalog
from ...common.store import store
from ...common.db import db
from ...common.config import config
from ...common.filters import DatasetFilter
from ...common.realtime_status import realtime_status as rts


class DatasetProcessor:

    tasks: list[asyncio.Task] = []

    def __init__(self) -> None:
        self.resource_processor = ResourceProcessor()
        self.meta_describer = MetaDescriber()
        self.embedder = DatasetEmbedder()
        self.indexer = DatasetIndexer()

    def set_concurrency(self, limit: int):
        self.resource_processor.set_concurrency_limit(limit)

    def queue(self, dataset: Dataset, catalog: DataCatalog, datasetFilter: DatasetFilter, ctx: str):
        rts.set(ctx, f'QUEUE DATASET {dataset.title}')
        self.tasks.append(asyncio.create_task(self.process(dataset, catalog, datasetFilter, ctx)))

    async def wait(self):
        await asyncio.gather(*self.tasks)

    async def process(self, dataset: Dataset, catalog: DataCatalog, datasetFilter: DatasetFilter, ctx: str):
        if config.debug:
            rts.set(ctx, f'PROCESS DATASET {dataset.versions.get('resource_analyzer')} {dataset.title}')
        resources = self.prune_resources(dataset, ctx)
        if await datasetFilter.analyze(datasetFilter):
            if len(resources) > 0:
                await asyncio.gather(
                    *[
                        self.resource_processor.process(resource, dataset, catalog, ctx + f'/RES.{resource.file_format}[{i}]')
                        for i, resource in enumerate(resources)
                    ]
                )
        else:
            if config.debug:
                rts.set(ctx, f'SKIP ANALYZE')
        resources = [resource for resource in resources if resource.status_loaded]
        if len(resources) > 0:
            if await datasetFilter.describe(dataset):
                await self.meta_describer.describe(dataset, ctx)
            else:
                if config.debug:
                    rts.set(ctx, f'SKIP DESCRIBE')
            if await datasetFilter.embed(dataset):
                await self.embedder.embed(dataset, ctx)
            if await datasetFilter.index(dataset):
                await self.indexer.index(dataset, ctx)
        await store.storeDataset(dataset, ctx)
        await db.storeDataset(dataset, ctx)
        rts.clear(ctx)

    def prune_resources(self, dataset: Dataset, ctx: str):
        resources = dataset.resources
        resources = [resource for resource in resources if ResourceProcessor.check_format(resource)]
        resource_names = {}
        for resource in resources:
            format_idx = ResourceProcessor.format_idx(resource)
            resource_names.setdefault(resource.title, format_idx)
            if resource_names[resource.title] > format_idx:
                resource_names[resource.title] = format_idx
        if config.debug:
            rts.set(ctx, f'RESOURCE NAMES {dataset.title} {resource_names}')
        resources = [resource for resource in resources if ResourceProcessor.format_idx(resource) == resource_names[resource.title]]
        return resources