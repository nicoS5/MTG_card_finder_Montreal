import streamlit as st
import pandas as pd
from supabase import create_client
import re

# Fonctions --------------------------------------------------------------------------------------------------------

## Fontion Optimisation.py
def Is_other_named_card(card_store_name: str, card_name: str):

    Bad_card_name: bool = card_store_name.find(card_name) < 0
    Bad_card_name: bool = Bad_card_name or card_store_name.find("art card") >= 0
    Bad_card_name: bool = Bad_card_name or card_store_name.find("double-sided token") >= 0
    # Bad_card_name: bool = Bad_card_name or card_store_name.find("display commander - thick stock") >= 0
    # Bad_card_name: bool = Bad_card_name or card_store_name[2:3] == "/"

    return Bad_card_name
def get_all_databases(supabase):

    df_all_data = pd.concat([get_all_data_from_magasin(supabase, "inventaire_VdC"),
                            get_all_data_from_magasin(supabase, "inventaire_Expedition"),
                            get_all_data_from_magasin(supabase, "inventaire_Alt_F4")],
                            ignore_index= True)
    df_all_data = df_all_data[df_all_data["etat_carte"] != "OoS"]

    return(df_all_data)
def filtrer_les_cartes_par_quantite(df_carte, carte):
    if len(df_carte) > 0:
        somme_cumulative = df_carte['stock_carte'].cumsum()

        total_carte_disponible = somme_cumulative.argmax()

        if total_carte_disponible < carte.quantite:
            # si la carte est dispo mais on manque de stock
            df_carte = pd.concat([df_carte,
                                  pd.DataFrame({
                                     "id_carte": [0],
                                     "nom_carte": [carte.nom_carte],
                                     "prix_carte": [0.00],
                                     "langue_carte": ["Indisponible"],
                                     "etat_carte": ["Indisponible"],
                                     "stock_carte": [carte.quantite - total_carte_disponible],
                                     "date_recherche": ["Indisponible"],
                                     "page_magasin": [0],
                                     "lien_carte": ["Indisponible"],
                                     "nom_magasin": ["Indisponible"],
                                     "priorite_mag": [1000]
                                     })],
                                 ignore_index=True)

        else:
            # si la carte est dispo on prend juste le stock qu'il faut
            lignes_necessaires = (somme_cumulative >= carte.quantite).argmax() + 1

            df_carte = df_carte.head(lignes_necessaires)
            df_carte.at[df_carte.index[-1], 'stock_carte'] = df_carte.at[df_carte.index[-1], 'stock_carte'] - (somme_cumulative.iloc[lignes_necessaires-1] - carte.quantite)

    else:
        # si la carte n'est pas du tout disponible
        df_carte = pd.DataFrame({
            "id_carte": [0],
            "nom_carte": [carte.nom_carte],
            "prix_carte": [0.00],  
            "langue_carte": ["Indisponible"],
            "etat_carte": ["Indisponible"],
            "stock_carte": [carte.quantite],
            "date_recherche": ["Indisponible"],
            "page_magasin": [0],
            "lien_carte": ["Indisponible"],
            "nom_magasin": ["Indisponible"],
            "priorite_mag": [1000]
        })

    return(df_carte)
def get_prices_in_stores(df_cartes_intrant, list_magasin_intrant, df_all_data, list_of_basic_lands):
    df_ordre_magasin = pd.DataFrame({
        'nom_magasin': list_magasin_intrant,
        'priorite_mag': range(len(list_magasin_intrant))
    })

    df_all_data = df_all_data[df_all_data["nom_magasin"].isin(list_magasin_intrant)].merge(df_ordre_magasin, on= "nom_magasin", how= "left")

    df_cartes_retenues = df_all_data.head(0) 

    for index_carte, carte in enumerate(df_cartes_intrant.itertuples()): # Boucle sur toutes les cartes dans le a chercher

        if carte.nom_carte in list_of_basic_lands:

            df_carte = pd.DataFrame({
                "id_carte": [1],
                "nom_carte": [carte.nom_carte],
                "prix_carte": [0.10],  
                "langue_carte": ["English"],
                "etat_carte": ["NM-Mint"],
                "stock_carte": [carte.quantite],
                "date_recherche": [""],
                "page_magasin": [0],
                "lien_carte": ["all"],
                "nom_magasin": ["lands"],
                "priorite_mag": [999]
            })

        else :
            df_carte = df_all_data[df_all_data["nom_carte"].apply(lambda x: not(Is_other_named_card(x, carte.nom_carte)))].sort_values(["prix_carte", "priorite_mag"], ascending= [True, True])
            df_carte = filtrer_les_cartes_par_quantite(df_carte, carte)
    
        df_cartes_retenues = pd.concat([df_cartes_retenues,
                                        df_carte],
                                        ignore_index=True)

    df_cartes_retenues = df_cartes_retenues.sort_values(["priorite_mag", "prix_carte", "nom_carte"], ascending= [True, False, True])

    return(df_cartes_retenues)
