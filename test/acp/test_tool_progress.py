import pytest

pytest.importorskip("acp")

from acp_adapter.progress import AcpToolProgressHook


class FakeConn:
    def __init__(self):
        self.updates = []

    async def session_update(self, session_id, update):
        self.updates.append((session_id, update))


@pytest.mark.asyncio
async def test_acp_tool_progress_hook_emits_start_and_end():
    conn = FakeConn()
    loop = __import__("asyncio").get_running_loop()
    hook = AcpToolProgressHook(loop=loop, conn=conn, session_id="sess-1")
    hook.on_tool_start("tc-1", "terminal", {"command": "echo hi"})
    hook.on_tool_end("tc-1", "terminal", {"command": "echo hi"}, '{"success": true}')
    await __import__("asyncio").sleep(0.05)
    assert len(conn.updates) == 2
    assert conn.updates[0][0] == "sess-1"
    assert conn.updates[0][1].tool_call_id == "tc-1"
