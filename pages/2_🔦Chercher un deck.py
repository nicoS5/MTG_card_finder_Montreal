import streamlit as st
import pandas as pd
import re
import math 
import time
import requests
import pytz
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from unidecode import unidecode

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
def Is_other_named_card(card_store_name: str, card_name: str):

    Bad_card_name: bool = card_store_name.find(card_name) < 0
    Bad_card_name: bool = Bad_card_name or card_store_name.find("art card") >= 0
    Bad_card_name: bool = Bad_card_name or card_store_name.find("double-sided token") >= 0
    # Bad_card_name: bool = Bad_card_name or card_store_name.find("display commander - thick stock") >= 0
    # Bad_card_name: bool = Bad_card_name or card_store_name[2:3] == "/"

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
def sauvegarder_donnees_magasin(supabase, df_cartes_intrant, nouvelle_data, nom_table):

    for index_df, carte in enumerate(df_cartes_intrant.itertuples()):

        all_data_magasin = []
        page_size = 1000
        offset = 0

        while True:
            response = supabase.table(nom_table).select('id_carte, nom_carte').range(offset, offset + page_size - 1).execute()
            
            if not response.data: break
            
            all_data_magasin.extend(response.data)
            
            if len(response.data) < page_size: break
            
            offset += page_size

        data_en_ligne = pd.DataFrame(all_data_magasin)
        if data_en_ligne.shape[0] > 0:
            data_en_ligne = data_en_ligne[data_en_ligne["nom_carte"].apply(lambda x: not(Is_other_named_card(x, carte.nom_carte)))]
            data_to_delete = data_en_ligne["id_carte"].to_list()

            batch_size = 100    
            for i in range(0, len(data_to_delete), batch_size):

                batch_ids = data_to_delete[i:i + batch_size]
                supabase.table(nom_table).delete().in_('id_carte', batch_ids).execute()

        nouvelle_data_carte = nouvelle_data[nouvelle_data["nom_carte"].apply(lambda x: not(Is_other_named_card(x, carte.nom_carte)))]

        if len(nouvelle_data_carte):

            nouvelle_data_carte = nouvelle_data_carte.to_dict("records")
            supabase.table(nom_table).insert(nouvelle_data_carte).execute()
def ui_progression_scrapping(message_mag_placerholder, progress_placeholder, message_magasin, df, row, index):
    with message_mag_placerholder.container():
        st.write(message_magasin)
        # Mise à jour de l'affichage
    with progress_placeholder.container():
        st.write(f"**{row.nom_carte} ({index + 1} / {len(df)})**")
        st.progress((index + 1) / len(df))
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
def get_derniere_recherche_carte(df_cartes_intrant, supabase, list_of_basic_lands):
    df_all_data = get_all_databases(supabase)
    date_de_derniere_recherche = []
    for index_carte, carte in enumerate(df_cartes_intrant.itertuples()):

        if carte.nom_carte in list_of_basic_lands:
            date_de_derniere_recherche.append("land")
            continue

        df_carte = df_all_data[df_all_data["nom_carte"].apply(lambda x: not(Is_other_named_card(x, carte.nom_carte)))]

        if df_carte.shape[0] == 0: date_de_derniere_recherche.append("jamais_trouvee")
        else: date_de_derniere_recherche.append(df_carte["date_recherche"].max())

    return(date_de_derniere_recherche)
def mettrer_a_jour_les_cartes_non_trouvee(carte_non_trouve, df_resultat_magasin_total):
    carte_non_trouve_magasin = []
    for index_carte, carte in enumerate(df_cartes_intrant.itertuples()):

        df_carte = df_resultat_magasin_total[df_resultat_magasin_total["nom_carte"].apply(lambda x: not(Is_other_named_card(x, carte.nom_carte)))]

        if df_carte.shape[0] == 0: carte_non_trouve_magasin.append(carte.nom_carte)

    return(carte_non_trouve[carte_non_trouve['nom_carte'].isin(carte_non_trouve_magasin)])
