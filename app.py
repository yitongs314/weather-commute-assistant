import streamlit as st

from agent import WeatherCommuteAgent

st.set_page_config(page_title="Weather & Commute Assistant", page_icon="\U0001F324️")
st.title("\U0001F324️ Weather & Commute Assistant")
st.caption("Ask about your commute, an outdoor activity, or an upcoming trip.")

if "agent" not in st.session_state:
    st.session_state.agent = WeatherCommuteAgent()
    st.session_state.history = []


def render_trace(trace: list[dict]) -> None:
    if not trace:
        return
    with st.expander("Agent reasoning & tool calls"):
        for step in trace:
            if step["type"] == "reasoning":
                st.markdown(f"\U0001F4AD {step['text']}")
            elif step["type"] == "tool_call":
                st.markdown(f"\U0001F527 **{step['name']}**")
                st.json({"input": step["input"], "result": step["result"]})


for entry in st.session_state.history:
    with st.chat_message(entry["role"]):
        st.write(entry["text"])
        render_trace(entry.get("trace", []))

if user_input := st.chat_input("e.g. I'm commuting to work tomorrow in San Francisco"):
    st.session_state.history.append({"role": "user", "text": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply, trace = st.session_state.agent.handle_message(user_input)
        st.write(reply)
        render_trace(trace)

    st.session_state.history.append({"role": "assistant", "text": reply, "trace": trace})
