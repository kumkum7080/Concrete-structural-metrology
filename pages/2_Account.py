import streamlit as st
import pandas as pd
from database import get_user_history

st.set_page_config(page_title="Inspector Profile", page_icon="👤", layout="wide")

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("🔒 Access Blocked. Please authenticate account on the gateway index.")
    st.stop()

st.title("👤 Inspector Workspace Profile")
col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("""
        <div style="background-color:#F1F5F9; padding:20px; border-radius:8px; border:1px solid #E2E8F0; text-align:center;">
            <h2 style="margin:0; color:#475569;">👨‍💻</h2>
            <h3 style="margin:10px 0 5px 0; color:#1E293B;">{0}</h3>
            <p style="color:#64748B; margin:0; font-size:14px;">Access Authorization: Field Analyst Pro</p>
        </div>
    """.format(st.session_state.username), unsafe_allow_html=True)

with col2:
    st.markdown("### Historical Audit Tracking Log")
    user_data = get_user_history(st.session_state.username)

    if not user_data:
        st.info("No execution inspection items mapped to this session profile yet.")
    else:
        df = pd.DataFrame(user_data)
        df.columns = ["Timestamp", "User ID", "Target File Source", "Max Width (mm)", "Tracked Length (mm)", "Risk Classification Profile"]
        st.dataframe(df, use_container_width=True)

        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Complete Audit Ledger as CSV",
            data=csv_data,
            file_name=f"{st.session_state.username}_inspection_history.csv",
            mime="text/csv"
        )