def verifier_la_liste_de_carte(df_cartes_intrant, supabase, afficher_ui = False):

    df_cartes_intrant_non_reconnue = df_cartes_intrant[df_cartes_intrant["quantite"] < 1].sort_values(["quantite", "nom_carte"], ascending= [True, True])
    df_cartes_intrant_non_reconnue = df_cartes_intrant_non_reconnue.reset_index(drop=True)
    df_cartes_intrant_non_reconnue.index = df_cartes_intrant_non_reconnue.index + 1

    df_cartes_intrant_doublon = df_cartes_intrant[df_cartes_intrant.duplicated(subset=['nom_carte'], keep=False)].sort_values(["nom_carte", "quantite"], ascending= [True, True])
    df_cartes_intrant_doublon.index = df_cartes_intrant_doublon.index + 1

    df_cartes_intrant = df_cartes_intrant[df_cartes_intrant["quantite"] >= 1].reset_index(drop=True)
    df_cartes_intrant["derniere_recherche"] = get_derniere_recherche_carte(df_cartes_intrant, supabase, list_of_basic_lands)

    df_cartes_intrant_jamais_trouvee = df_cartes_intrant[df_cartes_intrant["derniere_recherche"] == "jamais_trouvee"].sort_values(["nom_carte"], ascending= [True])
    df_cartes_intrant_jamais_trouvee = df_cartes_intrant_jamais_trouvee.reset_index(drop=True)
    df_cartes_intrant_jamais_trouvee.index = df_cartes_intrant_jamais_trouvee.index + 1

    df_cartes_intrant_lands = df_cartes_intrant[df_cartes_intrant["derniere_recherche"] == "land"].sort_values(["nom_carte"], ascending= [True])
    df_cartes_intrant_lands = df_cartes_intrant_lands.reset_index(drop=True)
    df_cartes_intrant_lands.index = df_cartes_intrant_lands.index + 1

    df_cartes_intrant_deja_trouvee = df_cartes_intrant[~df_cartes_intrant["derniere_recherche"].isin(["jamais_trouvee", "land"])].sort_values(["nom_carte"], ascending= [True])
    df_cartes_intrant_deja_trouvee = df_cartes_intrant_deja_trouvee.reset_index(drop=True)
    df_cartes_intrant_deja_trouvee.index = df_cartes_intrant_deja_trouvee.index + 1

    if afficher_ui:
        if df_cartes_intrant_non_reconnue.shape[0] > 0:
            st.error("❌ Certaines cartes n'ont pas ete reconnues ou seront skiper par l'algo :")
            st.dataframe(df_cartes_intrant_non_reconnue, width='stretch')

        if df_cartes_intrant_doublon.shape[0] > 0:
            st.warning("⚠️ Certaines cartes sont en double dans la liste de carte :")
            st.dataframe(df_cartes_intrant_doublon, width='stretch')

        st.success("✅ Cartes verifiees :")
        st.write("Quantite de carte total dans la liste :", df_cartes_intrant["quantite"].sum(), 
                ". Nombre de carte unique :", df_cartes_intrant.shape[0],
                ". Nombre de carte jamais trouvee :", df_cartes_intrant_jamais_trouvee.shape[0],
                ". Temps estime pour rechercher", df_cartes_intrant.shape[0], "cartes : ", math.ceil(df_cartes_intrant.shape[0]*temps_recherche_carte/60), "min.")

        if df_cartes_intrant_jamais_trouvee.shape[0] > 0:
            st.write("La liste de cartes encore jamais trouvees :") 
            st.dataframe(df_cartes_intrant_jamais_trouvee, width='stretch')

        if df_cartes_intrant_deja_trouvee.shape[0] > 0:
            st.write("La liste de cartes trouvees lors d'anciennes recherches :") 
            st.dataframe(df_cartes_intrant_deja_trouvee, width='stretch')

        if df_cartes_intrant_lands.shape[0] > 0:
            st.write("La liste de basic lands :") 
            st.dataframe(df_cartes_intrant_lands, width='stretch')
def make_session_connection_site():
    session = requests.Session()

    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    return(session)

