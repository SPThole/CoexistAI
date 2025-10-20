import hashlib
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from langchain_community.vectorstores import Chroma
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
import chromadb
from chromadb.config import Settings

# Set up logger
logger = logging.getLogger(__name__)

# Global persistent ChromaDB client for better performance
_chroma_client = None
_chroma_persistent_path = "./chroma_db"

def get_chroma_client():
    """Get or create a persistent ChromaDB client with optimized settings."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=_chroma_persistent_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        # Optional: Test connection
        try:
            _chroma_client.heartbeat()  # Verify client is working
        except Exception as e:
            logger.warning(f"ChromaDB client health check failed: {e}")
    
    return _chroma_client

async def create_vectorstore_async(docs, collection_name, hf_embeddings, top_k, ensemble_weights=[0.25, 0.75], local_mode=False, batch_size=32, persist_directory="./chroma_db"):
    """
    Asynchronously creates a vectorstore from the given documents using Chroma and returns an ensemble retriever.
    Uses persistent ChromaDB client with optimized settings for better performance.
    Each subquery gets its own collection for query isolation.

    Args:
        docs (list): A list of documents to be added to the vectorstore.
        collection_name (str): The name of the collection to be used for the vectorstore.
        hf_embeddings (object): The embedding model to be used for the vectorstore.
        top_k (int): The number of documents to retrieve from the vectorstore.
        ensemble_weights (list): Weights for BM25 and semantic retrievers [bm25_weight, semantic_weight]

    Returns:
        EnsembleRetriever: An ensemble retriever that combines BM25 and semantic retrievers.
    """
    # Create unique collection name with timestamp to avoid conflicts
    timestamp = str(int(time.time() * 1000))  # millisecond precision
    if local_mode:
        unique_collection_name = f"{collection_name}"
    else:   
        unique_collection_name = f"{collection_name}_{timestamp}"
    
    # Use thread pool for CPU-intensive operations
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        # Run ChromaDB operations in thread pool
        ensemble_retriever = await loop.run_in_executor(
            executor,
            _create_vectorstore_sync,
            docs, unique_collection_name, hf_embeddings, top_k, ensemble_weights, batch_size, persist_directory
        )
    
    return ensemble_retriever

def _create_vectorstore_sync(docs, unique_collection_name, hf_embeddings, top_k, ensemble_weights, batch_size=8, persist_directory="./chroma_db"):
    """
    Synchronous helper function for creating vectorstore.
    This runs in a thread pool to avoid blocking the event loop.
    """
    try:
        # Use persistent client for the specified directory
        client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # If the collection already exists, load and reuse it instead of recreating.
        existing_collections = [c.name for c in client.list_collections()]

        if unique_collection_name in existing_collections:
            logger.info(f"Collection {unique_collection_name} exists — loading existing vectorstore")
            vectorstore = Chroma(
                client=client,
                collection_name=unique_collection_name,
                embedding_function=hf_embeddings
            )
            # Do not re-add documents to avoid duplicates; assume caller passed docs for BM25
        else:
            # Create vectorstore using the collection
            vectorstore = Chroma(
                client=client,
                collection_name=unique_collection_name,
                embedding_function=hf_embeddings
            )
            # Add documents to vectorstore (only when creating new collection)
            if docs:
                # Try to precompute embeddings in batches to improve performance
                try:
                    texts = [d.page_content for d in docs]
                    metadatas = [getattr(d, 'metadata', {}) for d in docs]
                    embeddings = None
                    # Prefer embed_documents API if available
                    if hasattr(hf_embeddings, 'embed_documents'):
                        try:
                            embeddings = hf_embeddings.embed_documents(texts, batch_size=batch_size)
                        except TypeError:
                            # fallback if batch_size not supported
                            embeddings = hf_embeddings.embed_documents(texts)
                    elif hasattr(hf_embeddings, 'embed'):
                        try:
                            embeddings = hf_embeddings.embed(texts)
                        except Exception:
                            embeddings = None

                    if embeddings is not None:
                        # Add texts with precomputed embeddings
                        try:
                            vectorstore.add_texts(texts=texts, metadatas=metadatas, embeddings=embeddings)
                        except Exception:
                            # Fallback to add_documents if add_texts fails
                            vectorstore.add_documents(docs)
                    else:
                        # No embedding function available; let vectorstore compute embeddings
                        vectorstore.add_documents(docs)
                except Exception as e:
                    logger.warning(f"Batched embedding failed, falling back to add_documents: {e}")
                    try:
                        vectorstore.add_documents(docs)
                    except Exception as e2:
                        logger.error(f"Failed to add documents to vectorstore: {e2}")
        
        # Create retrievers
        sem_retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
        bm25_retriever = BM25Retriever.from_documents(docs)
        bm25_retriever.k = top_k
        
        # Create ensemble retriever with configurable weights
        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, sem_retriever], 
            weights=ensemble_weights
        )
        
        logger.info(f"Created vectorstore with collection: {unique_collection_name}")
        return ensemble_retriever
        
    except Exception as e:
        logger.error(f"Error creating vectorstore: {e}")
        raise

# Keep synchronous version for backward compatibility
def create_vectorstore(docs, collection_name, hf_embeddings, top_k, ensemble_weights=[0.25, 0.75]):
    """
    Synchronous version of create_vectorstore for backward compatibility.
    For better performance, use create_vectorstore_async() instead.
    """
    timestamp = str(int(time.time() * 1000))
    unique_collection_name = f"{collection_name}_{timestamp}"
    return _create_vectorstore_sync(docs, unique_collection_name, hf_embeddings, top_k, ensemble_weights)

async def cleanup_old_collections_async(max_collections=20):
    """
    Asynchronously clean up old ChromaDB collections to prevent memory buildup.
    Keeps only the most recent collections.
    
    Args:
        max_collections (int): Maximum number of collections to keep
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        await loop.run_in_executor(executor, _cleanup_collections_sync, max_collections)

def _cleanup_collections_sync(max_collections):
    """
    Synchronous helper function for cleaning up collections.
    This runs in a thread pool to avoid blocking the event loop.
    """
    try:
        client = get_chroma_client()
        collections = client.list_collections()
        
        if len(collections) > max_collections:
            # Sort collections by name (which includes timestamp) and delete oldest
            sorted_collections = sorted(collections, key=lambda x: x.name)
            collections_to_delete = sorted_collections[:-max_collections]
            
            logger.info(f"Cleaning up {len(collections_to_delete)} old collections")
            
            for collection in collections_to_delete:
                try:
                    client.delete_collection(collection.name)
                    logger.info(f"Deleted old collection: {collection.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete collection {collection.name}: {e}")
        else:
            logger.info(f"Collection count ({len(collections)}) within limit ({max_collections})")
                    
    except Exception as e:
        logger.error(f"Error during collection cleanup: {e}")

# Keep synchronous version for backward compatibility
def cleanup_old_collections(max_collections=20):
    """
    Synchronous version of cleanup_old_collections for backward compatibility.
    For better performance, use cleanup_old_collections_async() instead.
    """
    _cleanup_collections_sync(max_collections)
