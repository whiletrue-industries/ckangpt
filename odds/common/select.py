CONFIG = {
    'Config': 'YAMLConfig',
    'CatalogRepo': 'ConfigCatalogRepo',
    'Store': 'FSStore',
    'LLMRunner': 'OpenAILLMRunner',
    'Embedder': 'OpenAIEmbedder',
    'Indexer': 'ChromaDBIndexer',
    'DBStorage': 'PeeweeDBStorage'
}

def select(kind, context):
    classname = CONFIG[kind]
    klass = context[classname]
    return klass