# fonction pour les magasins ---------------------------------------------------------------------------------------------------
def get_prix_du_valet_de_coeur(df_cartes_intrant, message_mag_placerholder, progress_placeholder, message_magasin, list_of_basic_lands, session):
    
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

            # print(carte.nom_carte, "-> page", compteur_page
            url_site: str = get_VdC_url(carte.nom_carte, compteur_page=compteur_page)

            try:
                # Faire la requête avec la session
                page_site = session.get(url_site, timeout=30)
                page_site.raise_for_status()

                soup_site: BeautifulSoup = BeautifulSoup(page_site.text, features="lxml")

                fuseau_horaire_montreal = pytz.timezone('America/Montreal') 
                match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now(fuseau_horaire_montreal)))
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

                    Is_not_MTG_card = lien_carte.find("magic") < 0
                    if Is_not_MTG_card:
                        Go_to_next_page: bool = False
                        continue
                
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
                                
            except requests.exceptions.RequestException as e:
                print(f"❌ Erreur de requête pour {url_site}: {e}")
                continue

            except Exception as e:
                print(f"❓ Erreur inconnue pour {carte.nom_carte}: {e}")
                continue

        df_resultat_magasin = df_resultat_magasin[df_resultat_magasin["nom_carte"] != ""] 
        df_resultat_magasin_total = pd.concat([df_resultat_magasin_total, df_resultat_magasin], ignore_index=True)

    return(df_resultat_magasin_total)
def get_VdC_url(nom_carte: str, compteur_page: int = 1):
    nom_carte_pour_url = nom_carte.replace(" ", "+").replace("'", "%27")
    if compteur_page <= 1 :
        url_site: str = "https://www.carte.levalet.com/products/search?q=" + nom_carte_pour_url + "&c=1" # Voir pour la recherche avance sur le site 
    else :
        url_site: str = "https://www.carte.levalet.com/products/search?c=1&page=" + str(compteur_page) + "&q=" + nom_carte_pour_url

    return(url_site)

def get_prix_de_l_expedition(df_cartes_intrant, message_mag_placerholder, progress_placeholder, message_magasin, list_of_basic_lands, session):
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

            # print(carte.nom_carte, "-> page", compteur_page)
            url_site: str = get_Expedition_url(carte.nom_carte, compteur_page=compteur_page)
            
            try:
                # Faire la requête avec la session
                page_site = session.get(url_site, timeout=30)
                page_site.raise_for_status()

                soup_site: BeautifulSoup = BeautifulSoup(page_site.text, features="lxml")

                fuseau_horaire_montreal = pytz.timezone('America/Montreal') 
                match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now(fuseau_horaire_montreal)))
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
                    lien_carte = "https://www.expeditionjeux.com" + match_pour_lien_carte.group(1) if match_pour_lien_carte else None

                    Is_not_MTG_card = lien_carte.find("magic") < 0
                    if Is_not_MTG_card:
                        Go_to_next_page: bool = False
                        continue
                
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

            except requests.exceptions.RequestException as e:
                print(f"❌ Erreur de requête pour {url_site}: {e}")
                continue

            except Exception as e:
                print(f"❓ Erreur inconnue pour {carte.nom_carte}: {e}")
                continue

        df_resultat_magasin = df_resultat_magasin[df_resultat_magasin["nom_carte"] != ""] 
        df_resultat_magasin_total = pd.concat([df_resultat_magasin_total, df_resultat_magasin], ignore_index=True)

    return(df_resultat_magasin_total)
def get_Expedition_url(nom_carte: str, compteur_page: int = 1):
    nom_carte_pour_url = nom_carte.replace(" ", "+").replace("'", "%27")
    if compteur_page <= 1 :
        url_site: str = "https://www.expeditionjeux.com/products/search?q=" + nom_carte_pour_url + "&c=1" # Voir pour la recherche avance sur le site 
    else :
        url_site: str = "https://www.expeditionjeux.com/products/search?c=1&page=" + str(compteur_page) + "&q="+ nom_carte_pour_url

    return(url_site)

