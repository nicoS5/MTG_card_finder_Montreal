import streamlit as st
import pandas as pd
import re
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from supabase import create_client

# Functions ---------------------------------------------------------------------------------------------------------------------
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
def Is_other_named_card(card_store_name: str, card_name: str):
    Bad_card_name: bool = card_store_name.find(card_name) < 0

    return Bad_card_name
def creat_empty_df_resultat_magasin(nb_ligne, nom_magasin = ""):
    df_resultat_magasin = pd.DataFrame({
        "nom_carte": [""] * nb_ligne,
        "prix_carte": [None] * nb_ligne,  
        "langue_carte": [""] * nb_ligne,
        "etat_carte": [""] * nb_ligne,
        "stock_carte": [None] * nb_ligne,
        "date_recherche": [""] * nb_ligne,
        "page_magasin": [None] * nb_ligne,
        "lien_carte": [""] * nb_ligne,
        "nom_magasin": [nom_magasin] * nb_ligne
    })

    return(df_resultat_magasin)
def get_VdC_url(nom_carte: str, compteur_page: int = 1):
    nom_carte_pour_url = nom_carte.replace(" ", "+").replace("'", "%27")
    if compteur_page <= 1 :
        url_site: str = "https://www.carte.levalet.com/products/search?q=" + nom_carte_pour_url + "&c=1" # Voir pour la recherche avance sur le site 
    else :
        url_site: str = "https://www.carte.levalet.com/products/search?c=1&page=" + str(compteur_page) + "&q=" + nom_carte_pour_url

    return(url_site)
def get_Expedition_url(nom_carte: str, compteur_page: int = 1):
    nom_carte_pour_url = nom_carte.replace(" ", "+").replace("'", "%27")
    if compteur_page <= 1 :
        url_site: str = "https://www.expeditionjeux.com/products/search?q=" + nom_carte_pour_url + "&c=1" # Voir pour la recherche avance sur le site 
    else :
        url_site: str = "https://www.expeditionjeux.com/products/search?c=1&page=" + str(compteur_page) + "&q="+ nom_carte_pour_url

    return(url_site)
def get_alt_f4_ulr(nom_carte: str):
    nom_carte_pour_url: str = nom_carte.replace(" ", "+").replace("'", "%27")
    url_site: str = "https://altf4online.com/search?q=" + nom_carte_pour_url + "&sort_by=relevance&filter.v.availability=1&filter.p.product_type=MTG+Single"

    return(url_site)    
def update_df_resultat_magasin(df_resultat_magasin, ligne, nom_carte, prix_carte, langue_carte, etat_carte, stock_carte, date_recherche, page_magasin, lien_carte):

    df_resultat_magasin.loc[ligne, "nom_carte"] = nom_carte                
    df_resultat_magasin.loc[ligne, "prix_carte"] = prix_carte
    df_resultat_magasin.loc[ligne, "langue_carte"] = langue_carte
    df_resultat_magasin.loc[ligne, "etat_carte"] = etat_carte
    df_resultat_magasin.loc[ligne, "stock_carte"] = stock_carte
    df_resultat_magasin.loc[ligne, "date_recherche"] = date_recherche
    df_resultat_magasin.loc[ligne, "page_magasin"] = page_magasin
    df_resultat_magasin.loc[ligne, "lien_carte"] = lien_carte

    return(df_resultat_magasin)
