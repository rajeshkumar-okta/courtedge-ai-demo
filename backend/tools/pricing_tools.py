"""
Pricing Tools - LangChain tools for pricing and discount operations.

These tools interact with the demo data store and require appropriate
scopes from the MCP token to execute.
"""

from typing import Optional
from langchain_core.tools import tool
from data.demo_store import demo_store
import logging

logger = logging.getLogger(__name__)


@tool
def get_price(product_name: str) -> str:
    """
    Get pricing information for a specific product.
    Use this to check price, cost, and margin for a product.

    Args:
        product_name: Name or partial name of the product

    Returns:
        Product pricing details including price, cost, and margin
    """
    item = demo_store.get_inventory_by_name(product_name)
    if not item:
        return f"Product not found: {product_name}"

    sku = item['sku']
    pricing = demo_store.get_price_by_sku(sku)

    if not pricing:
        return f"Pricing not found for: {product_name}"

    return (
        f"**{pricing['name']}** (SKU: {pricing['sku']})\n"
        f"- Price: ${pricing['price']:.2f}\n"
        f"- Cost: ${pricing['cost']:.2f}\n"
        f"- Margin: {pricing['margin']}%"
    )


@tool
def get_pricing_by_category(category: str) -> str:
    """
    Get pricing for all products in a category.
    Use this to see prices and margins for a product category.

    Args:
        category: Category name (e.g., 'Basketballs', 'Hoops & Backboards', 'Uniforms')

    Returns:
        List of products with pricing in that category
    """
    pricing_list = demo_store.get_pricing_by_category(category)

    if not pricing_list:
        return f"No products found in category: {category}"

    lines = [f"**Pricing for {category}:**\n"]

    # Calculate average margin
    total_margin = sum(p['margin'] for p in pricing_list)
    avg_margin = total_margin / len(pricing_list)

    for item in pricing_list:
        lines.append(
            f"- {item['name']}: ${item['price']:.2f} "
            f"(cost: ${item['cost']:.2f}, margin: {item['margin']}%)"
        )

    lines.append(f"\n**Average margin for {category}: {avg_margin:.1f}%**")

    return "\n".join(lines)


@tool
def update_price(product_name: str, new_price: float) -> str:
    """
    Update the price of a product. REQUIRES pricing:margin or pricing:discount scope.
    Use this to change product prices.

    Args:
        product_name: Name of the product to update
        new_price: New price in dollars

    Returns:
        Confirmation of the price update
    """
    item = demo_store.get_inventory_by_name(product_name)
    if not item:
        return f"Product not found: {product_name}"

    sku = item['sku']
    result = demo_store.update_price(sku, new_price)

    if "error" in result:
        return f"Error: {result['error']}"

    price_change = result['new_price'] - result['old_price']
    change_text = f"+${price_change:.2f}" if price_change > 0 else f"-${abs(price_change):.2f}"

    return (
        f"**Price Updated Successfully**\n\n"
        f"**{result['name']}** (SKU: {result['sku']})\n"
        f"- Previous Price: ${result['old_price']:.2f}\n"
        f"- New Price: ${result['new_price']:.2f} ({change_text})\n"
        f"- New Margin: {result['margin']}%"
    )


@tool
def calculate_discount(customer_name: str, quantity: int) -> str:
    """
    Calculate the total discount for a customer and order quantity.
    Use this to determine what discount a customer gets for an order.

    Args:
        customer_name: Name of the customer
        quantity: Number of units being ordered

    Returns:
        Breakdown of tier and volume discounts
    """
    customer = demo_store.get_customer_by_name(customer_name)
    if not customer:
        return f"Customer not found: {customer_name}"

    tier = customer.get('tier', 'Bronze')
    discount_info = demo_store.calculate_total_discount(tier, quantity)

    return (
        f"**Discount Calculation for {customer['name']}**\n\n"
        f"- Customer Tier: {discount_info['tier']}\n"
        f"- Tier Discount: {discount_info['tier_discount']}%\n"
        f"- Order Quantity: {discount_info['quantity']:,} units\n"
        f"- Volume Discount: {discount_info['volume_discount']}%\n"
        f"- **Total Discount: {discount_info['total_discount']}%**"
    )


@tool
def get_pricing_summary() -> str:
    """
    Get a summary of pricing and margins across all categories.
    Use this for an overview of pricing structure.

    Returns:
        Summary of pricing by category with average margins
    """
    inventory = demo_store.get_all_inventory()
    pricing = demo_store.get_all_pricing()

    categories = {}
    for sku, item in inventory.items():
        category = item.get('category', 'Other')
        if sku in pricing:
            if category not in categories:
                categories[category] = {'products': [], 'margins': []}
            categories[category]['products'].append(item['name'])
            categories[category]['margins'].append(pricing[sku]['margin'])

    lines = ["**ProGear Basketball - Pricing Summary**\n"]

    all_margins = []
    for category, data in categories.items():
        avg_margin = sum(data['margins']) / len(data['margins'])
        all_margins.extend(data['margins'])
        lines.append(
            f"- {category}: {len(data['products'])} products, "
            f"avg margin {avg_margin:.1f}%"
        )

    overall_avg = sum(all_margins) / len(all_margins) if all_margins else 0
    lines.append(f"\n**Overall Average Margin: {overall_avg:.1f}%**")

    # Add discount structure
    discounts = demo_store.get_discount_structure()
    lines.append("\n**Discount Structure:**")
    lines.append("Tier Discounts: " + ", ".join(
        f"{tier}: {disc}%" for tier, disc in discounts.get('tier_discounts', {}).items()
    ))
    lines.append("Volume Discounts: " + ", ".join(
        f"{qty}+ units: {disc}%" for qty, disc in sorted(
            discounts.get('volume_discounts', {}).items(),
            key=lambda x: int(x[0])
        )
    ))

    return "\n".join(lines)


# List of all pricing tools for export
PRICING_TOOLS = [
    get_price,
    get_pricing_by_category,
    update_price,
    calculate_discount,
    get_pricing_summary
]
