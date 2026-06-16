"""Local Shopify Admin MCP server.

Exposes the Shopify Admin API as MCP tools over HTTP, matching the tool names
the agent company expects (mcp__shopify__<tool>). Run it locally and point
SHOPIFY_MCP_URL at it. Your Admin API token never leaves this process.

Tools served (read-only by default; writes require write_* scopes on the token):
    get-shop-info
    search_products
    get-product
    list-orders
    get-order
    run-analytics-query        (ShopifyQL)
    get-inventory-levels
    update-product             (write_products)

Env:
    SHOPIFY_STORE_DOMAIN   e.g. cvqpju-j0.myshopify.com  (or your .myshopify.com)
    SHOPIFY_ADMIN_TOKEN    the Admin API access token (shpat_...)
    SHOPIFY_API_VERSION    optional, defaults to 2025-01
    PORT                   optional, defaults to 8000
"""

from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

STORE = os.environ.get("SHOPIFY_STORE_DOMAIN", "").replace("https://", "").strip("/")
TOKEN = os.environ.get("SHOPIFY_ADMIN_TOKEN", "")
API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2025-01")
PORT = int(os.environ.get("PORT", "8000"))

if not STORE or not TOKEN:
    raise SystemExit(
        "Set SHOPIFY_STORE_DOMAIN and SHOPIFY_ADMIN_TOKEN before starting the server."
    )

GRAPHQL_URL = f"https://{STORE}/admin/api/{API_VERSION}/graphql.json"
HEADERS = {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}

mcp = FastMCP("shopify")


def _gql(query: str, variables: dict | None = None) -> dict:
    """Run a GraphQL request against the Admin API and return data (or raise)."""
    resp = httpx.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"Shopify GraphQL error: {body['errors']}")
    return body["data"]


@mcp.tool(name="get-shop-info")
def get_shop_info() -> dict:
    """Basic store info: name, domain, currency, plan."""
    data = _gql(
        "{ shop { name myshopifyDomain primaryDomain { host } "
        "currencyCode plan { displayName } } }"
    )
    return data["shop"]


@mcp.tool(name="search_products")
def search_products(search_query: str = "", first: int = 10) -> dict:
    """Search/browse products. `search_query` uses Shopify search syntax."""
    q = """
    query($q: String, $first: Int!) {
      products(first: $first, query: $q) {
        edges { node {
          id title handle status productType vendor totalInventory
          priceRangeV2 { minVariantPrice { amount currencyCode } }
        } }
        pageInfo { hasNextPage endCursor }
      }
    }"""
    return _gql(q, {"q": search_query or None, "first": min(first, 50)})


@mcp.tool(name="get-product")
def get_product(product_id: str) -> dict:
    """Fetch one product by GID (gid://shopify/Product/...)."""
    q = """
    query($id: ID!) {
      product(id: $id) {
        id title handle status descriptionHtml productType vendor totalInventory
        variants(first: 50) { edges { node { id title sku price inventoryQuantity } } }
      }
    }"""
    return _gql(q, {"id": product_id})


@mcp.tool(name="list-orders")
def list_orders(first: int = 10, query: str = "") -> dict:
    """Recent orders with status and totals."""
    q = """
    query($first: Int!, $q: String) {
      orders(first: $first, query: $q, sortKey: CREATED_AT, reverse: true) {
        edges { node {
          id name createdAt displayFinancialStatus displayFulfillmentStatus
          totalPriceSet { shopMoney { amount currencyCode } }
          customer { displayName }
        } }
      }
    }"""
    return _gql(q, {"first": min(first, 50), "q": query or None})


@mcp.tool(name="get-order")
def get_order(order_id: str) -> dict:
    """Fetch one order by GID, including fulfillment/tracking."""
    q = """
    query($id: ID!) {
      order(id: $id) {
        id name createdAt displayFinancialStatus displayFulfillmentStatus
        totalPriceSet { shopMoney { amount currencyCode } }
        fulfillments { status trackingInfo { number url company } }
        lineItems(first: 50) { edges { node { title quantity } } }
      }
    }"""
    return _gql(q, {"id": order_id})


@mcp.tool(name="get-inventory-levels")
def get_inventory_levels(first: int = 20) -> dict:
    """Inventory quantities across products/variants."""
    q = """
    query($first: Int!) {
      products(first: $first) {
        edges { node {
          title totalInventory
          variants(first: 10) { edges { node { sku inventoryQuantity } } }
        } }
      }
    }"""
    return _gql(q, {"first": min(first, 50)})


@mcp.tool(name="run-analytics-query")
def run_analytics_query(query: str) -> dict:
    """Run a ShopifyQL analytics query (FROM ... SHOW ...)."""
    q = """
    query($q: String!) {
      shopifyqlQuery(query: $q) {
        __typename
        ... on TableResponse {
          tableData {
            columns { name dataType }
            rowData
          }
        }
        parseErrors { code message }
      }
    }"""
    return _gql(q, {"q": query})


@mcp.tool(name="update-product")
def update_product(product_id: str, title: str = "", description_html: str = "") -> dict:
    """Update a product's title/description. Requires write_products scope.
    Mutation tool — the agent company only calls this when autonomy is 'auto'."""
    fields: dict = {"id": product_id}
    if title:
        fields["title"] = title
    if description_html:
        fields["descriptionHtml"] = description_html
    q = """
    mutation($input: ProductInput!) {
      productUpdate(input: $input) {
        product { id title }
        userErrors { field message }
      }
    }"""
    return _gql(q, {"input": fields})


@mcp.tool(name="create-product")
def create_product(title: str, description_html: str = "", status: str = "DRAFT") -> dict:
    """Create a product (defaults to DRAFT). Requires write_products scope.
    Mutation tool — only callable when the agent's autonomy is 'auto'."""
    q = """
    mutation($input: ProductInput!) {
      productCreate(input: $input) {
        product { id title status }
        userErrors { field message }
      }
    }"""
    return _gql(q, {"input": {"title": title, "descriptionHtml": description_html, "status": status}})


if __name__ == "__main__":
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = PORT
    print(f"Shopify MCP server for {STORE} on http://localhost:{PORT} (api {API_VERSION})")
    mcp.run(transport="streamable-http")