def get_prix_alt_f4(df_cartes_intrant, message_mag_placerholder, progress_placeholder, message_magasin, list_of_basic_lands, session):
    df_resultat_magasin_total = creat_empty_df_resultat_magasin(0)

    for index_df, carte in enumerate(df_cartes_intrant.itertuples()): # Boucle sur toutes les cartes dans le a chercher

        ui_progression_scrapping(message_mag_placerholder, progress_placeholder, message_magasin, df_cartes_intrant, carte, index_df)

        if carte.nom_carte in list_of_basic_lands: continue 

        df_resultat_magasin = creat_empty_df_resultat_magasin(100, nom_magasin= "Alt F4") # Creation d'un df vide pour toutes 100 instances de la meme carte dans le magasin

        compteur_page: int = 1
        compteur_instance_carte: int = 0
            
        url_site: str = get_alt_f4_ulr(carte.nom_carte)
        
        try:
            # Faire la requête avec la session
            page_site = session.get(url_site, timeout=30)
            page_site.raise_for_status()
            time.sleep(1)

            soup_site: BeautifulSoup = BeautifulSoup(page_site.text, features="lxml")
            soup_all_cards: list[BeautifulSoup] = soup_site.find_all("div", class_="product-card__content grow flex flex-col justify-start text-center")

            fuseau_horaire_montreal = pytz.timezone('America/Montreal') 
            match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now(fuseau_horaire_montreal)))
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

        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur de requête pour {url_site}: {e}")
            continue

        except Exception as e:
            print(f"❓ Erreur inconnue pour {carte.nom_carte}: {e}")
            continue
    
        df_resultat_magasin = df_resultat_magasin[df_resultat_magasin["nom_carte"] != ""] 
        df_resultat_magasin_total = pd.concat([df_resultat_magasin_total, df_resultat_magasin], ignore_index=True)

    return(df_resultat_magasin_total)
def get_alt_f4_ulr(nom_carte: str):
    nom_carte_pour_url: str = nom_carte.replace(" ", "+").replace("'", "%27")
    url_site: str = "https://altf4online.com/search?q=" + nom_carte_pour_url + "&sort_by=relevance&filter.v.availability=1&filter.p.product_type=MTG+Single"

    return(url_site)    

def get_prix_de_games_keeper_lajeunesse(df_cartes_intrant, message_mag_placerholder, progress_placeholder, message_magasin, list_of_basic_lands, session):
    
    df_resultat_magasin_total = creat_empty_df_resultat_magasin(0)

    for index_df, carte in enumerate(df_cartes_intrant.itertuples()): # Boucle sur toutes les cartes dans le magasin

        ui_progression_scrapping(message_mag_placerholder, progress_placeholder, message_magasin, df_cartes_intrant, carte, index_df)

        if carte.nom_carte in list_of_basic_lands: continue 

        df_resultat_magasin = creat_empty_df_resultat_magasin(100, nom_magasin= "GK Lajeunesse") # Creation d'un df vide pour toutes 100 instances de la meme carte dans le magasin

        # Boucle pour aller voir les 3 premieres pages du magasin si necessaire pour la carte
        Go_to_next_page: bool = True
        compteur_page: int = 1
        compteur_instance_carte: int = 0
        while Go_to_next_page:

            # print(carte.nom_carte, "-> page", compteur_page
            url_site: str = get_gk_lajeunesse_url(carte.nom_carte, compteur_page=compteur_page)

            try:
                # Faire la requête avec la session
                page_site = session.get(url_site, timeout=30)
                page_site.raise_for_status()

                soup_site: BeautifulSoup = BeautifulSoup(page_site.text, features="lxml")

                fuseau_horaire_montreal = pytz.timezone('America/Montreal') 
                match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now(fuseau_horaire_montreal)))
                date_recherche = match_pour_date_recherche.group(1) if match_pour_date_recherche else None

                soup_card_container: BeautifulSoup = soup_site.find("ul", class_="products")
                if soup_card_container == None: break

                soup_all_cards: list[BeautifulSoup] = soup_card_container.find_all("li") 

                for i_carte_magazin in range(len(soup_all_cards)):

                    if compteur_instance_carte >= 100 : 
                        Go_to_next_page = False
                        break

                    soup_card_info: BeautifulSoup = soup_all_cards[i_carte_magazin].find("div", class_="meta")
                    
                    match_pour_nom_carte = re.search(r'title="([^"]*)"', str(soup_card_info))
                    nom_carte = match_pour_nom_carte.group(1).lower() if match_pour_nom_carte else None

                    Bad_card_name: bool = Is_other_named_card(nom_carte, carte.nom_carte)
                    if Bad_card_name:
                        Go_to_next_page: bool = False
                        continue

                    match_pour_lien_carte = re.search(r'href="([^"]*)"', str(soup_card_info))
                    lien_carte = "https://www.gamekeeperonline.com" + match_pour_lien_carte.group(1) if match_pour_lien_carte else None

                    Is_not_MTG_card = lien_carte.find("magic") < 0
                    if Is_not_MTG_card:
                        Go_to_next_page: bool = False
                        continue
                
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

                            etat_et_langue_carte: str = str(soup_card_info[j_carte_version].find("span", class_="variant-short-info"))

                            match_pour_etat_et_langue_carte = re.search(r'class="variant-short-info">([^,<]+),\s*([^,<]+),', etat_et_langue_carte)
                            etat_carte = match_pour_etat_et_langue_carte.group(1) if match_pour_etat_et_langue_carte else None
                            langue_carte = match_pour_etat_et_langue_carte.group(2) if match_pour_etat_et_langue_carte else None

                            match_pour_stock_carte = re.search(r'<em>([0-9]+)\s', etat_et_langue_carte)
                            stock_carte = int(match_pour_stock_carte.group(1)) if match_pour_stock_carte else None

                            card_info: str = str(soup_card_info[j_carte_version].find("form", class_="add-to-cart-form"))

                            match_pour_prix = re.search(r'class="regular price">[^$]*\$\s*([0-9.]+)<', card_info)
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

                    url_site: str = get_gk_lajeunesse_url(carte.nom_carte, compteur_page=compteur_page)
                                
            except requests.exceptions.RequestException as e:
                print(f"❌ Erreur de requête pour {url_site}: {e}")
                continue

            except Exception as e:
                print(f"❓ Erreur inconnue pour {carte.nom_carte}: {e}")
                continue

        df_resultat_magasin = df_resultat_magasin[df_resultat_magasin["nom_carte"] != ""] 
        df_resultat_magasin_total = pd.concat([df_resultat_magasin_total, df_resultat_magasin], ignore_index=True)

    return(df_resultat_magasin_total)
