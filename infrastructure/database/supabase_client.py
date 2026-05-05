from supabase import create_client, Client

_client: Client = None


def get_supabase_client(url: str, key: str) -> Client:
    global _client
    if _client is None:
        _client = create_client(url, key)
    return _client
