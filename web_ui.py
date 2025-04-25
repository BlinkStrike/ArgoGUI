import streamlit as st
import os
from core import manager
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("WEB_USERNAME")
PASSWORD = os.getenv("WEB_PASSWORD")

def check_auth():
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == USERNAME and pwd == PASSWORD:
            st.session_state["authenticated"] = True
        else:
            st.error("Invalid credentials")

def main():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        check_auth()
        return

    st.title("Cloudflare Argo Tunnel Manager")

    if st.button("List Tunnels"):
        st.json(manager.list_tunnels())

    name = st.text_input("Tunnel Name")
    if st.button("Create Tunnel") and name:
        manager.create_tunnel(name)
        st.success("Tunnel created")

    tunnel_id = st.text_input("Tunnel ID to Delete")
    if st.button("Delete Tunnel") and tunnel_id:
        manager.delete_tunnel(tunnel_id)
        st.success("Tunnel deleted")

    if st.button("Start Service"):
        manager.start_service()
        st.success("Service started")

    if st.button("Stop Service"):
        manager.stop_service()
        st.success("Service stopped")

    st.write("Service status:", manager.is_service_running())