def get_gk_lajeunesse_url(nom_carte: str, compteur_page: int = 1):
    nom_carte_pour_url = nom_carte.replace(" ", "+").replace("'", "%27")
    if compteur_page <= 1 :
        url_site: str = "https://www.gamekeeperonline.com/products/search?q=" + nom_carte_pour_url + "&c=1" 
    else :
        url_site: str = "https://www.gamekeeperonline.com/products/search?c=1&page=" + str(compteur_page) + "&q=" + nom_carte_pour_url

    return(url_site)

def get_prix_de_carta_magica(df_cartes_intrant, message_mag_placerholder, progress_placeholder, message_magasin, list_of_basic_lands, session):
    
    df_resultat_magasin_total = creat_empty_df_resultat_magasin(0)

    for index_df, carte in enumerate(df_cartes_intrant.itertuples()): # Boucle sur toutes les cartes dans le magasin

        ui_progression_scrapping(message_mag_placerholder, progress_placeholder, message_magasin, df_cartes_intrant, carte, index_df)

        if carte.nom_carte in list_of_basic_lands: continue 

        df_resultat_magasin = creat_empty_df_resultat_magasin(100, nom_magasin= "Carta Magica") # Creation d'un df vide pour toutes 100 instances de la meme carte dans le magasin

        # Boucle pour aller voir les 3 premieres pages du magasin si necessaire pour la carte
        Go_to_next_page: bool = True
        compteur_page: int = 1
        compteur_instance_carte: int = 0
        while Go_to_next_page:

            # print(carte.nom_carte, "-> page", compteur_page
            url_site: str = get_Carta_Magica_url(carte.nom_carte, compteur_page=compteur_page)

            try:
                # Faire la requête avec la session
                page_site = session.get(url_site, timeout=30)
                page_site.raise_for_status()

                soup_site: BeautifulSoup = BeautifulSoup(page_site.text, features="lxml")

                fuseau_horaire_montreal = pytz.timezone('America/Montreal') 
                match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now(fuseau_horaire_montreal)))
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
                    lien_carte = "https://www.cartamagica.com" + match_pour_lien_carte.group(1) if match_pour_lien_carte else None

                    Is_not_MTG_card = lien_carte.find("magic") < 0
                    if Is_not_MTG_card:
                        Go_to_next_page: bool = False
                        continue
                
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

                            match_pour_stock_carte = re.search(r'class="variant-short-info variant-qty">\s*([0-9]+)\s', etat_et_langue_carte)
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
                                
            except requests.exceptions.RequestException as e:
                print(f"❌ Erreur de requête pour {url_site}: {e}")
                continue

            except Exception as e:
                print(f"❓ Erreur inconnue pour {carte.nom_carte}: {e}")
                continue

        df_resultat_magasin = df_resultat_magasin[df_resultat_magasin["nom_carte"] != ""] 
        df_resultat_magasin_total = pd.concat([df_resultat_magasin_total, df_resultat_magasin], ignore_index=True)

    return(df_resultat_magasin_total)