def get_prix_du_valet_de_coeur(df_cartes_intrant, message_mag_placerholder, progress_placeholder, message_magasin, list_of_basic_lands):
    df_resultat_magasin_total = creat_empty_df_resultat_magasin(0)

    for index_df, carte in enumerate(df_cartes_intrant.itertuples()): # Boucle sur toutes les cartes dans le magasin

        ui_progression_scrapping(message_mag_placerholder, progress_placeholder, message_magasin, df_cartes_intrant, carte, index_df)

        if carte.nom_carte in list_of_basic_lands: continue 

        df_resultat_magasin = creat_empty_df_resultat_magasin(100, nom_magasin= "Valet de Coeur") # Creation d'un df vide pour toutes 100 instances de la meme carte dans le magasin

        # Boucle pour aller voir les 3 premieres pages du magasin si necessaire pour la carte
        Go_to_next_page: bool = True
        compteur_page: int = 1
        compteur_instance_carte: int = 0
        while Go_to_next_page:

            # Obtention de l'URL pour la carte
            url_site: str = get_VdC_url(carte.nom_carte, compteur_page=compteur_page)

            # print(carte.nom_carte, "-> page", compteur_page)
            page_site: requests = requests.get(url_site)
            soup_site: BeautifulSoup = BeautifulSoup(page_site.text, features="lxml")

            match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now()))
            date_recherche = match_pour_date_recherche.group(1) if match_pour_date_recherche else None

            soup_card_container: BeautifulSoup = soup_site.find("ul", class_="products")
            if soup_card_container == None: break

            soup_all_cards: list[BeautifulSoup] = soup_card_container.find_all("li") 

            for i_carte_magazin in range(len(soup_all_cards)):

                if compteur_instance_carte >= 100 : 
                    Go_to_next_page = False
                    break

                soup_card_info: BeautifulSoup = soup_all_cards[i_carte_magazin].find("div", class_="image")
                
                match_pour_nom_carte = re.search(r'title="([^"]*)"', str(soup_card_info))
                nom_carte = match_pour_nom_carte.group(1).lower() if match_pour_nom_carte else None

                Bad_card_name: bool = Is_other_named_card(nom_carte, carte.nom_carte)
                if Bad_card_name:
                    Go_to_next_page: bool = False
                    continue

                match_pour_lien_carte = re.search(r'href="([^"]*)"', str(soup_card_info))
                lien_carte = "https://www.carte.levalet.com" + match_pour_lien_carte.group(1) if match_pour_lien_carte else None
            
                soup_card_info: BeautifulSoup = soup_all_cards[i_carte_magazin].find_all("div", class_="variant-row row")

                if (len(soup_card_info) <= 0) :
                    
                    df_resultat_magasin = update_df_resultat_magasin(df_resultat_magasin, ligne= compteur_instance_carte, 
                                                                    nom_carte= nom_carte, prix_carte= 999999.99, 
                                                                    langue_carte= "OoS", etat_carte= "OoS", 
                                                                    stock_carte= 0, date_recherche= date_recherche,
                                                                    page_magasin= compteur_page, lien_carte= lien_carte) 

                    compteur_instance_carte += 1
                
                else :
                    for j_carte_version in range(len(soup_card_info)):

                        etat_et_langue_carte: str = str(soup_card_info[j_carte_version].find("span", class_="variant-main-info"))

                        match_pour_etat_et_langue_carte = re.search(r'class="variant-short-info variant-description">([^,<]+),\s*([^,<]+)<', etat_et_langue_carte)
                        etat_carte = match_pour_etat_et_langue_carte.group(1) if match_pour_etat_et_langue_carte else None
                        langue_carte = match_pour_etat_et_langue_carte.group(2) if match_pour_etat_et_langue_carte else None

                        match_pour_stock_carte = re.search(r'class="variant-short-info variant-qty">([0-9]+)\s', etat_et_langue_carte)
                        stock_carte = int(match_pour_stock_carte.group(1)) if match_pour_stock_carte else None

                        card_info: str = str(soup_card_info[j_carte_version].find("form", class_="add-to-cart-form"))

                        match_pour_prix = re.search(r'data-price="[^$]*\$\s*([0-9.]+)"', card_info)
                        prix_carte = float(match_pour_prix.group(1)) if match_pour_prix else None

                        df_resultat_magasin = update_df_resultat_magasin(df_resultat_magasin, ligne= compteur_instance_carte, 
                                                                    nom_carte= nom_carte, prix_carte= prix_carte, 
                                                                    langue_carte= langue_carte, etat_carte= etat_carte, 
                                                                    stock_carte= stock_carte, date_recherche= date_recherche,
                                                                    page_magasin= compteur_page, lien_carte= lien_carte) 

                        compteur_instance_carte += 1
                        if compteur_instance_carte >= 100 : break
            
            if Go_to_next_page: # Si la page est rempli de differente version de la carte en stock, alors on va voir la page suivante

                compteur_page += 1
                if compteur_page >= 4: break # On va voir maximum la 3e page, au dela on arrete

                url_site: str = get_VdC_url(carte.nom_carte, compteur_page=compteur_page)

        df_resultat_magasin = df_resultat_magasin[df_resultat_magasin["nom_carte"] != ""] 
        df_resultat_magasin_total = pd.concat([df_resultat_magasin_total, df_resultat_magasin], ignore_index=True)
        
    return(df_resultat_magasin_total)
