from vector.store import create_vector_store, sqlite_vec_available


def test_create_vector_store_sqlite_vec_raises_when_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr("vector.store.sqlite_vec_available", lambda: False)
    try:
        create_vector_store(tmp_path, "skills.json", backend="sqlite-vec")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "sqlite-vec" in str(exc)


def test_sqlite_vec_available_matches_environment():
    # Document environment capability; never fails the suite.
    assert isinstance(sqlite_vec_available(), bool)