def get_Carta_Magica_url(nom_carte: str, compteur_page: int = 1):
    nom_carte_pour_url = nom_carte.replace(" ", "+").replace("'", "%27")
    if compteur_page <= 1 :
        url_site: str = "https://www.cartamagica.com/products/search?q=" + nom_carte_pour_url
    else :
        url_site: str = "https://www.cartamagica.com/products/search?page=" + str(compteur_page) + "&q=" + nom_carte_pour_url

    return(url_site)

def get_prix_de_chez_geeks(df_cartes_intrant, message_mag_placerholder, progress_placeholder, message_magasin, list_of_basic_lands, session):
    
    df_resultat_magasin_total = creat_empty_df_resultat_magasin(0)

    for index_df, carte in enumerate(df_cartes_intrant.itertuples()): # Boucle sur toutes les cartes dans le magasin

        ui_progression_scrapping(message_mag_placerholder, progress_placeholder, message_magasin, df_cartes_intrant, carte, index_df)

        if carte.nom_carte in list_of_basic_lands: continue 

        df_resultat_magasin = creat_empty_df_resultat_magasin(100, nom_magasin= "Chez Geeks") # Creation d'un df vide pour toutes 100 instances de la meme carte dans le magasin

        # Boucle pour aller voir les 3 premieres pages du magasin si necessaire pour la carte
        Go_to_next_page: bool = True
        compteur_page: int = 1
        compteur_instance_carte: int = 0
        while Go_to_next_page:

            # print(carte.nom_carte, "-> page", compteur_page
            url_site: str = get_Chez_Geeks_url(carte.nom_carte, compteur_page=compteur_page)

            try:
                # Faire la requête avec la session
                page_site = session.get(url_site, timeout=30)
                page_site.raise_for_status()

                soup_site: BeautifulSoup = BeautifulSoup(page_site.text, features="lxml")

                fuseau_horaire_montreal = pytz.timezone('America/Montreal') 
                match_pour_date_recherche = re.search(r'([^.]+).', str(datetime.now(fuseau_horaire_montreal)))
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
                    lien_carte = "https://www.chezgeeks.com" + match_pour_lien_carte.group(1) if match_pour_lien_carte else None

                    Is_not_MTG_card = lien_carte.find("magic") < 0
                    if Is_not_MTG_card:
                        Go_to_next_page: bool = False
                        continue
                
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

                            match_pour_stock_carte = re.search(r'class="variant-short-info variant-qty">\s*([0-9]+)\s', etat_et_langue_carte)
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
                                
            except requests.exceptions.RequestException as e:
                print(f"❌ Erreur de requête pour {url_site}: {e}")
                continue

            except Exception as e:
                print(f"❓ Erreur inconnue pour {carte.nom_carte}: {e}")
                continue

        df_resultat_magasin = df_resultat_magasin[df_resultat_magasin["nom_carte"] != ""] 
        df_resultat_magasin_total = pd.concat([df_resultat_magasin_total, df_resultat_magasin], ignore_index=True)

    return(df_resultat_magasin_total)
def get_Chez_Geeks_url(nom_carte: str, compteur_page: int = 1):
    nom_carte_pour_url = nom_carte.replace(" ", "+").replace("'", "%27")
    if compteur_page <= 1 :
        url_site: str = "https://www.chezgeeks.com/products/search?q=" + nom_carte_pour_url
    else :
        url_site: str = "https://www.chezgeeks.com/products/search?page=" + str(compteur_page) + "&q=" + nom_carte_pour_url
    return(url_site)

