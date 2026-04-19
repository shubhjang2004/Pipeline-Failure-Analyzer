from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os

load_dotenv()

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

model = SentenceTransformer("all-MiniLM-L6-v2")
COLLECTION = "pipeline_failures"
VECTOR_SIZE = 384  

# ── Create collection if it doesn't exist ──────────────────────
def ensure_collection():
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )
        print(f"Created collection: {COLLECTION}")
    else:
        print(f"Collection already exists: {COLLECTION}")

ensure_collection()  # runs automatically when rag.py is imported

def get_embedding(text: str) -> list[float]:
    return model.encode(text).tolist()

def search_failures(query: str, n_results: int = 3) -> list[dict]:
    vector = get_embedding(query)
    results = client.query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=n_results,
        with_payload=True
    ).points

    return [
        {
            "content": r.payload.get("text", ""),
            "metadata": r.payload,
            "distance": 1 - r.score
        }
        for r in results
    ]
def add_failure(id: str, failure_text: str, metadata: dict):
    vector = get_embedding(failure_text)
    client.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(
            id=id,
            vector=vector,
            payload={**metadata, "text": failure_text}
        )]
    )

def count_failures() -> int:
    return client.count(collection_name=COLLECTION).count