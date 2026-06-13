import json

from agent.context_compressor import CompressionConfig, compress_messages
from agent.memory_manager import MemoryManager
from agent.memory_sedimentation import extract_memory_entries_heuristic, sediment_global_memory
from agent.session_compression import persist_session_compression
from evolux_state import SessionDB
from tools.session_search_tool import session_search


def _make_turns(count: int) -> list[dict]:
    messages: list[dict] = []
    for idx in range(count):
        messages.append({"role": "user", "content": f"question {idx} about python asyncio"})
        messages.append({"role": "assistant", "content": f"answer {idx} about asyncio patterns"})
    return messages


def test_session_db_fts_search(evolux_home):
    db = SessionDB(home=evolux_home)
    session_id = db.create_session("orchestrator:default:cli:dm:fts", "default", "cli")
    db.append_message(session_id, "user", "help me debug asyncio gather")
    db.append_message(session_id, "assistant", "use asyncio.gather for parallel tasks")

    hits = db.search_messages_fts("asyncio gather", assistant_id="default", limit=5)
    assert hits
    assert hits[0]["session_key"] == "orchestrator:default:cli:dm:fts"
    assert "asyncio" in hits[0]["content"]
    db.close()


def test_compression_chain_rotate_and_load(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:chain"
    session_id = db.create_session(key, "default", "cli")
    db.replace_messages(session_id, _make_turns(12))

    result = compress_messages(
        [{"role": m["role"], "content": m["content"]} for m in db.get_messages(session_id)],
        CompressionConfig(keep_recent_turns=3),
    )
    assert result.compressed
    child_id = persist_session_compression(db, session_key=key, result=result)
    assert child_id is not None
    assert child_id != session_id
    assert db.get_session_id_by_key(key) == child_id

    log = db.get_compression_log_for_child(child_id)
    assert log is not None
    assert log["parent_session_id"] == session_id
    assert log["summary"]

    loaded = db.load_history(key)
    assert any("历史摘要" in m["content"] for m in loaded if m["role"] == "system")
    assert loaded[-1]["role"] in {"user", "assistant"}
    db.close()


def test_session_search_uses_fts(evolux_home):
    db = SessionDB(home=evolux_home)
    session_id = db.create_session("orchestrator:default:cli:dm:search", "default", "cli")
    db.append_message(session_id, "user", "unique-keyword-xyzzy plugh")
    db.append_message(session_id, "assistant", "acknowledged")
    db.close()

    payload = json.loads(session_search(query="xyzzy plugh", assistant_id="default", limit=5))
    assert payload["success"] is True
    assert payload["count"] >= 1
    assert payload["results"][0]["match_source"] == "fts5"


def test_global_memory_sediment_after_turn(evolux_home):
    memory = MemoryManager(home=evolux_home)
    written = sediment_global_memory(
        memory,
        user_message="please refactor the auth module with tests",
        final_reply="Refactored auth module and added pytest coverage for login flows.",
        dispatches=[
            {
                "agent_id": "code-expert",
                "skills": ["git"],
                "summary": "done",
                "exhausted": False,
            }
        ],
    )
    assert written
    snapshot = memory.read_snapshot()
    assert "code-expert" in snapshot
    assert "auth module" in snapshot.lower() or "协调记录" in snapshot


def test_memory_heuristic_skips_short_turns():
    entries = extract_memory_entries_heuristic("hi", "ok", [])
    assert entries == []
