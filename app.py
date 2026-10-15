"""Streamlit interface for the CrewAI order-management demo."""

import streamlit as st

from crew_workflow import run_order_workflow


st.set_page_config(page_title="Order Support Assistant", page_icon="📦")
st.title("Smart E-Commerce Order Support")
st.write(
    "Ask about an order. The support, inventory, delivery, and resolution agents "
    "will collaborate using the included sample data."
)

with st.form("order_support"):
    order_id = st.text_input("Order ID", placeholder="ORD1025")
    question = st.text_area(
        "How can we help?",
        placeholder="My order is late. Can you check its status?",
    )
    submitted = st.form_submit_button("Check my order")

if submitted:
    if not order_id.strip() or not question.strip():
        st.warning("Enter both an order ID and a question.")
    else:
        with st.spinner("The support team is reviewing your order..."):
            try:
                result = run_order_workflow(order_id, question)
            except Exception as exc:
                st.error(f"Unable to complete the order review: {exc}")
                st.exception(exc)
            else:
                st.subheader("Resolution")
                st.write(result["customer_response"])
                st.write(f"**Recommended next step:** {result['recommended_next_step']}")
                if result["escalation"]:
                    st.warning(
                        "Human support follow-up is recommended. "
                        f"{result['escalation_reason']}"
                    )
                else:
                    st.success("This issue can be handled automatically.")
                with st.expander("Order details"):
                    order = result["order"]
                    order_id_column, product_column, status_column = st.columns(3)
                    with order_id_column:
                        st.caption("Order ID")
                        st.write(order["order_id"])
                    with product_column:
                        st.caption("Product")
                        st.write(order["product"])
                    with status_column:
                        st.caption("Order status")
                        st.write(order["order_status"].replace("_", " ").title())
                with st.expander("Agent collaboration output"):
                    for task_output in result["agent_outputs"]:
                        st.markdown(f"**{task_output['agent']}**")
                        st.write(task_output["output"])
