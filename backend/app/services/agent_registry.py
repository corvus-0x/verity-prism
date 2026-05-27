"""
Tool schema registry — maps vertical names to their tool lists.
Core tools are always available. Add vertical-specific tools by extending
VERTICAL_TOOLS[<vertical>] with tool schemas from agent_tools_<vertical>.py.
"""


def build_tool_schemas() -> list[dict]:
    """Return the JSON schemas for all 6 core tools.
    These descriptions are a design artifact — Claude uses them to decide which tool to call.
    """
    return [
        {
            "name": "search_documents",
            "description": (
                "Search workspace documents by keyword and optionally filter by document type. "
                "Returns up to 10 matching documents with filename, type, and top matched fields."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword search string",
                    },
                    "doc_type": {
                        "type": "string",
                        "description": "Optional document type filter (DEED, 990, UCC, SOS-FILING, etc.)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_entity",
            "description": (
                "Look up a specific entity (person, LLC, organization) by name. "
                "Returns the entity record and all associated data fields."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Entity name to look up (exact or partial match)",
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "query_extractions",
            "description": (
                "Find documents where a specific extracted field matches a value. "
                "Use for precise field-level queries like 'all deeds where grantor contains Smith' "
                "or 'documents where consideration_amount is greater than 500000'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "The extracted field name to filter on",
                    },
                    "operator": {
                        "type": "string",
                        "enum": ["eq", "contains", "gt", "lt"],
                        "description": "Comparison operator",
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to compare against (always a string, even for numeric comparisons)",
                    },
                },
                "required": ["field_name", "operator", "value"],
            },
        },
        {
            "name": "get_transactions",
            "description": (
                "Filter workspace transactions by amount range and/or transaction type. "
                "Returns amount paid, appraised value, overpay percentage, date, and instrument number."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "min_amount": {
                        "type": "number",
                        "description": "Minimum transaction amount",
                    },
                    "max_amount": {
                        "type": "number",
                        "description": "Maximum transaction amount",
                    },
                    "transaction_type": {
                        "type": "string",
                        "description": "Filter by transaction type",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "get_findings",
            "description": (
                "List all findings in the workspace with title, severity, and status. "
                "Check this before making new observations to avoid duplicating what is already recorded."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "get_leads",
            "description": (
                "List investigation leads filtered by status. "
                "Check this before suggesting new leads to avoid duplicating what is already being tracked."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "all"],
                        "description": "Filter by lead status. Defaults to pending.",
                    },
                },
                "required": [],
            },
        },
    ]


VERTICAL_TOOLS: dict[str, list[dict]] = {
    "fraud": build_tool_schemas(),
    "insurance": build_tool_schemas(),
    "general": build_tool_schemas(),
}


def get_tools_for_vertical(vertical: str) -> list[dict]:
    """Return tool schemas for the given vertical.
    Falls back to core tools if vertical is not registered.
    To add vertical-specific tools: extend VERTICAL_TOOLS[vertical] with additional schemas.
    """
    return VERTICAL_TOOLS.get(vertical, build_tool_schemas())
