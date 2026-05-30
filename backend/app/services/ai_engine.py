"""
AI Chat Engine — Claude with native tool use.

chat() runs an agentic loop: Claude calls tools to query workspace data,
results are injected back as tool_result blocks, and the loop repeats until
end_turn or MAX_TOOL_ROUNDS. A synthesis pass handles the round-limit case.
Message persistence is the router's responsibility — chat() returns a plain string.
"""
import json
import logging
import time

from sqlalchemy.orm import Session

from app.models.ai import AIConversation, AIMessage
from app.models.workspace import Workspace
from app.services import agent_registry, agent_tools, claude_client

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10


def get_conversation_history(
    conversation_id: str, workspace_id: str, db: Session, limit: int = 20
) -> list[dict]:
    """Return the last N messages for a conversation, scoped to workspace_id.
    The workspace join is defence-in-depth — the router already validates ownership,
    but this ensures cross-workspace leakage is impossible at the service layer too.
    """
    messages = (
        db.query(AIMessage)
        .join(AIConversation, AIConversation.id == AIMessage.conversation_id)
        .filter(
            AIMessage.conversation_id == conversation_id,
            AIConversation.workspace_id == workspace_id,
        )
        .order_by(AIMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


def chat(
    workspace_id: str,
    conversation_id: str,
    user_message: str,
    db: Session,
) -> str:
    """
    Agentic chat loop. Claude calls tools to query workspace data before answering.
    Loops until stop_reason == 'end_turn' or MAX_TOOL_ROUNDS is reached.
    If rounds are exhausted, _synthesis_pass() forces a final answer from accumulated results.
    Message persistence is the router's responsibility — this returns a plain string.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    tools = agent_registry.get_tools_for_vertical(workspace.vertical)
    history = get_conversation_history(conversation_id, workspace_id, db)

    system_prompt = (
        f"You are an investigation assistant for workspace '{workspace.name}'. "
        f"Subject: {workspace.subject_name or 'Not specified'}. "
        f"Vertical: {workspace.vertical}. "
        "Use the available tools to look up data before answering. "
        "Answer accurately from tool results only — do not speculate beyond what the data shows. "
        "Be precise with numbers, dates, names, and document references. "
        "Reference documents by filename, not by ID. "
        "When identifying something not yet investigated, end with: "
        "'Next lead to consider: [question]'."
    )

    messages = history + [{"role": "user", "content": user_message}]
    rounds = 0

    while rounds < MAX_TOOL_ROUNDS:
        response = claude_client.get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return _extract_text(response)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    start = time.time()
                    result = agent_tools.execute(
                        block.name, workspace_id, db, block.input
                    )
                    elapsed = time.time() - start
                    logger.info(
                        "tool_call name=%s params=%s result_size=%d latency=%.3fs",
                        block.name,
                        block.input,
                        len(str(result)),
                        elapsed,
                    )
                    is_error = "error" in result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                        "is_error": is_error,
                    })
            messages.append({"role": "user", "content": tool_results})
            rounds += 1
            continue

        break  # Unexpected stop reason — fall through to synthesis pass

    return _synthesis_pass(messages)


def _synthesis_pass(messages: list[dict]) -> str:
    """Force a final answer when the tool-use loop hits MAX_TOOL_ROUNDS.
    Sends accumulated messages to Claude with tools disabled and a directive to synthesize.
    """
    response = claude_client.get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=(
            "You've gathered the following tool results. "
            "Provide your final answer to the user's question using only this data. "
            "No further tool calls are available."
        ),
        messages=messages,
    )
    return _extract_text(response)


def _extract_text(response) -> str:
    """Extract the first text block from a Claude response content list."""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return "I was unable to produce a response."
