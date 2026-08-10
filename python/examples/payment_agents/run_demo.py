"""Run multiple agents against the payment app; print .situation results."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ensure src on path when run as script
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from examples.payment_agents.app import (  # noqa: E402
    ORDERS,
    ag,
    ch,
    load_payable,
    pay_order,
    refund_order,
    reset_demo,
    select_order,
    st,
)
from ux_channel.context import Principal


def facts() -> dict:
    return {
        "orders": {
            oid: {
                "user_id": o.user_id,
                "status": o.status,
                "payable": load_payable(oid).to_dict(),
            }
            for oid, o in ORDERS.items()
        },
        "selected_order": st.session("selected_order", "").peek() or None,
        "pay_step": st.session("pay_step", "review").peek(),
    }


def show(title: str, sit: dict) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    print(json.dumps(sit, indent=2, default=str))


def main() -> None:
    # Reset world
    ag.clear_policy()
    ag.dispatch("reset_demo", {})

    # ── Agent personas (different power) ─────────────────────────────
    clerk = ag.peer("agent.clerk", scopes=("pay", "select"))
    cashier = ag.peer("agent.cashier", scopes=("pay", "select", "charge"))
    refund_bot = ag.peer("agent.refund", scopes=("pay", "refund"))
    auditor = ag.peer("agent.auditor", scopes=("read",))

    # Policy: clerk cannot refund; auditor is read-only; refund_bot blocked from pay
    # We use ag.block per persona by cloning situation views with exclude lists.

    print("\n### INITIAL SITUATIONS (before any payment)\n")

    show(
        "1) CLERK situation (can select + see tools, no refund)",
        ag.situation(
            Principal(id="agent.clerk"),
            facts=facts(),
            notices=["Role: clerk — select orders only; manager pays"],
        )
        | {"allowed": [t["name"] for t in ag.tools_for(exclude=["refund_order", "reset_demo"])]},
    )

    # tools_for with exclude for display
    clerk_tools = [t["name"] for t in ag.tools_for(exclude=["refund_order", "reset_demo"])]
    show(
        "1b) CLERK tools_for",
        {"peer": "agent.clerk", "tools": clerk_tools},
    )

    cashier_tools = [t["name"] for t in ag.tools_for(exclude=["refund_order"])]
    show(
        "2) CASHIER situation",
        {
            **ag.situation(
                Principal(id="agent.cashier"),
                facts=facts(),
                notices=["Role: cashier — may pay selected orders"],
            ),
            "allowed": cashier_tools,
        },
    )

    refund_tools = [t["name"] for t in ag.tools_for(include=["refund_order", "select_order"])]
    show(
        "3) REFUND BOT situation",
        {
            **ag.situation(
                Principal(id="agent.refund"),
                facts=facts(),
                notices=["Role: refund-only"],
            ),
            "allowed": refund_tools,
            "blocked": ["pay_order", "reset_demo"],
        },
    )

    show(
        "4) AUDITOR situation (read-only — no mutating tools)",
        {
            **ag.situation(
                Principal(id="agent.auditor"),
                facts=facts(),
                notices=["Role: auditor — observe only"],
            ),
            "allowed": [],
            "blocked": [t["name"] for t in ag.tools_for()],
        },
    )

    # ── Run multi-agent workflow ─────────────────────────────────────
    print("\n### MULTI-AGENT RUN\n")

    r1 = ag.dispatch("select_order", {"order_id": "ord_1001"}, peer=clerk)
    print("clerk select_order →", ag.effects(r1).to_dict())

    show(
        "5) CASHIER situation AFTER select",
        {
            **ag.situation(
                Principal(id="agent.cashier"),
                facts=facts(),
                notices=["Order selected by clerk; ready to charge from DB amount"],
            ),
            "allowed": cashier_tools,
        },
    )

    r2 = ag.dispatch("pay_order", {"order_id": "ord_1001"}, peer=cashier)
    print("cashier pay_order →", ag.effects(r2).to_dict())

    show(
        "6) REFUND BOT situation AFTER pay",
        {
            **ag.situation(
                Principal(id="agent.refund"),
                facts=facts(),
                notices=["Order paid — refund permitted for this bot"],
            ),
            "allowed": refund_tools,
        },
    )

    r3 = ag.dispatch("refund_order", {"order_id": "ord_1001"}, peer=refund_bot)
    print("refund_bot refund_order →", ag.effects(r3).to_dict())

    show(
        "7) AUDITOR situation AFTER refund (final world facts)",
        {
            **ag.situation(
                Principal(id="agent.auditor"),
                facts=facts(),
                notices=["Post-refund snapshot for compliance"],
            ),
            "allowed": [],
        },
    )

    # blocked cashier cannot refund if we block
    ag.block("refund_order")
    r4 = ag.dispatch("refund_order", {"order_id": "ord_1002"}, peer=cashier)
    print("cashier refund (blocked) →", ag.effects(r4).to_dict())

    show(
        "8) CASHIER situation with refund blocked on façade",
        ag.situation(
            Principal(id="agent.cashier"),
            facts=facts(),
            notices=["refund_order blocked on Agents façade"],
        ),
    )

    if getattr(ch, "audit", None):
        pack = ch.audit.export()
        print("\n### AUDIT SUMMARY")
        print(json.dumps({"intent_count": len(pack["intents"]), "frame_count": len(pack["frames"])}, indent=2))
        print("actions:", [i["action"] for i in pack["intents"]])


if __name__ == "__main__":
    main()
