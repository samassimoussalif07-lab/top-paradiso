import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Gestion Résidence G-Sheets", layout="wide")

# --- CONNEXION À GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FONCTIONS DE GESTION DES DONNÉES ---
def charger_sejours():
    return conn.read(worksheet="sejours", ttl=0) # ttl=0 pour forcer la lecture réelle

def charger_depenses():
    return conn.read(worksheet="depenses", ttl=0)

def ajouter_ligne(df_existant, nouvelle_ligne, onglet):
    # Ajouter la nouvelle ligne au dataframe
    df_maj = pd.concat([df_existant, pd.DataFrame([nouvelle_ligne])], ignore_index=True)
    # Envoyer vers Google Sheets
    conn.update(worksheet=onglet, data=df_maj)
    st.cache_data.clear() # Nettoyer le cache pour voir les modifs

# --- INITIALISATION ---
LISTE_APPARTEMENTS = ["Appart A1", "Appart A2", "Appart A3", "Appart A4"]

if 'authentifie' not in st.session_state:
    st.session_state.authentifie = False
    st.session_state.role = None

# --- SYSTÈME DE CONNEXION ---
def login_page():
    st.title("🏨 Gestion Résidence (Cloud) - Connexion")
    with st.form("Login"):
        user = st.text_input("Identifiant")
        pw = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Se connecter"):
            if user == "admin" and pw == "patron2024":
                st.session_state.authentifie, st.session_state.role = True, "admin"
                st.rerun()
            elif user == "employe" and pw == "bienvenue":
                st.session_state.authentifie, st.session_state.role = True, "employe"
                st.rerun()
            else:
                st.error("Identifiants incorrects")

if not st.session_state.authentifie:
    login_page()
else:
    # Chargement des données en temps réel depuis Google
    df_sejours = charger_sejours()
    df_depenses = charger_depenses()

    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    options = ["Tableau de Bord", "Enregistrer un Client", "Saisir une Dépense"]
    if st.session_state.role == "admin":
        options.append("Bilan Financier")
    
    menu = st.sidebar.radio("Navigation", options)
    if st.sidebar.button("Déconnexion"):
        st.session_state.authentifie = False
        st.rerun()

    # --- 1. TABLEAU DE BORD ---
    if menu == "Tableau de Bord":
        st.header("📊 État en temps réel")
        occupes = df_sejours["Appartement"].unique() if not df_sejours.empty else []
        cols = st.columns(4)
        for i, name in enumerate(LISTE_APPARTEMENTS):
            is_occ = name in occupes
            with cols[i]:
                st.metric(label=name, value="🔴 Occupé" if is_occ else "🟢 Libre")

    # --- 2. ENREGISTREMENT CLIENT ---
    elif menu == "Enregistrer un Client":
        st.header("📝 Nouveau Séjour (Sauvegarde Cloud)")
        with st.form("Client_Form"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Prénom et Nom")
                tel = st.text_input("Téléphone")
                date_n = st.date_input("Date de Naissance", min_value=date(1915, 1, 1), value=date(1990, 1, 1))
                piece = st.selectbox("Pièce d'identité", ["Passeport", "CNI", "Permis", "Carte Séjour"])
            with c2:
                appart = st.selectbox("Appartement", LISTE_APPARTEMENTS)
                d_ent = st.date_input("Date d'entrée")
                d_sor = st.date_input("Date de sortie prévue")
                dem_nom = st.text_input("Démarcheur (Optionnel)")
            
            if st.form_submit_button("Valider et Sauvegarder sur Google"):
                nuits = max((d_sor - d_ent).days, 1)
                brut = nuits * 15000
                comm = brut * 0.10 if dem_nom else 0
                nouvelle_ligne = {
                    "Client": nom, "Tel_Client": tel, "Appartement": appart,
                    "Entree": str(d_ent), "Sortie": str(d_sor), "Nuits": nuits,
                    "Montant_Brut": brut, "Commission": comm, 
                    "Demarcheur": dem_nom if dem_nom else "Aucun",
                    "Mois": d_ent.strftime("%B %Y")
                }
                ajouter_ligne(df_sejours, nouvelle_ligne, "sejours")
                st.success(f"✅ Données envoyées sur Google Sheets ! Total : {brut:,} F")

    # --- 3. SAISIR UNE DÉPENSE ---
    elif menu == "Saisir une Dépense":
        st.header("💸 Frais & Dépenses")
        with st.form("Depense_Form"):
            type_d = st.radio("Type", ["Par Appartement", "Dépense Générale"])
            montant_d = st.number_input("Montant (F)", min_value=0)
            date_d = st.date_input("Date")
            if type_d == "Par Appartement":
                app_d = st.selectbox("Appartement", LISTE_APPARTEMENTS)
                cat_d = st.selectbox("Catégorie", ["Électricité", "Abonnement TV"])
                desc_d = f"{cat_d} {app_d}"
            else:
                app_d, cat_d = "Global", "Autre"
                desc_d = st.text_input("Description")
            
            if st.form_submit_button("Sauvegarder la dépense"):
                nouvelle_dep = {
                    "Date": str(date_d), "Type": type_d, "Appartement": app_d,
                    "Categorie": cat_d, "Description": desc_d, "Montant": montant_d,
                    "Mois": date_d.strftime("%B %Y")
                }
                ajouter_ligne(df_depenses, nouvelle_dep, "depenses")
                st.success("Dépense enregistrée sur Google.")

    # --- 4. BILAN FINANCIER (ADMIN) ---
    elif menu == "Bilan Financier":
        st.header("💰 Bilan consolidé (Google Sheets)")
        
        tous_mois = sorted(list(set(df_sejours["Mois"].dropna()) | set(df_depenses["Mois"].dropna())))
        if tous_mois:
            mois_sel = st.selectbox("Mois à analyser", tous_mois)
            
            # Filtres
            s_mois = df_sejours[df_sejours["Mois"] == mois_sel]
            d_mois = df_depenses[df_depenses["Mois"] == mois_sel]
            
            rev_brut = s_mois["Montant_Brut"].sum()
            t_comm = s_mois["Commission"].sum()
            t_dep = d_mois["Montant"].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Revenu Brut", f"{rev_brut:,} F")
            c2.metric("Commissions", f"- {t_comm:,} F")
            c3.metric("Dépenses", f"- {t_dep:,} F")
            
            st.subheader(f"💵 Bénéfice Net : {rev_brut - t_comm - t_dep:,} F CFA")
            st.write("---")
            st.write("Dernières opérations (Google Sheets) :")
            st.dataframe(s_mois)
        else:
            st.info("Aucune donnée disponible.")