def get_prix_de_l_expedition(df_cartes_intrant, message_mag_placerholder, progress_placeholder, message_magasin, list_of_basic_lands):
    df_resultat_magasin_total = creat_empty_df_resultat_magasin(0)

    for index_df, carte in enumerate(df_cartes_intrant.itertuples()): # Boucle sur toutes les cartes dans le magasin

        ui_progression_scrapping(message_mag_placerholder, progress_placeholder, message_magasin, df_cartes_intrant, carte, index_df)

        if carte.nom_carte in list_of_basic_lands: continue 

        df_resultat_magasin = creat_empty_df_resultat_magasin(100, nom_magasin= "Expedition") # Creation d'un df vide pour toutes 100 instances de la meme carte dans le magasin

        # Boucle pour aller voir les 3 premieres pages du magasin si necessaire pour la carte
        Go_to_next_page: bool = True
        compteur_page: int = 1
        compteur_instance_carte: int = 0
        while Go_to_next_page:

            # Obtention de l'URL pour la carte
            url_site: str = get_Expedition_url(carte.nom_carte, compteur_page=compteur_page)
            
            # print(carte.nom_carte, "-> page", compteur_page)
            page_site: requests = requests.get(url_site)
            soup_site: BeautifulSoup = BeautifulSoup(page_site.text, features="lxml")

            match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now()))
            date_recherche = match_pour_date_recherche.group(1) if match_pour_date_recherche else None

            soup_card_container: BeautifulSoup = soup_site.find("ul", class_="products")
            if soup_card_container == None: print(url_site)
            if soup_card_container == None: break

            soup_all_cards: list[BeautifulSoup] = soup_card_container.find_all("li") 

            for i_carte_magazin in range(len(soup_all_cards)):

                if compteur_instance_carte >= 100 : 
                    Go_to_next_page = False
                    break

                soup_card_info: BeautifulSoup = soup_all_cards[i_carte_magazin].find("div", class_="image")
                
                match_pour_nom_carte = re.search(r'title="([^"]*)"', str(soup_card_info))
                nom_carte = match_pour_nom_carte.group(1).lower() if match_pour_nom_carte else None

                Bad_card_name: bool = Is_other_named_card(nom_carte, carte.nom_carte)
                if Bad_card_name:
                    Go_to_next_page: bool = False
                    continue

                match_pour_lien_carte = re.search(r'href="([^"]*)"', str(soup_card_info))
                lien_carte = "https://www.expeditionjeux.com" + match_pour_lien_carte.group(1) if match_pour_lien_carte else None
            
                soup_card_info: BeautifulSoup = soup_all_cards[i_carte_magazin].find_all("div", class_="variant-row row")

                if (len(soup_card_info) <= 0) :
                    
                    df_resultat_magasin = update_df_resultat_magasin(df_resultat_magasin, ligne= compteur_instance_carte, 
                                                                    nom_carte= nom_carte, prix_carte= 999999.99, 
                                                                    langue_carte= "OoS", etat_carte= "OoS", 
                                                                    stock_carte= 0, date_recherche= date_recherche,
                                                                    page_magasin= compteur_page, lien_carte= lien_carte) 

                    compteur_instance_carte += 1
                
                else :
                    for j_carte_version in range(len(soup_card_info)):

                        etat_et_langue_carte: str = str(soup_card_info[j_carte_version].find("span", class_="variant-main-info"))

                        match_pour_etat_et_langue_carte = re.search(r'class="variant-short-info variant-description">([^,<]+),\s*([^,<]+),\s*([^,<]+)<', etat_et_langue_carte)
                        etat_carte = match_pour_etat_et_langue_carte.group(1) if match_pour_etat_et_langue_carte else None
                        langue_carte = match_pour_etat_et_langue_carte.group(2) if match_pour_etat_et_langue_carte else None

                        match_pour_stock_carte = re.search(r'class="variant-short-info variant-qty">\s*([0-9]+)\s*', etat_et_langue_carte)
                        stock_carte = int(match_pour_stock_carte.group(1)) if match_pour_stock_carte else None

                        card_info: str = str(soup_card_info[j_carte_version].find("form", class_="add-to-cart-form"))

                        match_pour_prix = re.search(r'data-price="[^$]*\$\s*([0-9.]+)"', card_info)
                        prix_carte = float(match_pour_prix.group(1)) if match_pour_prix else None

                        df_resultat_magasin = update_df_resultat_magasin(df_resultat_magasin, ligne= compteur_instance_carte, 
                                                                    nom_carte= nom_carte, prix_carte= prix_carte, 
                                                                    langue_carte= langue_carte, etat_carte= etat_carte, 
                                                                    stock_carte= stock_carte, date_recherche= date_recherche,
                                                                    page_magasin= compteur_page, lien_carte= lien_carte) 

                        compteur_instance_carte += 1
                        if compteur_instance_carte >= 100 : break

            
            if Go_to_next_page: # Si la page est rempli de differente version de la carte en stock, alors on va voir la page suivante

                compteur_page += 1
                if compteur_page >= 4: break # On va voir maximum la 3e page, au dela on arrete

                url_site: str = get_Expedition_url(carte.nom_carte, compteur_page=compteur_page)

        df_resultat_magasin = df_resultat_magasin[df_resultat_magasin["nom_carte"] != ""] 
        df_resultat_magasin_total = pd.concat([df_resultat_magasin_total, df_resultat_magasin], ignore_index=True)

    return(df_resultat_magasin_total)
