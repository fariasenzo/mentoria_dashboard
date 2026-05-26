import streamlit as st
import psycopg2
import os
from dotenv import load_dotenv
from views.vendas import show_vendas
from views.marketing import show_marketing

load_dotenv()

def get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, "")

DATABASE_URL = get_secret("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
LEADFY_URL   = get_secret("LEADFY_URL").replace("postgresql+asyncpg://", "postgresql://")

st.set_page_config(page_title="Dashboard Mentoria", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

with open("assets/style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

@st.cache_resource
def get_conn():
    if not DATABASE_URL:
        st.error("DATABASE_URL não encontrada. Configure nos Secrets do Streamlit Cloud.")
        return None
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        st.error(f"Erro ao conectar ao banco principal: {e}")
        return None

@st.cache_resource
def get_leadfy_conn():
    if not LEADFY_URL:
        st.error("LEADFY_URL não encontrada. Configure nos Secrets do Streamlit Cloud.")
        return None
    try:
        return psycopg2.connect(LEADFY_URL)
    except Exception as e:
        st.error(f"Erro ao conectar ao Leadfy: {e}")
        return None

if "pagina" not in st.session_state:
    st.session_state.pagina = "vendas"

with st.sidebar:
    st.markdown("## Mentoria")
    st.markdown("---")
    if st.button("📈 Vendas", use_container_width=True):
        st.session_state.pagina = "vendas"
    if st.button("📣 Marketing", use_container_width=True):
        st.session_state.pagina = "marketing"

conn         = get_conn()
leadfy_conn  = get_leadfy_conn()

if st.session_state.pagina == "vendas":
    show_vendas(conn)
elif st.session_state.pagina == "marketing":
    show_marketing(leadfy_conn)