# APP ---------------------------------------------------------------------------------------------------------------------------

list_of_basic_lands = ["plains", "island", "swamp", "mountain", "forest", "wastes"]
list_de_magasins = ["Alt F4", "Expedition", "Carta Magica", "GK Lajeunesse", "Valet de Coeur", "Chez Geeks"]
temps_recherche_carte =  10 # seconde

url: str = st.secrets["supabase"]["SUPABASE_URL"]
key: str  = st.secrets["supabase"]["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(
    page_title="Chercher un deck",
    page_icon="🔦",
    layout="wide"
)

st.title("🔦Chercher un deck")

st.divider()

st.header("Liste de cartes :")

st.markdown(
"""
Entrez la liste de cartes a chercher ci-dessous :
"""
)

text_cartes_brut = st.text_area(
    label = "Liste de cartes Magic :",
    label_visibility= "hidden",
    value = "",
    placeholder = "Copier coller la quantite et le noms des cartes sous ce format :\n1 sol ring\n1 arcane signet\n..."
)

st.divider()

st.header("Verification de la liste :")

st.markdown(
"""
Verifiez grace a ce bouton que toutes les cartes ont bien ete entrees :
"""
)

if st.button("Verification de la liste de cartes"):

    df_cartes_intrant: pd.DataFrame = separation_intrant_carte(text_cartes_brut)
    verifier_la_liste_de_carte(df_cartes_intrant, supabase, afficher_ui = True)

st.divider()

st.header("Lancer la recherche :")

df_resultat_magasin = pd.DataFrame({
        "magasin": list_de_magasins,
        "est_ouvert": [True] * len(list_de_magasins)
    })
df_resultat_magasin.index = df_resultat_magasin.index + 1

with st.form(key= "validation_magasin_recherche"):

    st.markdown(
    """
    Ci dessous vous avez une liste de magasin avec des boites a cocher. 
    Vous pouvez fermer un magasin en chochant la boite a cote de son nom. 
    Le magasin sera exclu de la recherhe des prix. 
    Cela pourrait accelerer le temps de recherche de l'algorithme. 
    """
    )

    df_resultat_magasin = st.data_editor(df_resultat_magasin, 
                column_config={
                        "magasin": st.column_config.Column(
                            "magasin",
                            disabled=True  # Cette colonne ne sera pas modifiable
                        )
                },
                width='stretch')
    
    st.markdown(
    """
    Si tout est bon, c'est parti pour la recherche des cartes !
    """
    )
        
    validation_magasin_recherche = st.form_submit_button("Lancer la recherche")