def get_prix_alt_f4(df_cartes_intrant, message_mag_placerholder, progress_placeholder, message_magasin, list_of_basic_lands):
    df_resultat_magasin_total = creat_empty_df_resultat_magasin(0)

    for index_df, carte in enumerate(df_cartes_intrant.itertuples()): # Boucle sur toutes les cartes dans le a chercher

        ui_progression_scrapping(message_mag_placerholder, progress_placeholder, message_magasin, df_cartes_intrant, carte, index_df)

        if carte.nom_carte in list_of_basic_lands: continue 

        df_resultat_magasin = creat_empty_df_resultat_magasin(100, nom_magasin= "Alt F4") # Creation d'un df vide pour toutes 100 instances de la meme carte dans le magasin

        compteur_page: int = 1
        compteur_instance_carte: int = 0
            
        # Obtention de l'URL pour la carte
        url_site: str = get_alt_f4_ulr(carte.nom_carte)
        
        # print(carte.nom_carte, "-> page", compteur_page)
        page_site: requests = requests.get(url_site)
        soup_site: BeautifulSoup = BeautifulSoup(page_site.text, features="lxml")
        soup_all_cards: list[BeautifulSoup] = soup_site.find_all("div", class_="product-card__content grow flex flex-col justify-start text-center")

        match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now()))
        date_recherche = match_pour_date_recherche.group(1) if match_pour_date_recherche else None

        for i in range(len(soup_all_cards)):

            card_info: BeautifulSoup = soup_all_cards[i]
            card_name_info: str = str(card_info.find("a", class_="product-card__title reversed-link text-base-xl font-medium leading-tight"))

            match_pour_lien_carte = re.search(r'<a[^>]*>(.*?)</a>', card_name_info)
            nom_carte = match_pour_lien_carte.group(1).lower() if match_pour_lien_carte else None

            Bad_card_name: bool = Is_other_named_card(nom_carte, carte.nom_carte)
            if Bad_card_name:
                continue

            match_pour_lien_carte = re.search(r'href="([^"]*)"', card_name_info)
            lien_carte = "https://altf4online.com" + match_pour_lien_carte.group(1) if match_pour_lien_carte else None

            card_price_info: str = str(card_info.find("div", class_="price flex flex-wrap lg:flex-col lg:items-end gap-2 md:gap-1d5"))

            match_pour_lien_carte = re.search(r'<span[^>]*>\$(.*?)</span>', card_price_info)
            prix_carte = float(match_pour_lien_carte.group(1)) if match_pour_lien_carte else None

            df_resultat_magasin = update_df_resultat_magasin(df_resultat_magasin, ligne= compteur_instance_carte, 
                                                                    nom_carte= nom_carte, prix_carte= prix_carte, 
                                                                    langue_carte= "Indisponible", etat_carte= "Indisponible", 
                                                                    stock_carte= 1, date_recherche= date_recherche,
                                                                    page_magasin= compteur_page, lien_carte= lien_carte) 
            
            compteur_instance_carte += 1
            if compteur_instance_carte >= 100 : break

        df_resultat_magasin = df_resultat_magasin[df_resultat_magasin["nom_carte"] != ""] 
        df_resultat_magasin_total = pd.concat([df_resultat_magasin_total, df_resultat_magasin], ignore_index=True)

    return(df_resultat_magasin_total)
