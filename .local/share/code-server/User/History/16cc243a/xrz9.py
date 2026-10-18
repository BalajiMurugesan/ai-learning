import asyncio
from openai import AsyncOpenAI
import streamlit as st
#import utils
from dotenv import load_dotenv

import utils
#load_dotenv()
# App title
st.title("Your Personal ChatGPT")
st.caption("Ask any question")

# Initialize the Async OpenAI client using Streamlit secrets
client = AsyncOpenAI()

# Set a default model
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o-mini"

# Initialize historical chat messages in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display prior chat messages from history when the app reruns
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Define the system prompt restricting response length
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are a helpful chatbot that responds to customer questions in less than 20 words."
}


# Async function to fetch and stream the response from OpenAI safely
async def generate_response():
    # Combine the system prompt with the ongoing chat history
    messages_payload = [SYSTEM_PROMPT] + [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]

    stream = await client.chat.completions.create(
        model=st.session_state["openai_model"],
        messages=messages_payload,
        stream=True,
    )

    # Async generator to yield text chunks safely
    async for chunk in stream:
        # Check if choices list is not empty to prevent IndexError
        if chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if delta and delta.content is not None:
                yield delta.content


# Accept user input from the chat box at the bottom
if prompt := st.chat_input("Type your message here..."):
    # Append user message to history and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate and stream response asynchronously on submit
    with st.chat_message("assistant"):
        # st.write_stream natively supports async generators
        response = st.write_stream(generate_response())

    # Append assistant response to session state history
    st.session_state.messages.append({"role": "assistant", "content": response})