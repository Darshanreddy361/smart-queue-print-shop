import os
import time
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://printshop-api:8000").rstrip("/")
STATUSES = ["queued", "printing", "binding", "ready", "collected", "cancelled"]
STATUS_LABELS = {
    "queued": "In queue", "printing": "Printing", "binding": "Binding",
    "ready": "Ready for pickup", "collected": "Collected", "cancelled": "Cancelled",
}

st.set_page_config(page_title="Campus Print Queue", page_icon="🖨️", layout="wide")

def api_request(method, path, **kwargs):
    try:
        response = requests.request(method, f"{API_URL}{path}", timeout=8, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"Could not reach the print shop server: {exc}")
        return None

st.title("🖨️ Campus Print Shop")
st.caption("Skip the line. Submit your print job and collect it when it is ready.")

student_tab, shop_tab = st.tabs(["🎓 Student portal", "🧑‍🔧 Shopkeeper dashboard"])

with student_tab:
    st.subheader("Place a print order")
    with st.form("new_order", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            student_name = st.text_input("Your name")
            document_name = st.text_input("Document / file name", placeholder="e.g. Physics Lab Record")
            pages = st.number_input("Total pages", min_value=1, max_value=2000, value=20)
        with col2:
            copies = st.number_input("Number of copies", min_value=1, max_value=20, value=1)
            binding = st.selectbox("Binding type", ["none", "soft", "spiral"],
                                   format_func=lambda x: {"none": "No binding", "soft": "Soft binding", "spiral": "Spiral binding"}[x])
        submitted = st.form_submit_button("Submit order", type="primary", use_container_width=True)
    if submitted:
        if not student_name.strip() or not document_name.strip():
            st.warning("Please enter your name and document name.")
        else:
            result = api_request("POST", "/orders", json={
                "student_name": student_name.strip(), "document_name": document_name.strip(),
                "pages": int(pages), "copies": int(copies), "binding": binding
            })
            if result:
                st.session_state["last_order_id"] = result["id"]
                st.success(f"Order #{result['id']} submitted! Estimated pickup: about {result['estimated_minutes']} minute(s).")

    st.divider()
    st.subheader("Track your order")
    default_id = st.session_state.get("last_order_id", 1)
    track_col, button_col = st.columns([3, 1])
    with track_col:
        order_id = st.number_input("Order ID", min_value=1, step=1, value=int(default_id))
    with button_col:
        st.write("")
        st.write("")
        refresh = st.button("Check status", use_container_width=True)
    if refresh or "last_order_id" in st.session_state:
        order = api_request("GET", f"/orders/{int(order_id)}")
        if order:
            st.markdown(f"### Order #{order['id']} — {STATUS_LABELS.get(order['status'], order['status'])}")
            a, b, c = st.columns(3)
            a.metric("Estimated pickup", f"{order['estimated_minutes']} min" if order["status"] in ("queued", "printing", "binding") else "—")
            b.metric("Pages", order["pages"] * order["copies"])
            c.metric("Binding", order["binding"].title())
            if order["status"] == "ready":
                st.success("🔔 Your print is ready! Please collect it from the counter.")
            elif order["status"] in ("collected", "cancelled"):
                st.info(f"Order is {order['status']}.")
            else:
                st.info("Your order is being processed. Check again for live updates.")

    # Lightweight automatic refresh for the student's latest order.
    if "last_order_id" in st.session_state:
        @st.fragment(run_every="15s")
        def live_order_status():
            current = api_request("GET", f"/orders/{st.session_state['last_order_id']}")
            if current:
                if current["status"] == "ready":
                    st.success(f"🔔 Order #{current['id']} is READY for pickup!")
                else:
                    st.caption(f"Live status: {STATUS_LABELS.get(current['status'], current['status'])} · Estimated pickup: {current['estimated_minutes']} min")
        live_order_status()

with shop_tab:
    st.subheader("Live shop overview")
    summary = api_request("GET", "/queue/summary")
    if summary:
        m1, m2, m3 = st.columns(3)
        m1.metric("Active orders", summary["active_orders"])
        m2.metric("Ready for pickup", summary["ready_orders"])
        m3.metric("Total estimated queue", f"{summary['estimated_queue_minutes']} min")

    st.subheader("Manage orders")
    if st.button("Refresh order list"):
        st.rerun()
    orders = api_request("GET", "/orders")
    if orders:
        for order in orders:
            with st.container(border=True):
                left, middle, right = st.columns([3, 2, 2])
                with left:
                    st.markdown(f"**#{order['id']} · {order['student_name']}**")
                    st.caption(f"{order['document_name']} · {order['pages']} pages × {order['copies']} · {order['binding']} binding")
                with middle:
                    st.write(f"**{STATUS_LABELS.get(order['status'], order['status'])}**")
                    st.caption(f"ETA: {order['estimated_minutes']} min")
                with right:
                    new_status = st.selectbox("Update status", STATUSES,
                        index=STATUSES.index(order["status"]), key=f"status_{order['id']}",
                        label_visibility="collapsed",
                        format_func=lambda x: STATUS_LABELS[x])
                    if st.button("Save", key=f"save_{order['id']}"):
                        updated = api_request("PATCH", f"/orders/{order['id']}/status", json={"status": new_status})
                        if updated:
                            st.success(f"Order #{order['id']} updated.")
                            st.rerun()
    else:
        st.info("No orders yet.")
