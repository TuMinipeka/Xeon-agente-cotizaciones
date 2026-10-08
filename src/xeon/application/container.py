from __future__ import annotations

from dataclasses import dataclass

from xeon.adapters.catalog.memory import InMemoryProductCatalog
from xeon.adapters.llm import build_llm
from xeon.adapters.persistence.memory import InMemoryQuoteDraftRepository
from xeon.agent.service import AgentService
from xeon.application.ports.catalog import ProductCatalog
from xeon.application.ports.llm import LLMPort
from xeon.application.ports.quotes import QuoteDraftRepository
from xeon.application.quote_draft import CreateQuoteDraft, GetQuoteDraft
from xeon.config import Settings


@dataclass(frozen=True, slots=True)
class AppContainer:
    settings: Settings
    catalog: ProductCatalog
    quotes: QuoteDraftRepository
    llm: LLMPort
    agent: AgentService
    create_quote_draft: CreateQuoteDraft
    get_quote_draft: GetQuoteDraft

    async def aclose(self) -> None:
        await self.agent.aclose()


def build_container(
    settings: Settings,
    *,
    catalog: ProductCatalog | None = None,
    quotes: QuoteDraftRepository | None = None,
    llm: LLMPort | None = None,
) -> AppContainer:
    resolved_catalog = catalog or InMemoryProductCatalog()
    resolved_quotes = quotes or InMemoryQuoteDraftRepository()
    resolved_llm = llm or build_llm(settings)
    agent = AgentService(resolved_llm)
    return AppContainer(
        settings=settings,
        catalog=resolved_catalog,
        quotes=resolved_quotes,
        llm=resolved_llm,
        agent=agent,
        create_quote_draft=CreateQuoteDraft(resolved_catalog, resolved_quotes),
        get_quote_draft=GetQuoteDraft(resolved_quotes),
    )
