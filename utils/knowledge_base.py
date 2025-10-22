import os
import hashlib
from utils.websearch_utils import urls_to_docs, get_all_paths
from utils.retriever_utils import create_vectorstore_async
from chromadb.config import Settings
import chromadb
import logging
from langchain_text_splitters import TokenTextSplitter

async def create_knowledge_base(document_paths, hf_embeddings):
    """
    Creates a knowledge base from the given paths by extracting all files,
    processing them into documents, embedding them, and saving to ChromaDB local.

    Args:
        document_paths (list or str): List of paths or a single path to process.
        hf_embeddings: Hugging Face embeddings instance.

    Returns:
        str: The name of the created vector database collection.
    """
    logger = logging.getLogger(__name__)

    if isinstance(document_paths, str):
        document_paths = [document_paths]

    all_paths = []
    for k in document_paths:
        paths = get_all_paths(k)
        if paths:
            all_paths.extend(paths)

    if not all_paths:
        raise ValueError("No files found in the provided paths.")

    all_paths = [all_paths]  # Make it list of lists as expected

    logger.info(f"Found {len(all_paths[0])} file paths to process")

    # Process documents
    docs_map = await urls_to_docs(all_paths[0], local_mode=True, split=False)

    logger.info(f"docs_map has {len(docs_map)} entries")
    for url, docs in docs_map.items():
        logger.info(f"URL {url}: {len(docs)} docs")

    all_docs = []
    for docs in docs_map.values():
        all_docs.extend(docs)

    logger.info(f"Total documents before splitting: {len(all_docs)}")

    # Split documents
    text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=128)
    all_docs = text_splitter.split_documents(all_docs)

    logger.info(f"Total documents after splitting: {len(all_docs)}")

    if not all_docs:
        raise ValueError("No documents could be processed.")

    # Create collection name based on hash of paths
    sorted_paths = ''.join(sorted(all_paths[0]))
    collection_name = f"kb-{hashlib.md5(sorted_paths.encode()).hexdigest()[:8]}"

    # Delete existing collection if it exists to ensure fresh creation
    client = chromadb.PersistentClient(path="./chroma_db", settings=Settings(anonymized_telemetry=False, allow_reset=True))
    try:
        client.delete_collection(collection_name)
        logger.info(f"Deleted existing collection {collection_name}")
    except Exception as e:
        logger.info(f"Collection {collection_name} not found or error deleting: {e}")

    collections_after_delete = [c.name for c in client.list_collections()]
    logger.info(f"Collections after delete: {collections_after_delete}")

    # Create and save vectorstore
    try:
        await create_vectorstore_async(
            docs=all_docs,
            collection_name=collection_name,
            hf_embeddings=hf_embeddings,
            top_k=3,
            ensemble_weights=[0.4, 0.6],
            local_mode=True,
            persist_directory="./chroma_db"
        )
        logger.info(f"create_vectorstore_async completed for {collection_name}")
    except Exception as e:
        logger.error(f"Error in create_vectorstore_async: {e}")
        raise

    # Verify the collection was created with documents
    collections = client.list_collections()
    collection_names = [c.name for c in collections]
    if collection_name in collection_names:
        count = client.get_collection(collection_name).count()
        logger.info(f"Collection {collection_name} successfully created with {count} documents")
    else:
        logger.error(f"Collection {collection_name} not found after creation")

    return collection_name
