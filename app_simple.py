import streamlit as st

st.set_page_config(page_title="ResolveOne AI", page_icon="⚠️", layout="wide")

st.sidebar.title("🤖 ResolveOne")

page = st.sidebar.radio("Navigation", [
    "🏠 Dashboard",
    "⚠️ Exception Management",
    "🤖 AI Assistant",
    "📊 Analytics",
    "📋 Audit & Governance",
    "⚙️ Settings"
])

if page == "🏠 Dashboard":
    st.title("📊 Dashboard")
    st.write("Dashboard content here")
    st.metric("Total", 3126)

elif page == "⚠️ Exception Management":
    st.title("⚠️ Exception Management")
    st.write("Exception Management content here")
    st.text_input("Search")

elif page == "🤖 AI Assistant":
    st.title("🤖 AI Assistant")
    st.write("AI Assistant content here")
    st.button("Question 1")

elif page == "📊 Analytics":
    st.title("📊 Analytics")
    st.write("Analytics content here")
    st.metric("Avg Time", "87 min")

elif page == "📋 Audit & Governance":
    st.title("📋 Audit & Governance")
    st.write("Audit content here")
    st.write("Activity log")

elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    st.write("Settings content here")
    st.selectbox("Theme", ["Light", "Dark"])
