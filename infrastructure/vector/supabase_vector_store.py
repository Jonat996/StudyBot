from typing import Optional
from core.interfaces.vector_store import VectorStore
from core.interfaces.llm_provider import LLMProvider
from infrastructure.database.supabase_client import get_supabase_client

TABLE = "resources"


class SupabaseVectorStore(VectorStore):
    def __init__(self, settings, llm: LLMProvider):
        self._db = get_supabase_client(settings.supabase_url, settings.supabase_key)
        self._llm = llm

    def upsert(self, id: str, text: str, metadata: dict) -> bool:
        embedding = self._llm.generate_embedding(text)
        payload = {
            "id": id,
            "content": text,
            "embedding": embedding,
            **metadata,
        }
        self._db.table(TABLE).upsert(payload).execute()
        return True

    def search(self, query: str, top_k: int = 3, filters: Optional[dict] = None) -> list[dict]:
        embedding = self._llm.generate_embedding(query)
        result = self._db.rpc(
            "match_resources",
            {
                "query_embedding": embedding,
                "match_count": top_k,
                "filter": filters or {},
            },
        ).execute()
        return result.data or []