def get_all_data_from_magasin(supabase, nom_table_magasin):
    all_data_magasin = []
    page_size = 1000
    offset = 0

    while True:
        response = supabase.table(nom_table_magasin).select('*').neq('etat_carte', 'OoS').range(offset, offset + page_size - 1).execute()
        
        if not response.data: break
        
        all_data_magasin.extend(response.data)
        
        if len(response.data) < page_size: break
        
        offset += page_size

    return(pd.DataFrame(all_data_magasin))

## Fontion page 1
def separation_intrant_carte(intrant):
    """
    Separe chaque ligne d'un intrant text sous la forme 'Quantite' 'Nom de la carte'. EXEMPLE : 1 Sol ring"
    Rend un dataframe avec 2 colonnes : nom_carte, quantite
    """
    lignes_intrant = intrant.strip().split("\n")
    list_cartes = []

    for ligne in lignes_intrant :
        ligne = ligne.strip()
        if not ligne :
            continue
        
        separation = re.match(r"^(\d+)\s+(.+)$", ligne)

        if separation :
            quantite = int(separation.group(1))
            nom_carte = separation.group(2).strip().lower()
            list_cartes.append({"nom_carte": nom_carte,
                                "quantite": quantite})
    
    if(len(list_cartes) <= 0): return(pd.DataFrame(columns=['nom_carte', 'quantite']))

    return(pd.DataFrame(list_cartes))

# APP --------------------------------------------------------------------------------------------------------------

st.set_page_config(
    page_title="Optimisation",
    page_icon="✅",
    layout="wide"
)

list_of_basic_lands = ["plains", "island", "swamp", "mountain", "forest", "wastes"]

## VARIABLE GLOBAL
url: str = st.secrets["supabase"]["SUPABASE_URL"]
key: str  = st.secrets["supabase"]["SUPABASE_KEY"]
supabase = create_client(url, key)

## Initialiser les données
if 'list_magasins_ouverts' not in st.session_state:
    st.session_state.list_magasins_ouverts = ["Valet de Coeur", "Expedition", "Alt F4"]
if 'list_magasins_fermes' not in st.session_state:
    st.session_state.list_magasins_fermes = []

st.title("Optimisation")

st.divider()

st.header("Liste de cartes :")

st.markdown(
"""
Entrez la liste de cartes a chercher ci-dessous :
""")

## Debut App
text_cartes_brut = st.text_area(
    label = "Liste de cartes Magic :",
    label_visibility= "hidden",
    value = "",
    placeholder = "Copier coller la quantite et le noms des cartes sous ce format :\n1 sol ring\n1 arcane signet\n...")

st.divider()

st.header("Filtrer par magasin :")

st.markdown(
"""
Ci dessous vous avez une liste de magasin avec des boites a cocher. 

Vous pouvez selectionner un magasin en chochant la boite a cote de son nom. 

Puis vous pouvez faire l'action indiquer par les 3 boutons ci dessous aux magasins selectionnes.
""")

st.warning("⚠️ L'ordre des magasins a de l'importance. En cas de prix egale, le magasin le plus haut dans la liste sera priorise par rapport aux autres magasins.")

col1, col2, col3 = st.columns([2, 1, 2])

with col1:
    st.subheader("Magasins Ouverts :")
    magasins_a_fermer = []
    for i, item in enumerate(st.session_state.list_magasins_ouverts):
        if st.checkbox(f"{item}", key=f"id_magasin_a_fermer_{i}"):
            magasins_a_fermer.append(item)

with col3:
    st.subheader("Magasins Fermes :")
    magasins_a_ouvrir = []
    for i, item in enumerate(st.session_state.list_magasins_fermes):
        if st.checkbox(f"{item}", key=f"id_magasin_a_ouvrir_{i}"):
            magasins_a_ouvrir.append(item)

with col2:
    st.write("") # Espace
    st.write("") # Espace
    st.write("") # Espace
    
    if st.button("Fermer les magasins"):
        for item in magasins_a_fermer:
            st.session_state.list_magasins_ouverts.remove(item)
            st.session_state.list_magasins_fermes.append(item)
        st.rerun()
    
    if st.button("Ouvrir les magasins"):
        for item in magasins_a_ouvrir:
            st.session_state.list_magasins_fermes.remove(item)
            st.session_state.list_magasins_ouverts.append(item)
        st.rerun()

    if st.button("Prioriser le magasin"):
        for item in magasins_a_fermer:
            position_magasin = st.session_state.list_magasins_ouverts.index(item)
            if position_magasin:
                st.session_state.list_magasins_ouverts.remove(item)
                st.session_state.list_magasins_ouverts.insert(position_magasin-1, item)
        st.rerun()

