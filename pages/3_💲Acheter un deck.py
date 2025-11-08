import streamlit as st
import pandas as pd
import re
from supabase import create_client
from unidecode import unidecode

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
                            get_all_data_from_magasin(supabase, "inventaire_Alt_F4"),
                            get_all_data_from_magasin(supabase, "inventaire_Chez_Geeks"),
                            get_all_data_from_magasin(supabase, "inventaire_GK_Lajeunesse"),
                            get_all_data_from_magasin(supabase, "inventaire_Carta_Magica")],
                            ignore_index= True)
    df_all_data = df_all_data[df_all_data["etat_carte"] != "OoS"]

    return(df_all_data)
def filtrer_les_cartes_par_quantite(df_carte, carte):
    if len(df_carte) > 0:

        somme_cumulative = df_carte['stock_carte'].cumsum()
        total_carte_disponible = df_carte['stock_carte'].sum()

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
            if quantite < 0:
                quantite = -1

            nom_carte = unidecode(separation.group(2).strip().lower())

            list_cartes.append({"nom_carte": nom_carte,
                                "quantite": quantite})
        
        else :
            quantite = -1
            nom_carte = ligne
            list_cartes.append({"nom_carte": nom_carte,
                                "quantite": quantite})
    
    if(len(list_cartes) <= 0): return(pd.DataFrame(columns=['nom_carte', 'quantite']))

    return(pd.DataFrame(list_cartes).sort_values(["nom_carte"], ascending= [True]))

# APP --------------------------------------------------------------------------------------------------------------

st.set_page_config(
    page_title="Acheter un deck",
    page_icon="💲",
    layout="wide"
)

list_of_basic_lands = ["plains", "island", "swamp", "mountain", "forest", "wastes"]
list_de_magasins = ["Alt F4", "Expedition", "Carta Magica", "GK Lajeunesse", "Valet de Coeur", "Chez Geeks"]

