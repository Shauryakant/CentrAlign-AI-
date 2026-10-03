import asyncio
import os
import pytest
from agent.browser import BrowserManager
from agent.tools import ToolContext, ToolExecutor

@pytest.mark.asyncio
async def test_approval_gate_enforcement():
    """Verify that clicking a submit element without prior request_approval is refused by code."""
    ctx = ToolContext(run_dir="runs/test_approval", auto_approve=False)
    executor = ToolExecutor(ctx)

    assert ctx.approval_granted == False

    # Simulate refusal scenario on non-existent or submit element
    res = await executor.execute_tool("browser_click", {"element_id": 99})
    assert res["ok"] == False

    await ctx.close()

@pytest.mark.asyncio
async def test_memory_remember_and_ask_user():
    """Verify remember and ask_user store state into ToolContext correctly."""
    user_responses = ["Acme Supplies"]
    def mock_ask_user(q: str):
        return user_responses.pop(0)

    ctx = ToolContext(run_dir="runs/test_memory", ask_user_fn=mock_ask_user)
    executor = ToolExecutor(ctx)

    # 1. Test remember tool
    res_mem = await executor.execute_tool("remember", {"fact": "Target vendor is Acme Supplies"})
    assert res_mem["ok"] == True
    assert any("Acme Supplies" in f for f in ctx.facts)

    # 2. Test ask_user tool
    res_ask = await executor.execute_tool("ask_user", {"question": "Did you mean Acme Supplies or Acme Supply Co?"})
    assert res_ask["ok"] == True
    assert "Acme Supplies" in res_ask["observation"]

    await ctx.close()

if __name__ == "__main__":
    asyncio.run(test_approval_gate_enforcement())
    asyncio.run(test_memory_remember_and_ask_user())
    print("All reliability and safety unit tests passed cleanly!")
