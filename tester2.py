import sys
from odds.common.embedder import embedder
from odds.common.vectordb import indexer
from odds.common.store import store

async def main():
    query = sys.argv[1]
    b = await embedder.embed(query)
    ids = await indexer.findDatasets(b)
    datasets = [await store.getDataset(id) for id in ids]
    for dataset in datasets:
        print(' - ' + dataset.better_title)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())