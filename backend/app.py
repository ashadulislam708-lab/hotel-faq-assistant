"""Streamlit chat UI for the Hotel FAQ Assistant."""

import streamlit as st

from config import require_config
from rag import answer_question

st.set_page_config(page_title="Hotel FAQ Assistant")
st.title("Hotel FAQ Assistant")

try:
    require_config("OPENAI_API_KEY", "DATABASE_URL")
except RuntimeError as e:
    st.error(str(e))
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_sources(sources: list[dict]):
    if not sources:
        return
    with st.expander("Sources"):
        for source in sources:
            st.markdown(
                f"**{source['category']}** — {source['question']} "
                f"(similarity {source['similarity']:.2f})"
            )
            st.caption(source["text"])


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        render_sources(message.get("sources", []))

if question := st.chat_input("Ask a question about the hotel"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching FAQ..."):
            try:
                result = answer_question(question)
            except Exception as e:
                st.error(f"Something went wrong: {e}")
                st.stop()
        st.write(result["answer"])
        render_sources(result["sources"])

    st.session_state.messages.append(
        {"role": "assistant", "content": result["answer"], "sources": result["sources"]}
    )
