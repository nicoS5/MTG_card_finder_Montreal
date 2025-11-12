import streamlit as st
import pandas as pd
import re
import pytz
from datetime import datetime
from supabase import create_client

st.set_page_config(
    page_title="Chercher une carte",
    page_icon="🤝",
    layout="wide"
)

## VARIABLE GLOBAL
url: str = st.secrets["supabase"]["SUPABASE_URL"]
key: str  = st.secrets["supabase"]["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🤝Laisser un message")

st.markdown(
"""
Dans cette section, vous pourrez laisser un message.
Si vous avez des idees ou des commentaire sur comment ameliorer l'app, n'hesitez pas !
""")

st.divider()

st.header("Entrez votre nom ci-dessous :")

nom_utilisateur = st.text_input("", 
              placeholder = "Entrez votre nom")

st.header("Entrez votre message ci-dessous :")

message_utilisateur = st.text_area(
    label = "Liste de cartes Magic :",
    label_visibility= "hidden",
    value = "",
    placeholder = "Message ...")

if st.button("Envoyer le message"):

    if message_utilisateur == "" :
        st.warning("⚠️ Vous n'avez pas entre de message.")
    elif nom_utilisateur == "" :
        st.warning("⚠️ Vous n'avez pas entre de nom.")
    else:
        fuseau_horaire_montreal = pytz.timezone('America/Montreal') 
        match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now(fuseau_horaire_montreal)))
        date_recherche = match_pour_date_recherche.group(1) if match_pour_date_recherche else None

        df_message = pd.DataFrame({
            "date_message": [date_recherche],
            "nom_utilisateur": [nom_utilisateur],
            "text_message": [message_utilisateur]
        })

        df_message = df_message.to_dict("records")
        supabase.table("message_utilisateur").insert(df_message).execute()
        st.success("✅ Message envoye !")