## VARIABLE GLOBAL
url: str = st.secrets["supabase"]["SUPABASE_URL"]
key: str  = st.secrets["supabase"]["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("💲Acheter un deck")

st.divider()

st.header("Liste de cartes :")

st.markdown(
"""
Entrez la liste de cartes a chercher ci-dessous :
""")

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
Vous pouvez fermer un magasin en chochant la boite a cote de son nom. 
Le magasin sera exclu de l'optimisation des prix. 
Vous pouvez aussi changer la priorite des magasins en modifiant le nombre sur la droite. 
Les magasin seront evalue dans le sens croissant des priorites (1 -> 2 -> 3 -> ...).
""")

st.warning("⚠️ L'ordre des magasins peut avoir de l'importance. En cas de prix egale, le magasin le plus haut dans la liste sera priorise par rapport aux autres magasins.")

df_resultat_magasin = pd.DataFrame({
        "magasin": list_de_magasins,
        "est_ouvert": [True] * len(list_de_magasins),  
        "priorite": list(range(1, len(list_de_magasins)+1))
    })
df_resultat_magasin.index = df_resultat_magasin.index + 1

with st.form(key= "validation_magasin_optimisation"):
    df_resultat_magasin = st.data_editor(df_resultat_magasin, 
                column_config={
                        "magasin": st.column_config.Column(
                            "magasin",
                            disabled=True  # Cette colonne ne sera pas modifiable
                        )
                },
                width='stretch')
        
    lancer_optimisation_cartes = st.form_submit_button("Lancer une recherche de prix")

st.divider()

st.header("Trouver les meilleurs prix :")

st.markdown(
"""
Tout est pret ? Cliquer sur le bouton ci dessous !

En cas de besoin, vous pourrez toujours modifier les paramettres ci-dessus pourlancer une nouvelle recherche.
""")

if lancer_optimisation_cartes:

    list_magasins_ouverts = df_resultat_magasin[df_resultat_magasin['est_ouvert']].sort_values(by='priorite')['magasin'].tolist()
    
    df_all_data = get_all_databases(supabase)

    df_cartes_intrant = separation_intrant_carte(text_cartes_brut)
    df_trouvailles = get_prices_in_stores(df_cartes_intrant, list_magasins_ouverts, df_all_data, list_of_basic_lands)

    nb_cartes_non_trouvees_total = df_trouvailles[df_trouvailles["nom_magasin"] == "Indisponible"]["stock_carte"].sum()
    prix_deck_total = (df_trouvailles["prix_carte"]*df_trouvailles["stock_carte"]).sum()
    st.write("Nombre de cartes trouvees : ", df_trouvailles["stock_carte"].sum()-nb_cartes_non_trouvees_total, "/", df_trouvailles["stock_carte"].sum(), 
             ", Prix total : ", round(prix_deck_total, 2), "$ (+", round(prix_deck_total*0.15, 2), "tx)")

    df_top_5_cartes_chers = df_trouvailles.sort_values(["prix_carte"], ascending=[False]).head(5)
    prix_top_5_cartes_chers = (df_top_5_cartes_chers["prix_carte"]*df_top_5_cartes_chers["stock_carte"]).sum()
    df_top_5_cartes_chers = df_top_5_cartes_chers.drop(columns=["id_carte", "priorite_mag"])
    df_top_5_cartes_chers = df_top_5_cartes_chers.reset_index(drop=True)
    df_top_5_cartes_chers.index = df_top_5_cartes_chers.index + 1

    st.write("Les 5 cartes les plus cher vous coutent", round(prix_top_5_cartes_chers, 2), "$, soit", round(100*prix_top_5_cartes_chers/prix_deck_total, 1), "% du prix total.")
    st.dataframe(df_top_5_cartes_chers, 
                 column_config={
                     "lien_carte": st.column_config.LinkColumn( 
                         help = "Cliquez pour ouvrir le site", 
                         display_text = "Acheter" 
                         )},
                 width='stretch')

    df_matrice_fermeture_magasin = pd.DataFrame(index=list_magasins_ouverts, columns=list_magasins_ouverts)
    for i in range(len(list_magasins_ouverts)):
        for j in range(i, len(list_magasins_ouverts)):

            if(i == j): list_magasin_reduit = [x for x in list_magasins_ouverts if x != list_magasins_ouverts[i]]
            else : list_magasin_reduit = [x for x in list_magasins_ouverts if x != list_magasins_ouverts[i] and x != list_magasins_ouverts[j]]

            if (len(list_magasin_reduit) <= 0):
                continue

            df_trouvailles_fermeture = get_prices_in_stores(df_cartes_intrant, list_magasin_reduit, df_all_data, list_of_basic_lands)
            nb_cartes_perdu = df_trouvailles_fermeture[df_trouvailles_fermeture["nom_magasin"] == "Indisponible"]["stock_carte"].sum() - nb_cartes_non_trouvees_total
            prix_fermeture_magasins = round((df_trouvailles_fermeture["prix_carte"]*df_trouvailles_fermeture["stock_carte"]).sum() - prix_deck_total, 2) 

            if nb_cartes_perdu > 0: message_matrice = f"{prix_fermeture_magasins}$ ({nb_cartes_perdu} cartes perdues)"
            else: message_matrice = f"{prix_fermeture_magasins}$"
            df_matrice_fermeture_magasin.at[list_magasins_ouverts[j], list_magasins_ouverts[i]] = message_matrice

    st.write("Ci-dessous un tableau montrant de combien le prix du deck augmenterait si on decidait de ne pas visiter un magasin :")
    st.dataframe(df_matrice_fermeture_magasin, width='stretch')

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
    
    st.write("Cartes a acheter et magasins a visiter :")

    for i in range(len(list_magasins_ouverts)):
        df_a_afficher = df_trouvailles[df_trouvailles["nom_magasin"] == list_magasins_ouverts[i]].drop(columns=["nom_magasin", "id"])
        df_a_afficher = df_a_afficher.reset_index(drop=True)
        df_a_afficher.index = df_a_afficher.index + 1

        st.write(list_magasins_ouverts[i], ": (", df_a_afficher["stock_carte"].sum(), "cartes a ", round((df_a_afficher["prix_carte"]*df_a_afficher["stock_carte"]).sum(), 2), "$)")
        st.dataframe(df_a_afficher, 
                 column_config={
                     "lien_carte": st.column_config.LinkColumn(
                         help = "Cliquez pour ouvrir le site", # aide quand on survole la case
                         display_text = "Acheter"  # Texte affiché au lieu de l'URL complète
                         )},
                 width='stretch')
        
    df_a_afficher = df_trouvailles[df_trouvailles["nom_magasin"] == "lands"].drop(columns=["nom_magasin", "id"])
    df_a_afficher = df_a_afficher.reset_index(drop=True)
    df_a_afficher.index = df_a_afficher.index + 1

    st.write("Basic lands : (", df_a_afficher["stock_carte"].sum(), " lands a ", round((df_a_afficher["prix_carte"]*df_a_afficher["stock_carte"]).sum(), 2), "$)")
    st.dataframe(df_a_afficher, width='stretch')

    df_a_afficher = df_trouvailles[df_trouvailles["nom_magasin"] == "Indisponible"].drop(columns=["nom_magasin", "id"])
    df_a_afficher = df_a_afficher.reset_index(drop=True)
    df_a_afficher.index = df_a_afficher.index + 1

    st.write("Cartes non trouvees : ", df_a_afficher["stock_carte"].sum())
    st.dataframe(df_a_afficher, width='stretch')

st.caption("© 2025 - MTG Card Finder Montreal")