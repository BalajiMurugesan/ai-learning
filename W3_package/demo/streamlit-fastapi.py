import streamlit as st
import requests
import json
import re
from pydantic import BaseModel

# FastAPI Backend URL
FASTAPI_URL = "http://localhost:8000/generate/post?stream=true"

# Page Configuration
st.set_page_config(
    page_title="OpenAI Assistant Chatbot",
    page_icon="💬",
    layout="centered"
)

st.title("💬 OpenAI Assistant Chatbot")
st.caption("Powered by FastAPI, OpenAI, and Streamlit (POST Streaming)")

# ==========================================
# Pydantic Model for Usage
# ==========================================
class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float

# ==========================================
# Initialize Session State for Chat History
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display prior chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "usage" in message and message["usage"]:
            u = message["usage"]
            st.info(
                f"📊 **Usage Stats** | Prompt: {u.prompt_tokens} | "
                f"Completion: {u.completion_tokens} | Total: {u.total_tokens} | "
                f"Cost: **${u.cost_usd:.6f}**"
            )

# ==========================================
# Handle User Input
# ==========================================
if prompt := st.chat_input("What is your question?"):
    # 1. Append and display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Generate and display assistant response via POST Streaming
    with st.chat_message("assistant"):
        # Use a dictionary or list container to safely mutate state inside the inner generator
        state = {"buffer": ""}
        usage_obj = None

        try:
            payload = {"query": prompt}

            # Generator function to consume chunks from requests stream
            def stream_generator():
                with requests.post(FASTAPI_URL, json=payload, stream=True) as response:
                    if response.status_code == 200:
                        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                            if chunk:
                                state["buffer"] += chunk
                                
                                # If the usage payload text arrives in the final chunk, filter it out from the typewriter display
                                if "[Usage Stats]" in chunk:
                                    clean_part = chunk.split("[Usage Stats]")[0]
                                    if clean_part:
                                        yield clean_part
                                    break
                                else:
                                    yield chunk
                    else:
                        yield f"Error {response.status_code}: {response.text}"

            # Stream text cleanly using Streamlit's native write_stream
            st.write_stream(stream_generator())

            # 3. Extract Usage Stats from the accumulated buffer via Regex
            match = re.search(
                r"\[Usage Stats\] Prompt Tokens: (\d+) \| Completion Tokens: (\d+) \| Total Tokens: (\d+) \| Estimated Cost: \$([\d\.]+)",
                state["buffer"]
            )
            
            if match:
                usage_obj = Usage(
                    prompt_tokens=int(match.group(1)),
                    completion_tokens=int(match.group(2)),
                    total_tokens=int(match.group(3)),
                    cost_usd=float(match.group(4))
                )
                st.info(
                    f"📊 **Usage Stats** | Prompt: {usage_obj.prompt_tokens} | "
                    f"Completion: {usage_obj.completion_tokens} | Total: {usage_obj.total_tokens} | "
                    f"Cost: **${usage_obj.cost_usd:.6f}**"
                )

            # Strip the usage footer string from the saved text history
            clean_display_text = state["buffer"].split("[Usage Stats]")[0].strip()

            # 4. Save assistant response and metrics to session state history
            st.session_state.messages.append({
                "role": "assistant",
                "content": clean_display_text,
                "usage": usage_obj
            })

        except Exception as e:
            error_msg = f"Connection error: {str(e)}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})