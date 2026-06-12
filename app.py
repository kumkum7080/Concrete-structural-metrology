import streamlit as st
from database import init_dbs, verify_user, register_user

st.set_page_config(page_title="InspectShield Pro", page_icon="🛡️", layout="wide")

init_dbs()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

st.title("🛡️ InspectShield Pro")
st.subheader("Enterprise Structural Metrology Platform")

if not st.session_state.logged_in:
    st.write("---")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### Secure Gateway Login")
        login_user = st.text_input("Username", key="login_user_input")
        login_pass = st.text_input("Password", type="password", key="login_pass_input")
        if st.button("Authorize Session"):
            if verify_user(login_user, login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.success(f"Session established. Welcome back, {login_user}!")
                st.rerun()
            else:
                st.error("Invalid structural credentials.")

    with col2:
        st.markdown("### Create Inspector Account")
        new_user = st.text_input("Preferred Username", key="new_user_input")
        new_pass = st.text_input("Secure Password", type="password", key="new_pass_input")
        if st.button("Register Credentials"):
            if new_user and new_pass:
                if register_user(new_user, new_pass):
                    st.success("Account created successfully! Proceed to login.")
                else:
                    st.warning("Username already cataloged in database.")
            else:
                st.error("Fields cannot be empty.")
else:
    st.success(f"🛡️ System active. Active Field Agent: **{st.session_state.username}**")
    st.info("👈 Use the left directory to switch to the Interactive Dashboard view.")
    if st.sidebar.button("Terminate Session (Log Out)"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()
