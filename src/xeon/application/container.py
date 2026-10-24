from __future__ import annotations

from dataclasses import dataclass

from xeon.adapters.catalog.memory import InMemoryProductCatalog
from xeon.adapters.channels.evolution import EvolutionAPIChannelAdapter
from xeon.adapters.channels.kapso import KapsoChannelAdapter
from xeon.adapters.conversation.memory import InMemoryConversationMemory
from xeon.adapters.inventory.memory import InMemoryBranchInventory
from xeon.adapters.llm import build_llm
from xeon.adapters.persistence.memory import InMemoryQuoteDraftRepository
from xeon.agent.hermes import HermesToolbelt
from xeon.agent.service import AgentService
from xeon.application.ports.catalog import ProductCatalog
from xeon.application.ports.channels import WhatsAppChannelPort
from xeon.application.ports.conversation_memory import ConversationMemory
from xeon.application.ports.inventory import BranchInventory
from xeon.application.ports.llm import LLMPort
from xeon.application.ports.quotes import QuoteDraftRepository
from xeon.application.quote_draft import CreateQuoteDraft, GetQuoteDraft
from xeon.application.stock import GetStockByBranches
from xeon.config import Settings


@dataclass(frozen=True, slots=True)
class AppContainer:
    settings: Settings
    catalog: ProductCatalog
    inventory: BranchInventory
    quotes: QuoteDraftRepository
    llm: LLMPort
    conversation_memory: ConversationMemory
    hermes_tools: HermesToolbelt
    agent: AgentService
    create_quote_draft: CreateQuoteDraft
    get_quote_draft: GetQuoteDraft
    get_stock_by_branches: GetStockByBranches
    whatsapp_channel: WhatsAppChannelPort | None = None

    async def aclose(self) -> None:
        await self.agent.aclose()
        if self.whatsapp_channel is not None:
            await self.whatsapp_channel.aclose()


def build_container(
    settings: Settings,
    *,
    catalog: ProductCatalog | None = None,
    inventory: BranchInventory | None = None,
    quotes: QuoteDraftRepository | None = None,
    llm: LLMPort | None = None,
    conversation_memory: ConversationMemory | None = None,
    whatsapp_channel: WhatsAppChannelPort | None = None,
) -> AppContainer:
    resolved_catalog = catalog or InMemoryProductCatalog()
    resolved_inventory = inventory or InMemoryBranchInventory()
    resolved_quotes = quotes or InMemoryQuoteDraftRepository()
    resolved_llm = llm or build_llm(settings)
    resolved_memory = conversation_memory or InMemoryConversationMemory(
        max_turns=settings.conversation_max_turns,
        max_conversations=settings.conversation_max_conversations,
    )
    create_quote_draft = CreateQuoteDraft(resolved_catalog, resolved_quotes)
    get_quote_draft = GetQuoteDraft(resolved_quotes)
    get_stock_by_branches = GetStockByBranches(resolved_inventory)
    hermes_tools = HermesToolbelt(
        catalog=resolved_catalog,
        create_quote_draft=create_quote_draft,
        get_stock_by_branches=get_stock_by_branches,
    )
    agent = AgentService(resolved_llm, tools=hermes_tools, memory=resolved_memory)

    resolved_whatsapp = whatsapp_channel
    if resolved_whatsapp is None and settings.whatsapp_send_enabled:
        if settings.whatsapp_channel == "kapso":
            resolved_whatsapp = KapsoChannelAdapter(
                base_url=settings.kapso_api_base_url,
                phone_number_id=settings.kapso_phone_number_id,
                graph_version=settings.meta_graph_version,
                api_key=settings.require_kapso_api_key().get_secret_value(),
            )
        else:
            resolved_whatsapp = EvolutionAPIChannelAdapter(
                base_url=settings.evolution_api_url,
                instance=settings.evolution_instance,
                api_key=settings.require_evolution_api_key().get_secret_value(),
            )

    return AppContainer(
        settings=settings,
        catalog=resolved_catalog,
        inventory=resolved_inventory,
        quotes=resolved_quotes,
        llm=resolved_llm,
        conversation_memory=resolved_memory,
        hermes_tools=hermes_tools,
        agent=agent,
        create_quote_draft=create_quote_draft,
        get_quote_draft=get_quote_draft,
        get_stock_by_branches=get_stock_by_branches,
        whatsapp_channel=resolved_whatsapp,
    )
