import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(
    page_title="Admin",
    page_icon="🅰️",
    layout="wide"
)

## VARIABLE GLOBAL
url: str = st.secrets["supabase"]["SUPABASE_URL"]
key: str  = st.secrets["supabase"]["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🅰️ Admin")

st.divider()

st.header("Message de la commu :")

all_messages = []
page_size = 1000
offset = 0

while True:
    response = supabase.table("message_utilisateur").select('*').range(offset, offset + page_size - 1).execute()
    
    if not response.data: break
    
    all_messages.extend(response.data)
    
    if len(response.data) < page_size: break
    
    offset += page_size

df_all_messages = pd.DataFrame(all_messages).sort_values(["date_message"], ascending=[False])

st.dataframe(df_all_messages, width='stretch')