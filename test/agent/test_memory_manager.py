from agent.memory_manager import MemoryManager


def test_memory_manager_reads_user_and_memory(evolux_home):
    mem_dir = evolux_home / "memories"
    mem_dir.mkdir(parents=True)
    (mem_dir / "USER.md").write_text("Name: Luke", encoding="utf-8")
    (mem_dir / "MEMORY.md").write_text("Prefers Python.", encoding="utf-8")

    manager = MemoryManager(home=evolux_home)
    snapshot = manager.read_snapshot()
    assert "Luke" in snapshot
    assert "Python" in snapshot


def test_memory_manager_agent_and_solution_sediment(evolux_home):
    manager = MemoryManager(home=evolux_home)
    manager.append_agent_memory("code-expert", "First lesson.")
    manager.append_agent_memory("code-expert", "Second lesson.")
    agent_mem = manager.read_agent_memory("code-expert")
    assert "First lesson." in agent_mem
    assert "Second lesson." in agent_mem

    manager.append_solution("Solution A")
    manager.append_solution("Solution B")
    solutions = manager.read_solutions_snapshot()
    assert "Solution A" in solutions
    assert "Solution B" in solutions