if validation_magasin_recherche:

    temps_lancement_algo = time.time()
    message_mag_placerholder = st.empty()
    progress_placeholder = st.empty()

    df_cartes_intrant = separation_intrant_carte(text_cartes_brut)
    df_cartes_intrant = df_cartes_intrant[~df_cartes_intrant["nom_carte"].isin(list_of_basic_lands)]

    df_carte_non_trouvee = df_cartes_intrant

    df_cartes_intrant = df_cartes_intrant[df_cartes_intrant["quantite"] >= 1].groupby('nom_carte', as_index = False)['quantite'].sum()

    list_magasins_ouverts = df_resultat_magasin[df_resultat_magasin['est_ouvert']]['magasin'].tolist()

    session = make_session_connection_site()
    
    try :
        if "Alt F4" in list_magasins_ouverts:
            df_resultat_magasin_total = get_prix_alt_f4(df_cartes_intrant, message_mag_placerholder, progress_placeholder, 
                                                        "Visite de Alt F4 :", list_of_basic_lands, session)
            df_carte_non_trouvee = mettrer_a_jour_les_cartes_non_trouvee(df_carte_non_trouvee, df_resultat_magasin_total)
            progress_placeholder.info("🔄 Sauvegarde des trouvailles...")
            sauvegarder_donnees_magasin(supabase, df_cartes_intrant, df_resultat_magasin_total, "inventaire_Alt_F4")

        if "Expedition" in list_magasins_ouverts:
            df_resultat_magasin_total = get_prix_de_l_expedition(df_cartes_intrant, message_mag_placerholder, progress_placeholder, 
                                                                "Visite de l'Expedition :", list_of_basic_lands, session)
            df_carte_non_trouvee = mettrer_a_jour_les_cartes_non_trouvee(df_carte_non_trouvee, df_resultat_magasin_total)
            progress_placeholder.info("🔄 Sauvegarde des trouvailles...")
            sauvegarder_donnees_magasin(supabase, df_cartes_intrant, df_resultat_magasin_total, "inventaire_Expedition")

        if "Carta Magica" in list_magasins_ouverts:
            df_resultat_magasin_total = get_prix_de_carta_magica(df_cartes_intrant, message_mag_placerholder, progress_placeholder,
                                                                "Visite de Carta Magica :", list_of_basic_lands, session)
            df_carte_non_trouvee = mettrer_a_jour_les_cartes_non_trouvee(df_carte_non_trouvee, df_resultat_magasin_total)
            progress_placeholder.info("🔄 Sauvegarde des trouvailles...")
            sauvegarder_donnees_magasin(supabase, df_cartes_intrant, df_resultat_magasin_total, "inventaire_Carta_Magica")

        if "GK Lajeunesse" in list_magasins_ouverts:
            df_resultat_magasin_total = get_prix_de_games_keeper_lajeunesse(df_cartes_intrant, message_mag_placerholder, progress_placeholder,
                                                                            "Visite de Games Keeper Lajeunesse :", list_of_basic_lands, session)
            df_carte_non_trouvee = mettrer_a_jour_les_cartes_non_trouvee(df_carte_non_trouvee, df_resultat_magasin_total)
            progress_placeholder.info("🔄 Sauvegarde des trouvailles...")
            sauvegarder_donnees_magasin(supabase, df_cartes_intrant, df_resultat_magasin_total, "inventaire_GK_Lajeunesse")

        if "Valet de Coeur" in list_magasins_ouverts:
            df_resultat_magasin_total = get_prix_du_valet_de_coeur(df_cartes_intrant, message_mag_placerholder, progress_placeholder, 
                                                                "Visite du Valet de Coeur :", list_of_basic_lands, session)
            df_carte_non_trouvee = mettrer_a_jour_les_cartes_non_trouvee(df_carte_non_trouvee, df_resultat_magasin_total)
            progress_placeholder.info("🔄 Sauvegarde des trouvailles...")
            sauvegarder_donnees_magasin(supabase, df_cartes_intrant, df_resultat_magasin_total, "inventaire_VdC")

        if "Chez Geeks" in list_magasins_ouverts:
            df_resultat_magasin_total = get_prix_de_chez_geeks(df_cartes_intrant, message_mag_placerholder, progress_placeholder,
                                                                "Visite de Chez Geeks :", list_of_basic_lands, session)
            df_carte_non_trouvee = mettrer_a_jour_les_cartes_non_trouvee(df_carte_non_trouvee, df_resultat_magasin_total)
            progress_placeholder.info("🔄 Sauvegarde des trouvailles...")
            sauvegarder_donnees_magasin(supabase, df_cartes_intrant, df_resultat_magasin_total, "inventaire_Chez_Geeks")

    finally:
        session.close()

    message_mag_placerholder.empty()

    df_carte_non_trouvee = df_carte_non_trouvee.sort_values(["nom_carte"], ascending= [True]).reset_index(drop=True)
    df_carte_non_trouvee.index = df_carte_non_trouvee.index + 1

    if df_carte_non_trouvee.shape[0] <= 0:
        progress_placeholder.success("✅ Algorithme terminé ! Toutes les cartes ont ete trouvees")

    else:
        progress_placeholder.warning("⚠️ Algorithme terminé ! Certaines cartes n'ont pas ete trouvees")
        st.write("Nombre de carte non trouvee :", df_carte_non_trouvee.shape[0], "/", df_cartes_intrant.shape[0])
        st.write("La liste de cartes non trouvees lors de la recherche :") 
        st.dataframe(df_carte_non_trouvee, width='stretch')

    temps_execution_algo = math.ceil((time.time() - temps_lancement_algo)/60)
    st.write("Temps de recherche :", temps_execution_algo, "min")

st.caption("© 2025 - MTG Card Finder Montreal")