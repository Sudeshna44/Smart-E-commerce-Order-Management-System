"""CrewAI orchestration for order support, inventory, delivery, and resolution."""

import json
import os
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from order_management import (
    get_inventory_findings,
    get_order,
    get_tracking_findings,
    mandatory_escalation_reason,
)


def _parse_resolution(raw_result: str) -> dict[str, Any]:
    try:
        resolution = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Resolution Agent did not return valid JSON. Please retry the request."
        ) from exc

    required_fields = {
        "escalate_to_human",
        "escalation_reason",
        "recommended_next_step",
        "customer_response",
    }
    if not isinstance(resolution, dict) or not required_fields.issubset(resolution):
        raise ValueError("Resolution Agent returned an incomplete resolution.")
    if not isinstance(resolution["escalate_to_human"], bool):
        raise ValueError("Resolution Agent returned an invalid escalation decision.")
    if not all(
        isinstance(resolution[field], str)
        for field in required_fields - {"escalate_to_human"}
    ):
        raise ValueError("Resolution Agent returned invalid resolution details.")
    return resolution


def run_order_workflow(order_id: str, customer_query: str) -> dict[str, Any]:
    """Run all four agents and apply mandatory human-escalation safeguards."""
    load_dotenv()
    order = get_order(order_id)
    tracking = get_tracking_findings(order_id)

    try:
        from crewai import Agent, Crew, LLM, Process, Task
        from crewai.tools import tool
    except ImportError as exc:
        raise RuntimeError(
            "CrewAI is not installed. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    ollama_base_url = os.getenv(
        "OLLAMA_BASE_URL", "https://ollama.com/v1"
    ).strip()
    ollama_api_key = os.getenv("OLLAMA_API_KEY", "").strip()
    if ollama_api_key == "your-ollama-api-key":
        ollama_api_key = ""
    is_local_ollama = urlparse(ollama_base_url).hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if not ollama_api_key and not is_local_ollama:
        raise RuntimeError(
            "Set OLLAMA_API_KEY in your .env file to your Ollama Cloud API key."
        )

    ollama_model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b-cloud").strip()
    if not ollama_model:
        raise RuntimeError("OLLAMA_MODEL must not be empty.")

    model = LLM(
        model=f"openai/{ollama_model}",
        base_url=ollama_base_url,
        api_key=ollama_api_key or "ollama",
    )

    @tool("get_order_details")
    def order_details_tool(requested_order_id: str) -> str:
        """Retrieve the order's product, status, and expected delivery date."""
        return json.dumps(get_order(requested_order_id))

    @tool("inventory_lookup")
    def inventory_tool(requested_order_id: str) -> str:
        """Check stock for an order and suggest an alternative if unavailable."""
        return json.dumps(get_inventory_findings(requested_order_id))

    @tool("order_tracking")
    def tracking_tool(requested_order_id: str) -> str:
        """Check mock shipment tracking status and estimated delivery date."""
        return json.dumps(get_tracking_findings(requested_order_id))

    customer_support = Agent(
        role="Customer Support Agent",
        goal="Understand the customer's issue and verify the correct order details.",
        backstory=(
            "You are a careful e-commerce support specialist. Confirm the supplied "
            "order ID and summarize the customer's issue without inventing facts."
        ),
        tools=[order_details_tool],
        llm=model,
        verbose=False,
    )
    inventory_agent = Agent(
        role="Inventory Agent",
        goal="Verify whether the ordered product is available and suggest alternatives.",
        backstory="You use the inventory tool as the source of truth for stock.",
        tools=[inventory_tool],
        llm=model,
        verbose=False,
    )
    delivery_agent = Agent(
        role="Delivery Agent",
        goal="Check shipment status and report the best available delivery estimate.",
        backstory="You use the tracking tool as the source of truth for shipment updates.",
        tools=[tracking_tool],
        llm=model,
        verbose=False,
    )
    resolution_agent = Agent(
        role="Resolution Agent",
        goal=(
            "Choose a safe and useful next step, deciding whether a human must "
            "take over, and prepare a factual customer response."
        ),
        backstory=(
            "You combine verified support, inventory, and tracking findings. Escalate "
            "when the customer asks for a human; the issue concerns fraud, payment "
            "disputes, legal action, injury, or safety; tracking says lost; or an "
            "automatic reply cannot safely resolve the complaint. Never promise a "
            "refund, replacement, or delivery date not supported by the findings."
        ),
        llm=model,
        verbose=False,
    )

    support_task = Task(
        description=(
            "Review customer query: {customer_query}\n"
            "The order ID supplied by the customer-facing form is {order_id}. "
            "Use get_order_details to verify the order. Identify the order ID and "
            "the customer's issue, distinguishing delivery, inventory, and other "
            "concerns. Report verified facts only."
        ),
        expected_output="A concise summary of the verified order and customer issue.",
        agent=customer_support,
    )
    inventory_task = Task(
        description=(
            "For order {order_id}, use inventory_lookup. State whether the ordered "
            "quantity is available and name the alternative only if out of stock."
        ),
        expected_output="Verified stock availability and an alternative when needed.",
        agent=inventory_agent,
        context=[support_task],
    )
    delivery_task = Task(
        description=(
            "For order {order_id}, use order_tracking. Report the shipment status, "
            "expected date, revised estimate when present, and whether it is delayed."
        ),
        expected_output="Verified tracking status and delivery estimate.",
        agent=delivery_agent,
        context=[support_task],
    )
    resolution_task = Task(
        description=(
            "Resolve the case using the customer query and all preceding verified "
            "findings. Decide whether to escalate to a human. Escalate when the "
            "customer asks for a human, the issue involves fraud/payment/legal/safety, "
            "tracking is lost, or the case cannot be safely resolved automatically. "
            "Return ONLY a JSON object with exactly these keys: "
            '{"escalate_to_human": boolean, "escalation_reason": string, '
            '"recommended_next_step": string, "customer_response": string}. '
            "If no escalation is needed, set escalation_reason to an empty string. "
            "Do not invent a policy, refund, replacement, or delivery promise. "
            "Customer query: {customer_query}"
        ),
        expected_output=(
            "A JSON object with escalation decision, reason, next step, and response."
        ),
        agent=resolution_agent,
        context=[support_task, inventory_task, delivery_task],
    )

    crew = Crew(
        agents=[customer_support, inventory_agent, delivery_agent, resolution_agent],
        tasks=[support_task, inventory_task, delivery_task, resolution_task],
        process=Process.sequential,
        verbose=False,
    )
    result = crew.kickoff(
        inputs={
            "order_id": order["order_id"],
            "customer_query": customer_query,
        }
    )
    resolution = _parse_resolution(str(result))

    required_reason = mandatory_escalation_reason(
        customer_query, tracking["tracking_status"]
    )
    if required_reason:
        resolution["escalate_to_human"] = True
        resolution["escalation_reason"] = required_reason
        resolution["recommended_next_step"] = (
            "A human support representative should review this case and follow up."
        )

    return {
        "order": order,
        "escalation": resolution["escalate_to_human"],
        "escalation_reason": resolution["escalation_reason"],
        "recommended_next_step": resolution["recommended_next_step"],
        "customer_response": resolution["customer_response"],
        "agent_outputs": [
            {
                "agent": getattr(task_output, "agent", "Agent"),
                "output": getattr(task_output, "raw", str(task_output)),
            }
            for task_output in getattr(result, "tasks_output", [])
        ],
    }
