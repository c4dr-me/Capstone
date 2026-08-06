import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.data_loader import load_sample_data

# Professional Banking Theme
st.set_page_config(
    page_title="ResolveOne AI - Exception Management",
    page_icon="⚠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional CSS
st.markdown("""
<style>
    * { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }

    body { background-color: #f8f9fa; }

    /* Sidebar */
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #1e3a5f 0%, #2a4a7c 100%); }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: white; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { color: #e0e0e0; font-weight: 500; }
    [data-testid="stSidebar"] [role="radio"]:checked + label { color: white; background: rgba(255,255,255,0.1); padding: 8px 12px; border-radius: 6px; }

    /* Main content */
    .main { background-color: #f8f9fa; }

    /* Cards */
    [data-testid="stMetric"] { background: white; padding: 20px; border-radius: 8px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    [data-testid="stMetricLabel"] { font-size: 13px; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #1e3a5f; font-weight: 700; }

    /* Dataframe */
    [data-testid="stDataFrame"] { border-radius: 8px; border: 1px solid #e5e7eb; }
    [data-testid="stDataFrame"] thead { background-color: #f0f1f3; }
    [data-testid="stDataFrame"] thead th { color: #1e3a5f; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid #2a4a7c; }
    [data-testid="stDataFrame"] tbody td { color: #374151; font-size: 13px; }

    /* Buttons */
    button { border-radius: 6px; border: 1px solid #2a4a7c; padding: 10px 16px; font-weight: 500; transition: all 0.2s; }
    button:hover { background-color: #1e3a5f; color: white; box-shadow: 0 4px 12px rgba(30,58,95,0.2); }

    /* Input fields */
    input { border-radius: 6px; border: 1px solid #d1d5db; padding: 10px 12px; }
    input:focus { border-color: #2a4a7c; box-shadow: 0 0 0 3px rgba(42,74,124,0.1); }

    /* Divider */
    hr { border-color: #e5e7eb; }

    /* Headers */
    h1 { color: #1e3a5f; font-size: 28px; font-weight: 700; }
    h2 { color: #1e3a5f; font-size: 20px; font-weight: 600; }
    h3 { color: #1e3a5f; font-size: 16px; font-weight: 600; }

    /* Info boxes */
    [data-testid="stAlert"] { border-radius: 8px; border-left: 4px solid #2a4a7c; }

    /* Tabs */
    [role="tab"] { color: #666; font-weight: 500; border-radius: 6px 6px 0 0; }
    [role="tab"][aria-selected="true"] { color: #1e3a5f; border-bottom: 3px solid #2a4a7c; }
</style>
""", unsafe_allow_html=True)

# Load data
@st.cache_data
def get_data():
    return load_sample_data()

df = get_data()

# ============================================================================
# SIDEBAR
# ============================================================================
st.sidebar.markdown("### 🤖 ResolveOne AI")
st.sidebar.markdown("#### Automation Exception Management")
st.sidebar.divider()

page = st.sidebar.radio("Navigation", [
    "🏠 Dashboard",
    "⚠️ Exception Management",
    "🤖 AI Assistant",
    "📊 Analytics",
    "📋 Audit & Governance",
    "⚙️ Settings"
])

st.sidebar.divider()
st.sidebar.markdown(f"""
**Status:** ✓ Online
**Data:** {len(df):,} transactions
**Exceptions:** {len(df)} active
**Version:** 1.0.0
""")

# ============================================================================
# PAGE 1: DASHBOARD
# ============================================================================
if page == "🏠 Dashboard":
    st.title("📊 Dashboard")
    st.markdown("Real-time exception monitoring and key performance indicators")
    st.divider()

    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Total Exceptions",
            f"{len(df):,}",
            delta="+145 this week",
            delta_color="inverse"
        )
    with col2:
        critical = len(df[df['priority'] == 'Critical'])
        st.metric("Critical Priority", critical, delta="Requires attention", delta_color="inverse")
    with col3:
        resolved = len(df[df['status'] == 'Resolved'])
        st.metric("Resolved", resolved, delta="+12% week-over-week")
    with col4:
        st.metric("Avg Resolution Time", "87 min", delta="-12% improvement")

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Exception Trends (30-Day View)")
        daily = df.groupby(df['date'].dt.date).size()
        chart_data = pd.DataFrame({'Count': daily.values}, index=daily.index)
        st.line_chart(chart_data, color="#2a4a7c", height=350)

    with col2:
        st.subheader("🎯 Exception Distribution")
        counts = df['exception_type'].value_counts()
        fig = go.Figure(data=[go.Pie(
            labels=counts.index,
            values=counts.values,
            marker=dict(colors=['#1e3a5f', '#2a4a7c', '#3b5998', '#5a7abc', '#7a96d6', '#9ab1e0', '#bdd1f4']),
            textposition='inside',
            textinfo='label+percent'
        )])
        fig.update_layout(height=350, showlegend=True, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📋 Recent Exceptions")
    cols_to_show = ['exception_id', 'transaction_id', 'customer_name', 'amount', 'exception_type', 'priority', 'status', 'date']
    available = [c for c in cols_to_show if c in df.columns]
    if 'date' in df.columns:
        st.dataframe(df[available].sort_values('date', ascending=False).head(15), use_container_width=True, hide_index=True)
    else:
        st.dataframe(df[available].head(15), use_container_width=True, hide_index=True)

# ============================================================================
# PAGE 2: EXCEPTION MANAGEMENT
# ============================================================================
elif page == "⚠️ Exception Management":
    st.title("⚠️ Exception Management")
    st.markdown("Search, filter, and manage exceptions across your organization")
    st.divider()

    # Search and controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("🔍 Search exceptions", placeholder="Enter Exception ID or Customer Name...")
    with col2:
        sort_by = st.selectbox("Sort by", ["Date (Newest)", "Date (Oldest)", "Amount (High to Low)", "Priority"])
    with col3:
        view_type = st.radio("View", ["Table", "Details"], horizontal=True)

    st.divider()

    # Filters
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        priority_f = st.multiselect("Priority Level", ["Critical", "High", "Medium", "Low"], default=None)
    with col2:
        status_f = st.multiselect("Status", ["Pending", "In Review", "Resolved", "Escalated"], default=None)
    with col3:
        type_f = st.multiselect("Exception Type", sorted(df['exception_type'].unique().tolist())[:7], default=None)
    with col4:
        dept_f = st.multiselect("Department", sorted(df['department'].unique().tolist()), default=None)
    with col5:
        team_f = st.multiselect("Assigned Team", sorted(df['assigned_team'].unique().tolist()), default=None)

    # Apply filters
    filtered = df.copy()

    if search:
        filtered = filtered[
            filtered['exception_id'].astype(str).str.contains(search, case=False, na=False) |
            filtered['transaction_id'].astype(str).str.contains(search, case=False, na=False) |
            filtered['customer_name'].astype(str).str.contains(search, case=False, na=False)
        ]

    if priority_f:
        filtered = filtered[filtered['priority'].isin(priority_f)]
    if status_f:
        filtered = filtered[filtered['status'].isin(status_f)]
    if type_f:
        filtered = filtered[filtered['exception_type'].isin(type_f)]
    if dept_f:
        filtered = filtered[filtered['department'].isin(dept_f)]
    if team_f:
        filtered = filtered[filtered['assigned_team'].isin(team_f)]

    # Sort
    if sort_by == "Date (Newest)":
        filtered = filtered.sort_values('date', ascending=False)
    elif sort_by == "Date (Oldest)":
        filtered = filtered.sort_values('date', ascending=True)
    elif sort_by == "Amount (High to Low)":
        filtered = filtered.sort_values('amount', ascending=False)
    elif sort_by == "Priority":
        priority_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
        filtered = filtered['priority'].map(priority_order).argsort()
        filtered = filtered.iloc[filtered]

    st.info(f"**{len(filtered)}** exceptions found | **{len(df) - len(filtered)}** filtered out")

    cols_to_show = ['exception_id', 'transaction_id', 'customer_name', 'amount', 'exception_type', 'priority', 'status', 'assigned_team']
    available = [c for c in cols_to_show if c in filtered.columns]

    if available:
        st.dataframe(filtered[available].head(100), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Export to CSV", use_container_width=True):
            csv = filtered[available].to_csv(index=False)
            st.download_button("⬇️ Download CSV", csv, "exceptions.csv", "text/csv")
    with col2:
        st.metric("Total Amount", f"${filtered['amount'].sum():.2f}")

# ============================================================================
# PAGE 3: AI ASSISTANT
# ============================================================================
elif page == "🤖 AI Assistant":
    st.title("🤖 AI Assistant")
    st.markdown("Intelligent exception analysis and recommendation engine")
    st.divider()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("💡 Quick Analysis")
        if st.button("Why did this exception occur?", use_container_width=True):
            st.session_state.ai_question = "Why"
        if st.button("Show similar cases", use_container_width=True):
            st.session_state.ai_question = "Similar"
        if st.button("What should I do next?", use_container_width=True):
            st.session_state.ai_question = "Next"
        if st.button("What's the policy?", use_container_width=True):
            st.session_state.ai_question = "Policy"

    with col2:
        st.subheader("📊 Current Status")
        st.metric("Total Exceptions", f"{len(df):,}")
        st.metric("Critical Cases", len(df[df['priority'] == 'Critical']))
        st.metric("Pending Review", len(df[df['status'] == 'Pending']))

    st.divider()
    st.subheader("💬 Conversation")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for role, message in st.session_state.chat_messages:
        with st.chat_message(role):
            st.write(message)

    user_input = st.chat_input("Ask a question about your exceptions...")
    if user_input:
        st.session_state.chat_messages.append(("user", user_input))

        # AI responses
        responses = {
            "why": "Based on exception analysis: This exception occurred due to insufficient balance in the customer's account. The transaction amount exceeded available funds.",
            "similar": "I identified 47 similar cases in the last 30 days. Pattern: 85% related to insufficient balance, 10% technical issues, 5% validation failures.",
            "next": "Recommended workflow: 1) Send account balance notification, 2) Offer deposit options, 3) Monitor for retry attempts, 4) Follow up within 24 hours.",
            "policy": "Per Policy EXC-2024-001: Exceptions require resolution within 24 hours. Critical cases: 4 hours. Escalation available after 2 hours without customer contact.",
        }

        response = "I'm here to help analyze exceptions. Ask me about causes, patterns, recommendations, or policies."
        for key, resp in responses.items():
            if key.lower() in user_input.lower():
                response = resp
                break

        st.session_state.chat_messages.append(("assistant", response))
        st.rerun()

# ============================================================================
# PAGE 4: ANALYTICS
# ============================================================================
elif page == "📊 Analytics":
    st.title("📊 Analytics & Performance")
    st.markdown("Comprehensive metrics and trend analysis")
    st.divider()

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Avg Resolution Time", "87 min", delta="-12% (improvement)", delta_color="normal")
    with col2:
        st.metric("SLA Compliance", "92%", delta="↑ On track")
    with col3:
        st.metric("AI Accuracy", "94%")
    with col4:
        st.metric("Team Throughput", "234/day")

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Resolution Trend (7 Days)")
        trend = pd.DataFrame({
            'Day': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            'Resolved': [45, 52, 48, 61, 58, 42, 50]
        })
        st.line_chart(trend.set_index('Day')['Resolved'], color="#2a4a7c", height=300)

    with col2:
        st.subheader("🎯 Exception Distribution by Type")
        counts = df['exception_type'].value_counts()
        st.bar_chart(counts, color="#2a4a7c", height=300)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👥 Team Performance")
        teams = df['assigned_team'].value_counts()
        st.bar_chart(teams, color="#3b5998", height=300)

    with col2:
        st.subheader("📊 SLA Compliance Status")
        sla = pd.DataFrame({'Status': ['Met', 'Violated'], 'Count': [245, 20]})
        fig = go.Figure(data=[go.Pie(
            labels=sla['Status'],
            values=sla['Count'],
            marker=dict(colors=['#2a4a7c', '#e74c3c']),
            textinfo='label+percent'
        )])
        fig.update_layout(height=300, showlegend=True, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("📋 Department Metrics")
    dept_data = pd.DataFrame({
        'Department': ['Payment Processing', 'Card Services', 'Risk Management', 'Customer Support'],
        'Total': [450, 320, 280, 210],
        'Critical': [15, 12, 8, 5],
        'Resolved': [380, 270, 240, 185],
        'Compliance %': ['84%', '84%', '86%', '88%']
    })
    st.dataframe(dept_data, use_container_width=True, hide_index=True)

# ============================================================================
# PAGE 5: AUDIT & GOVERNANCE
# ============================================================================
elif page == "📋 Audit & Governance":
    st.title("📋 Audit & Governance")
    st.markdown("Compliance tracking, activity logs, and approval workflows")
    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["Activity Log", "Approvals", "AI Recommendations", "Compliance"])

    with tab1:
        st.subheader("Recent Activities")
        activities = [
            ("16:48", "Exception Resolved", "John Smith", "EXC-000234", "✅"),
            ("16:45", "Escalated to Manager", "Sarah Johnson", "EXC-000212", "⬆️"),
            ("16:30", "AI Analysis Completed", "ResolveOne AI", "EXC-000198", "🤖"),
            ("15:45", "Exception Assigned", "System", "EXC-000156", "👥"),
            ("15:20", "Customer Notified", "Sarah Johnson", "EXC-000145", "📧"),
        ]
        for time, action, actor, exc_id, icon in activities:
            st.write(f"{icon} **{time}** — {action} by *{actor}* ({exc_id})")

    with tab2:
        st.subheader("Approval Workflow")
        approvals = pd.DataFrame({
            'Exception ID': ['EXC-000234', 'EXC-000212', 'EXC-000198'],
            'Priority': ['High', 'Critical', 'Medium'],
            'Status': ['✅ Approved', '⏳ Pending (Manager)', '✅ Approved'],
            'Approver': ['Manager A', 'VP Finance', 'Manager B'],
            'Date': ['2 hours ago', 'Awaiting', '4 hours ago']
        })
        st.dataframe(approvals, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("AI Analysis Log")
        log = pd.DataFrame({
            'Exception ID': ['EXC-000234', 'EXC-000212', 'EXC-000198'],
            'AI Recommendation': ['Contact customer', 'Escalate to compliance', 'Retry transaction'],
            'Confidence': ['95%', '92%', '88%'],
            'Acted Upon': ['✅ Yes', '✅ Yes', '❌ Override'],
            'Outcome': ['Resolved', 'In Progress', 'Resolved']
        })
        st.dataframe(log, use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("Compliance Status")
        col1, col2 = st.columns(2)
        with col1:
            st.success("✅ Data Masking: Applied")
            st.success("✅ PII Removal: Verified")
            st.success("✅ Audit Trail: Enabled")
        with col2:
            st.success("✅ Access Control: Role-based")
            st.success("✅ Encryption: Active")
            st.info("⏳ Q4 External Audit: Scheduled")

# ============================================================================
# PAGE 6: SETTINGS
# ============================================================================
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    st.markdown("Configure your preferences, notifications, and system settings")
    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["Preferences", "Notifications", "Security", "System"])

    with tab1:
        st.subheader("User Preferences")
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Theme", ["Light", "Dark", "Auto"], index=2)
            st.selectbox("Default View", ["Dashboard", "Exception Management", "Analytics"], index=0)
            st.selectbox("Timezone", ["UTC", "EST", "CST", "MST", "PST"], index=1)
        with col2:
            st.selectbox("Date Format", ["YYYY-MM-DD", "MM/DD/YYYY", "DD/MM/YYYY"], index=0)
            st.selectbox("Currency", ["USD", "EUR", "GBP", "CHF"], index=0)
            st.selectbox("Language", ["English", "Spanish", "French", "German"], index=0)

        if st.button("💾 Save Preferences", use_container_width=True):
            st.success("✅ Preferences saved successfully")

    with tab2:
        st.subheader("Notification Configuration")
        st.checkbox("Critical Exceptions - Email", value=True)
        st.checkbox("Critical Exceptions - SMS", value=False)
        st.checkbox("SLA Violations - Email", value=True)
        st.checkbox("Daily Summary Report", value=False)
        st.text_input("Email Address", value="user@company.com", disabled=False)

        if st.button("💾 Update Notifications", use_container_width=True):
            st.success("✅ Notification settings updated")

    with tab3:
        st.subheader("Security & Access")
        st.write("✅ **Two-Factor Authentication:** Enabled")
        st.write("✅ **Last Login:** Today at 09:45 AM")
        st.write("✅ **Session Timeout:** 30 minutes")
        st.write("✅ **Active Sessions:** 2")

        if st.button("🔑 Change Password", use_container_width=True):
            st.info("Redirecting to secure password change page...")

    with tab4:
        st.subheader("System Information")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Version:** 1.0.0")
            st.write("**Environment:** Production")
            st.write("**Database:** Connected ✓")
        with col2:
            st.write("**Last Update:** 2026-08-06")
            st.write("**Status:** Online ✓")
            st.write("**Uptime:** 99.9%")

        st.progress(0.65, text="Storage: 65% Used (6.5 GB / 10 GB)")
