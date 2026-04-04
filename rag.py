"""
rag.py — The RAG (Retrieval-Augmented Generation) layer.

What this does:
- Stores past pipeline failures as vector embeddings in ChromaDB
- When a new failure comes in, we embed the error text and find the
  most semantically similar past failures
- This gives the LLM real examples of "this error happened before, here's what fixed it"

Why ChromaDB?
- Runs locally, no external service needed
- PersistentClient saves to disk, so data survives restarts
- SentenceTransformer embeddings are free and run on CPU

The embedding model (all-MiniLM-L6-v2) converts text → 384-dim vector.
Similar texts have high cosine similarity. ChromaDB searches by that similarity.
"""
import chromadb
from chromadb.utils import embedding_functions


# PersistentClient writes to ./chroma_db/ on disk
# Use chromadb.Client() instead if you want in-memory (wipes on restart)
_client = chromadb.PersistentClient(path="./chroma_db")

# This embedding model runs locally — no API key needed
# It's small (~90MB) but good enough for error message similarity
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# get_or_create: safe to call repeatedly, won't duplicate the collection
_collection = _client.get_or_create_collection(
    name="pipeline_failures",
    embedding_function=_embedding_fn,
    # cosine distance: 0 = identical, 2 = opposite
    # We convert to similarity % later: (1 - distance) * 100
    metadata={"hnsw:space": "cosine"}
)


def add_failure(id: str, failure_text: str, metadata: dict) -> None:
    """
    Embed and store one past failure.

    failure_text is what gets embedded — make it descriptive.
    metadata stores the human-readable fields (not embedded, just stored).
    """
    _collection.add(
        documents=[failure_text],
        metadatas=[metadata],
        ids=[id]
    )


def search_failures(query: str, n_results: int = 3) -> list[dict]:
    """
    Find the n most similar past failures to the query string.

    Returns a list of dicts with:
      - content: the original text that was embedded
      - metadata: the dict passed to add_failure
      - distance: cosine distance (lower = more similar)
    """
    # Guard: ChromaDB errors if you query an empty collection
    if _collection.count() == 0:
        return []

    # n_results can't exceed the collection size
    n = min(n_results, _collection.count())

    results = _collection.query(
        query_texts=[query],
        n_results=n
    )

    # Unpack the nested lists ChromaDB returns
    # results["documents"] is [[doc1, doc2, ...]] (outer list = one per query)
    hits = []
    for i, doc in enumerate(results["documents"][0]):
        hits.append({
            "content": doc,
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i]
        })

    return hits


def count_failures() -> int:
    """How many past failures are in the knowledge base."""
    return _collection.count()
