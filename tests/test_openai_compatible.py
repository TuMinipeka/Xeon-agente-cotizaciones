import asyncio

import httpx

from xeon.adapters.llm.openai_compatible import OpenAICompatibleLLM
from xeon.application.ports.llm import ChatMessage


def test_adapter_uses_expected_chat_completions_contract() -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url) == "https://provider.example/v1/chat/completions"
            assert request.headers["Authorization"] == "Bearer test-secret"
            payload = __import__("json").loads(request.content)
            assert payload["model"] == "grok-4.6"
            assert payload["messages"][-1] == {"role": "user", "content": "hola"}
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "respuesta"}}]},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = OpenAICompatibleLLM(
            base_url="https://provider.example/v1/",
            api_key="test-secret",
            model="grok-4.6",
            max_output_tokens=256,
            timeout_seconds=5,
            client=client,
        )
        result = await adapter.complete((ChatMessage(role="user", content="hola"),))
        await client.aclose()

        assert result.text == "respuesta"
        assert result.provider == "grok"

    asyncio.run(run())
