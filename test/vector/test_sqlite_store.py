from concurrent.futures import ThreadPoolExecutor

from vector.embedder import HashEmbedder
from vector.store import JsonVectorStore, SqliteVectorStore, create_vector_store


def test_create_vector_store_sqlite_backend(tmp_path):
    store = create_vector_store(tmp_path, "skills.json", backend="sqlite")
    assert isinstance(store, SqliteVectorStore)


def test_sqlite_vector_store_search_returns_best_match(tmp_path):
    store = SqliteVectorStore(tmp_path / "vector" / "skills.db")
    embedder = HashEmbedder()
    store.upsert("a", embedder.embed("python code"), {"tag": "code"})
    store.upsert("b", embedder.embed("feishu document"), {"tag": "feishu"})

    hits = store.search(embedder.embed("python code"), top_k=1)
    assert hits[0][0] == "a"
    assert hits[0][1] > 0.99


def test_sqlite_vector_store_metadata_filter(tmp_path):
    store = SqliteVectorStore(tmp_path / "vector" / "subagents.db")
    embedder = HashEmbedder()
    store.upsert("x", embedder.embed("git"), {"assistant_id": "work"})
    store.upsert("y", embedder.embed("git"), {"assistant_id": "life"})

    hits = store.search(
        embedder.embed("git"),
        top_k=5,
        metadata_filter={"assistant_id": "work"},
    )
    assert len(hits) == 1
    assert hits[0][0] == "x"


def test_sqlite_vector_store_thread_safe_upsert(tmp_path):
    store = SqliteVectorStore(tmp_path / "vector" / "skills.db")
    embedder = HashEmbedder()

    def _upsert(i: int) -> None:
        store.upsert(f"skill-{i}", embedder.embed(f"topic {i}"), {"i": i})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_upsert, range(20)))

    hits = store.search(embedder.embed("topic 7"), top_k=1)
    assert hits[0][0] == "skill-7"
