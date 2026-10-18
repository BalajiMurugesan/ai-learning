import streamlit as st
import asyncio
import httpx

FASTAPI_URL = "http://127.0.0.1:8000/expenses/"

st.set_page_config(page_title="Home - AI Expense Tracker", page_icon="🏠", layout="wide")
st.title("🏠 Home / Expense Assistant")
st.caption("Type any expense in plain text (e.g., 'Spent 500 INR on lunch today')")

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Tell me about any expense you incurred today."}
    ]

# Display historical messages from session state
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input via chat input
if prompt := st.chat_input("Enter your expense detail..."):
    # Render user prompt in UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call FastAPI backend asynchronously using httpx and asyncio
    with st.chat_message("assistant"):
        with st.spinner("Processing expense with LLM..."):
            async def call_fastapi():
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        FASTAPI_URL,
                        json={"user_input": prompt}
                    )
                    return response

            try:
                # Use standard Python asyncio.run() to execute the coroutine
                response = asyncio.run(call_fastapi())

                if response.status_code == 201:
                    data = response.json()
                    expense = data.get("extracted_expense", {})
                    usage = data.get("usage", {})

                    success_msg = f"✅ **Expense created successfully!**\n\n" \
                                  f"* **Date:** {expense.get('transaction_date')}\n" \
                                  f"* **Amount:** {expense.get('amount')} {expense.get('currency')}\n" \
                                  f"* **Category:** {expense.get('transaction_type')}\n" \
                                  f"* **Summary:** {expense.get('narrative')}\n\n" \
                                  f"*Tokens Used: {usage.get('total_tokens', 0)} (Cost: ${usage.get('cost_usd', 0.0):.6f})*"

                    st.markdown(success_msg)
                    st.session_state.messages.append({"role": "assistant", "content": success_msg})

                else:
                    error_msg = f"❌ Failed to process expense (Status Code: {response.status_code}). Please try again."
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

            except httpx.RequestError as e:
                connection_error = f"⚠️ Could not connect to FastAPI backend at `{FASTAPI_URL}`. Make sure `uvicorn main:app` is running!"
                st.error(connection_error)
                st.session_state.messages.append({"role": "assistant", "content": connection_error})