"""
Customer Tools - LangChain tools for customer operations.

These tools interact with the demo data store and require appropriate
scopes from the MCP token to execute.
"""

from typing import Optional
from langchain_core.tools import tool
from data.demo_store import demo_store
import logging

logger = logging.getLogger(__name__)


@tool
def get_customer(customer_name: str) -> str:
    """
    Get information about a specific customer.
    Use this to look up customer details, tier, and spending history.

    Args:
        customer_name: Name or partial name of the customer

    Returns:
        Customer details including tier, contact, and total spent
    """
    customer = demo_store.get_customer_by_name(customer_name)
    if not customer:
        return f"Customer not found: {customer_name}"

    tier_emoji = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}.get(customer['tier'], "")

    return (
        f"**{customer['name']}** {tier_emoji}\n"
        f"- Customer ID: {customer['id']}\n"
        f"- Tier: {customer['tier']}\n"
        f"- Contact: {customer['contact']}\n"
        f"- Email: {customer['email']}\n"
        f"- Location: {customer['location']}\n"
        f"- Total Spent: ${customer['total_spent']:,}"
    )


@tool
def search_customers(query: str) -> str:
    """
    Search for customers by name, contact, or location.
    Use this to find customers matching a search term.

    Args:
        query: Search term (name, contact person, or city)

    Returns:
        List of matching customers
    """
    results = demo_store.search_customers(query)
    if not results:
        return f"No customers found matching: {query}"

    tier_emoji = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}

    lines = [f"**Found {len(results)} customers matching '{query}':**\n"]
    for customer in results:
        emoji = tier_emoji.get(customer['tier'], "")
        lines.append(
            f"- {emoji} **{customer['name']}** ({customer['tier']})\n"
            f"  Contact: {customer['contact']} | Location: {customer['location']} | "
            f"Spent: ${customer['total_spent']:,}"
        )

    return "\n".join(lines)


@tool
def get_customers_by_tier(tier: str) -> str:
    """
    Get all customers in a specific tier.
    Use this to list Platinum, Gold, Silver, or Bronze customers.

    Args:
        tier: Customer tier (Platinum, Gold, Silver, or Bronze)

    Returns:
        List of customers in that tier
    """
    customers = demo_store.get_customers_by_tier(tier)
    if not customers:
        return f"No customers found in tier: {tier}"

    tier_emoji = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}.get(tier, "")

    # Sort by total spent descending
    customers_sorted = sorted(customers, key=lambda x: x['total_spent'], reverse=True)

    lines = [f"**{tier_emoji} {tier} Tier Customers ({len(customers)}):**\n"]
    total_spent = 0

    for customer in customers_sorted:
        total_spent += customer['total_spent']
        lines.append(
            f"- **{customer['name']}** - ${customer['total_spent']:,}\n"
            f"  {customer['contact']} | {customer['location']}"
        )

    lines.append(f"\n**Total {tier} Revenue: ${total_spent:,}**")

    return "\n".join(lines)


@tool
def get_customer_summary() -> str:
    """
    Get a summary of all customers by tier.
    Use this for an overview of customer distribution and revenue.

    Returns:
        Summary statistics of customers by tier
    """
    summary = demo_store.get_customer_summary()

    tier_emoji = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
    tier_order = ["Platinum", "Gold", "Silver", "Bronze"]

    lines = [
        "**ProGear Basketball - Customer Summary**\n",
        f"- Total Customers: {summary['total_customers']}",
        f"- Total Revenue: ${summary['total_revenue']:,}",
        "\n**By Tier:**"
    ]

    for tier in tier_order:
        if tier in summary['by_tier']:
            data = summary['by_tier'][tier]
            emoji = tier_emoji.get(tier, "")
            lines.append(
                f"- {emoji} {tier}: {data['count']} customers, "
                f"${data['total_spent']:,} total"
            )

    return "\n".join(lines)


# List of all customer tools for export
CUSTOMER_TOOLS = [
    get_customer,
    search_customers,
    get_customers_by_tier,
    get_customer_summary
]