def sauvegarder_donnees_magasin(url, key, df_cartes_intrant, nouvelle_data, nom_table):

    for index_df, carte in enumerate(df_cartes_intrant.itertuples()):

        nouvelle_data_carte = nouvelle_data[nouvelle_data["nom_carte"].apply(lambda x: not(Is_other_named_card(x, carte.nom_carte)))]

        if len(nouvelle_data_carte):

            supabase = create_client(url, key)
            response = supabase.table(nom_table).select('id_carte, nom_carte').execute()
            data_en_ligne = pd.DataFrame(response.data)
            data_en_ligne = data_en_ligne[data_en_ligne["nom_carte"].apply(lambda x: not(Is_other_named_card(x, carte.nom_carte)))]
            data_to_delete = data_en_ligne["id_carte"].to_list()

            batch_size = 100    
            for i in range(0, len(data_to_delete), batch_size):

                batch_ids = data_to_delete[i:i + batch_size]
                supabase.table(nom_table).delete().in_('id_carte', batch_ids).execute()

            nouvelle_data_carte = nouvelle_data_carte.to_dict("records")
            supabase.table(nom_table).insert(nouvelle_data_carte).execute()
def ui_progression_scrapping(message_mag_placerholder, progress_placeholder, message_magasin, df, row, index):
    with message_mag_placerholder.container():
        st.write(message_magasin)
        # Mise à jour de l'affichage
    with progress_placeholder.container():
        st.write(f"**{row.nom_carte} ({index + 1} / {len(df)})**")
        st.progress((index + 1) / len(df))


# APP ---------------------------------------------------------------------------------------------------------------------------

st.set_page_config(
    page_title="Imporation",
    page_icon="ℹ️",
    layout="wide"
)

list_of_basic_lands = ["plains", "island", "swamp", "mountain", "forest", "wastes"]

st.title("Importation")

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

st.header("Verification de la liste :")

st.markdown(
"""
Verifiez grace a ce bouton que toutes les cartes ont bien ete entrees :
""")

if st.button("Verification de la liste de cartes"):

    st.write("La liste de cartes :") 
    df_cartes_intrant = separation_intrant_carte(text_cartes_brut)
    st.dataframe(df_cartes_intrant)

st.divider()

st.header("Lancer la recherche :")

st.markdown(
"""
Si tout est bon, c'est parti pour la recherche des cartes :
""")

# Lancement de la recherche de prix dans les magasins
if st.button("Lancer la recherche !"):

    url: str = st.secrets["supabase"]["SUPABASE_URL"]
    key: str  = st.secrets["supabase"]["SUPABASE_KEY"]

    message_mag_placerholder = st.empty()
    progress_placeholder = st.empty()

    df_cartes_intrant = separation_intrant_carte(text_cartes_brut)

    df_resultat_magasin_total = get_prix_du_valet_de_coeur(df_cartes_intrant, message_mag_placerholder, progress_placeholder, "Visite du Valet de Coeur :", list_of_basic_lands)
    progress_placeholder.info("🔄 Sauvegarde des trouvailles...")
    sauvegarder_donnees_magasin(url, key, df_cartes_intrant, df_resultat_magasin_total, "inventaire_VdC")

    df_resultat_magasin_total = get_prix_de_l_expedition(df_cartes_intrant, message_mag_placerholder, progress_placeholder, "Visite de l'Expedition :", list_of_basic_lands)
    progress_placeholder.info("🔄 Sauvegarde des trouvailles...")
    sauvegarder_donnees_magasin(url, key, df_cartes_intrant, df_resultat_magasin_total, "inventaire_Expedition")

    df_resultat_magasin_total = get_prix_alt_f4(df_cartes_intrant, message_mag_placerholder, progress_placeholder, "Visite de Alt F4 :", list_of_basic_lands)
    progress_placeholder.info("🔄 Sauvegarde des trouvailles...")
    sauvegarder_donnees_magasin(url, key, df_cartes_intrant, df_resultat_magasin_total, "inventaire_Alt_F4")

    message_mag_placerholder.empty()
    progress_placeholder.success("✅ Algorithme terminé !")

st.caption("© 2025 - MTG Card Finder Montreal")