st.divider()

st.header("Trouver les meilleurs prix :")

st.markdown(
"""
Tout est pret ? Cliquer sur le bouton ci dessous !

En cas de besoin, vous pourrez toujours modifier les paramettres ci-dessus pourlancer une nouvelle recherche.
""")

if st.button("Lancer une recherche de prix"):

    df_all_data = get_all_databases(supabase)

    df_cartes_intrant = separation_intrant_carte(text_cartes_brut)
    df_trouvailles = get_prices_in_stores(df_cartes_intrant, st.session_state.list_magasins_ouverts, df_all_data, list_of_basic_lands)

    nb_cartes_non_trouvees = df_trouvailles[df_trouvailles["nom_magasin"] == "Indisponible"]["stock_carte"].sum()
    st.write("Nombre de cartes trouvees : ", df_trouvailles["stock_carte"].sum()-nb_cartes_non_trouvees, "/", df_trouvailles["stock_carte"].sum(), ", Prix total : ", round((df_trouvailles["prix_carte"]*df_trouvailles["stock_carte"]).sum(), 2), "$")

    df_trouvailles["info_carte"] = df_trouvailles["langue_carte"] + ", " + df_trouvailles["etat_carte"]
    df_trouvailles["id"] = range(1, len(df_trouvailles)+1)
    df_trouvailles = df_trouvailles[["id",
                                     "nom_carte",
                                    "prix_carte",
                                    "info_carte",
                                    "stock_carte",
                                    "lien_carte",
                                    "page_magasin",
                                    "date_recherche",
                                    "nom_magasin"]]

    if len(st.session_state.list_magasins_ouverts) >= 1:
        df_a_afficher = df_trouvailles[df_trouvailles["nom_magasin"] == st.session_state.list_magasins_ouverts[0]].drop(columns=["nom_magasin"])
        df_a_afficher["id"] = range(1, len(df_a_afficher)+1)

        st.write(st.session_state.list_magasins_ouverts[0], ": (", df_a_afficher["stock_carte"].sum(), "cartes a ", round((df_a_afficher["prix_carte"]*df_a_afficher["stock_carte"]).sum(), 2), "$)")
        st.dataframe(df_a_afficher, hide_index= True, use_container_width=True)

    if len(st.session_state.list_magasins_ouverts) >= 2:
        df_a_afficher = df_trouvailles[df_trouvailles["nom_magasin"] == st.session_state.list_magasins_ouverts[1]].drop(columns=["nom_magasin"])
        df_a_afficher["id"] = range(1, len(df_a_afficher)+1)

        st.write(st.session_state.list_magasins_ouverts[1], ": (", df_a_afficher["stock_carte"].sum(), "cartes a ", round((df_a_afficher["prix_carte"]*df_a_afficher["stock_carte"]).sum(), 2), "$)")
        st.dataframe(df_a_afficher, hide_index= True, use_container_width=True)

    if len(st.session_state.list_magasins_ouverts) >= 3:
        df_a_afficher = df_trouvailles[df_trouvailles["nom_magasin"] == st.session_state.list_magasins_ouverts[2]].drop(columns=["nom_magasin"])
        df_a_afficher["id"] = range(1, len(df_a_afficher)+1)

        st.write(st.session_state.list_magasins_ouverts[2], ": (", df_a_afficher["stock_carte"].sum(), "cartes a ", round((df_a_afficher["prix_carte"]*df_a_afficher["stock_carte"]).sum(), 2), "$)")
        st.dataframe(df_a_afficher, hide_index= True, use_container_width=True)

    df_a_afficher = df_trouvailles[df_trouvailles["nom_magasin"] == "lands"].drop(columns=["nom_magasin"])
    df_a_afficher["id"] = range(1, len(df_a_afficher)+1)

    st.write("Basic lands : (", df_a_afficher["stock_carte"].sum(), " lands a ", round((df_a_afficher["prix_carte"]*df_a_afficher["stock_carte"]).sum(), 2), "$)")
    st.dataframe(df_a_afficher, hide_index= True, use_container_width=True)

    df_a_afficher = df_trouvailles[df_trouvailles["nom_magasin"] == "Indisponible"].drop(columns=["nom_magasin"])
    df_a_afficher["id"] = range(1, len(df_a_afficher)+1)

    st.write("Cartes non trouvees : ", df_a_afficher["stock_carte"].sum())
    st.dataframe(df_a_afficher, hide_index= True, use_container_width=True)

st.caption("© 2025 - MTG Card Finder Montreal")