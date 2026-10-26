"""Drive the public D14 conversation steps in integration tests."""

from __future__ import annotations

from xeon.application.container import AppContainer
from xeon.application.reply import Reply


async def add_product(
    container: AppContainer, key: str, query: str, sku: str, quantity: int
) -> Reply:
    agent = container.agent
    state = agent._funnel.state(key)
    if state.step == "inicio":
        await agent.respond_reply("start:products", conversation_key=key)
    elif state.step == "mas":
        await agent.respond_reply("more:add", conversation_key=key)
    search = await agent.respond_reply(query, conversation_key=key)
    assert any(option.id == f"product:{sku}" for option in search.options)
    await agent.respond_reply(f"product:{sku}", conversation_key=key)
    if quantity in {10, 20}:
        return await agent.respond_reply(f"quantity:{quantity}", conversation_key=key)
    await agent.respond_reply("quantity:other", conversation_key=key)
    return await agent.respond_reply(str(quantity), conversation_key=key)


async def select_pickup(container: AppContainer, key: str, branch_id: str) -> Reply:
    agent = container.agent
    await agent.respond_reply("more:view", conversation_key=key)
    await agent.respond_reply("delivery:pickup", conversation_key=key)
    return await agent.respond_reply(f"branch:{branch_id}", conversation_key=key)
