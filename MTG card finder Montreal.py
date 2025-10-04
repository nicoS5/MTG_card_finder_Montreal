import streamlit as st

st.set_page_config(
    page_title="Accueil",
    page_icon="🪄",
    layout="wide"
)

st.title("Bienvenue sur MTG Card Finder Montreal !")

st.divider()

st.header("Introduction :")

st.markdown(
"""
Cet outil vous permettra de rechercher des cartes du jeu Magic The Gathering dans les magasins de montreal. A date, seul les magasins suivant sont disponibles :
- Le Valet de coeur
- L'expedition
- Alt F4
            
Il est diviser en **2 sections** qui vous permettront de faire 2 actions distinctes :
""")

st.info("ℹ️ Chercher des cartes dans les magasins de montreal pour trouver leurs prix et leurs disponibilites")
st.success("✅ Trouver les magasins qui ont les cartes en stock pour le meilleur prix !")

st.divider()

st.header("C'est a vous :")

st.markdown(
"""
Pour commencer vos recherches de carte dirigez-vous vers l'onglet **"Importation"** pour commencer.

Si vous voulez consultez le prix des cartes precedemment recherchees, dirigez-vous vers l'onglet **"Optimisation"**. 
""")

st.warning("⚠️ Il se peut que certaines cartes n'ai jamais ete cherchees et donc apparaissent comme indisponible")

st.divider()

st.header("Contact :")

st.markdown(
"""
Pour tous commentaires sur l'outil, ou pour toutes fonctionnalites que vous aimeriez voir ajoutees a l'outil, n'hesitez pas a me contacter. Vous savez qui je suis la Fam.
""")

st.caption("© 2025 - MTG Card Finder Montreal")