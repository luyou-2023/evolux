from agent.memory_manager import MemoryManager


def test_memory_manager_reads_user_and_memory(evolux_home):
    mem_dir = evolux_home / "memories"
    mem_dir.mkdir(parents=True)
    (mem_dir / "USER.md").write_text("Name: Luke", encoding="utf-8")
    (mem_dir / "MEMORY.md").write_text("Prefers Python.", encoding="utf-8")

    snapshot = MemoryManager(home=evolux_home).read_snapshot()
    assert "Luke" in snapshot
    assert "Python" in snapshot
