import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date

# --- CONFIGURATION API ---
# Remplacez par votre lien SheetDB
API_URL = "https://sheetdb.io/api/v1/in9prjm4jds07" 

st.set_page_config(page_title="Gestion Résidence - Administration Patron", layout="wide")

# --- FONCTIONS API ---
def charger_donnees(onglet):
    try:
        response = requests.get(f"{API_URL}?sheet={onglet}")
        data = response.json()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def sauvegarder_ligne(nouvelle_ligne, onglet):
    return requests.post(f"{API_URL}?sheet={onglet}", json={"data": [nouvelle_ligne]})

def mettre_a_jour_ligne(nom_client, nouvelle_donnee, onglet):
    # Mise à jour basée sur le nom du client
    return requests.patch(f"{API_URL}/Client_Nom/{nom_client}?sheet={onglet}", json={"data": nouvelle_donnee})

def supprimer_ligne_totalement(nom_client, onglet):
    # Suppression totale de la ligne dans Google Sheets
    return requests.delete(f"{API_URL}/Client_Nom/{nom_client}?sheet={onglet}")

# --- INITIALISATION ---
LISTE_APPARTEMENTS = ["Appart A1", "Appart A2", "Appart A3", "Appart A4"]

if 'authentifie' not in st.session_state:
    st.session_state.authentifie = False
    st.session_state.role = None

# --- CONNEXION ---
if not st.session_state.authentifie:
    st.title("🔐 Accès Direction & Employés")
    user = st.text_input("Identifiant")
    pw = st.text_input("Mot de passe", type="password")
    if st.button("Entrer dans la plateforme"):
        if user == "admin" and pw == "patron2024":
            st.session_state.authentifie, st.session_state.role = True, "admin"
            st.rerun()
        elif user == "employe" and pw == "bienvenue":
            st.session_state.authentifie, st.session_state.role = True, "employe"
            st.rerun()
        else:
            st.error("Identifiants incorrects")
else:
    st.sidebar.header(f"Rôle : {st.session_state.role.upper()}")
    
    options = ["🏠 Tableau de Bord", "📝 Enregistrement Client", "💸 Saisir une Dépense"]
    if st.session_state.role == "admin":
        options.append("⚙️ Gérer / Supprimer (ADMIN)")
        options.append("📊 Rapport Mensuel")
    
    menu = st.sidebar.radio("Menu Principal", options)
    if st.sidebar.button("Se déconnecter"):
        st.session_state.authentifie = False
        st.rerun()

    # --- 1. TABLEAU DE BORD ---
    if "Tableau de Bord" in menu:
        st.header("📊 Disponibilité des Appartements")
        df_s = charger_donnees("sejours")
        occupes = df_s["Appartement"].unique() if not df_s.empty else []
        cols = st.columns(4)
        for i, name in enumerate(LISTE_APPARTEMENTS):
            is_occ = name in occupes
            with cols[i]:
                st.metric(label=name, value="🔴 OCCUPÉ" if is_occ else "🟢 LIBRE")

    # --- 2. ENREGISTREMENT CLIENT (CONFORME CAHIER DE CHARGE) ---
    elif "Enregistrement Client" in menu:
        st.header("📝 Nouvelle Fiche Client")
        with st.form("Inscription"):
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("👤 Identité")
                nom = st.text_input("Nom et Prénom du client")
                tel = st.text_input("Téléphone client")
                date_n = st.date_input("Date de naissance", min_value=date(1915,1,1), value=date(1990,1,1))
                lieu_n = st.text_input("Lieu de naissance")
                prov = st.text_input("Provenance (Pays et Ville)")
                piece_t = st.selectbox("Type de pièce", ["CNI", "Passeport", "Permis", "Carte Séjour"])
                piece_n = st.text_input("N° de la pièce")
            with c2:
                st.subheader("🏠 Séjour")
                appart = st.selectbox("Appartement choisi", LISTE_APPARTEMENTS)
                d_ent = st.date_input("Date d'arrivée")
                d_sor = st.date_input("Date de départ prévue")
                raison = st.text_area("Raison du séjour")
                emp_nom = st.text_input("Employé responsable")
                emp_tel = st.text_input("Tel de l'employé")
            
            st.subheader("🤝 Intermédiaire")
            dem_nom = st.text_input("Nom du démarcheur (Si aucun, vide)")
            dem_tel = st.text_input("Téléphone démarcheur")
            
            if st.form_submit_button("VALIDER ET ENVOYER"):
                nuits = max((d_sor - d_ent).days, 1)
                brut = nuits * 15000
                comm = (brut * 0.10) if dem_nom else 0
                nouvelle_ligne = {
                    "Client_Nom": nom, "Tel_Client": tel, "Date_Naissance": str(date_n),
                    "Lieu_Naissance": lieu_n, "Provenance": prov, "Piece_Type": piece_t,
                    "Piece_Num": piece_n, "Appartement": appart, "Date_Entree": str(d_ent),
                    "Date_Sortie": str(d_sor), "Raison": raison, "Employe_Garde": emp_nom,
                    "Employe_Tel": emp_tel, "Nuits": nuits, "Montant_Brut": brut,
                    "Demarcheur_Nom": dem_nom if dem_nom else "Aucun", "Demarcheur_Tel": dem_tel,
                    "Commission": comm, "Mois": d_ent.strftime("%B %Y")
                }
                sauvegarder_ligne(nouvelle_ligne, "sejours")
                st.success(f"✅ Enregistrement réussi ! Montant : {brut:,} F CFA")

    # --- 3. SAISIR UNE DÉPENSE ---
    elif "Saisir une Dépense" in menu:
        st.header("💸 Sortie de Caisse")
        with st.form("Depense"):
            type_d = st.radio("Cible", ["Appartement Spécifique", "Dépense Générale"])
            montant_d = st.number_input("Somme dépensée (F)", min_value=0)
            date_d = st.date_input("Date du paiement")
            if type_d == "Appartement Spécifique":
                app_d = st.selectbox("Appartement concerné", LISTE_APPARTEMENTS)
                cat_d = st.selectbox("Catégorie", ["Électricité", "Canal+ / TV"])
                desc_d = f"{cat_d} {app_d}"
            else:
                app_d, cat_d = "Global", "Divers"
                desc_d = st.text_input("Motif de la dépense")
            
            if st.form_submit_button("ENREGISTRER LA DÉPENSE"):
                nouvelle_dep = {
                    "Date": str(date_d), "Type": type_d, "Appartement": app_d,
                    "Categorie": cat_d, "Description": desc_d, "Montant": montant_d,
                    "Mois": date_d.strftime("%B %Y")
                }
                sauvegarder_ligne(nouvelle_dep, "depenses")
                st.success("Dépense enregistrée sur Google Sheets.")

    # --- 4. GÉRER / SUPPRIMER (ACTION PATRON) ---
    elif "Gérer" in menu:
        st.header("⚙️ Espace de Correction Patron")
        df_s = charger_donnees("sejours")
        
        if not df_s.empty:
            st.subheader("1. Sélectionner l'entrée à traiter")
            liste_noms = df_s["Client_Nom"].tolist()
            client_sel = st.selectbox("Chercher le nom du client enregistré par l'employé", [""] + liste_noms)
            
            if client_sel:
                data = df_s[df_s["Client_Nom"] == client_sel].iloc[0]
                
                # --- PARTIE MODIFICATION ---
                st.divider()
                st.subheader("📝 Modifier les informations")
                with st.form("Modif_Form"):
                    col1, col2 = st.columns(2)
                    new_tel = col1.text_input("Nouveau Téléphone", value=data["Tel_Client"])
                    new_app = col1.selectbox("Changer Appartement", LISTE_APPARTEMENTS, index=LISTE_APPARTEMENTS.index(data["Appartement"]))
                    new_brut = col2.number_input("Corriger Montant Total (F)", value=int(data["Montant_Brut"]))
                    new_ent = col2.text_input("Date Entrée (AAAA-MM-JJ)", value=data["Date_Entree"])
                    
                    if st.form_submit_button("💾 ENREGISTRER LES CORRECTIONS"):
                        maj = {"Tel_Client": new_tel, "Appartement": new_app, "Montant_Brut": new_brut, "Date_Entree": new_ent}
                        mettre_a_jour_ligne(client_sel, maj, "sejours")
                        st.success("Modifications enregistrées !")
                        st.rerun()

                # --- PARTIE SUPPRESSION TOTALE ---
                st.divider()
                st.subheader("🗑️ Zone de Suppression (Action irréversible)")
                st.error(f"Attention : Vous allez supprimer totalement le passage de {client_sel} de la base de données.")
                confirmer = st.checkbox("Je confirme que cette action de l'employé est invalide et je veux l'effacer.")
                
                if st.button("❌ SUPPRIMER DÉFINITIVEMENT CETTE LIGNE"):
                    if confirmer:
                        supprimer_ligne_totalement(client_sel, "sejours")
                        st.success(f"L'entrée de {client_sel} a été totalement effacée.")
                        st.rerun()
                    else:
                        st.warning("Veuillez cocher la case de confirmation avant de supprimer.")
        else:
            st.info("Aucun séjour enregistré à modifier.")

    # --- 5. RAPPORT MENSUEL ---
    elif "Rapport Mensuel" in menu:
        st.header("📊 Bilan Comptable Mensuel")
        df_s = charger_donnees("sejours")
        df_d = charger_donnees("depenses")
        
        if not df_s.empty:
            mois_sel = st.selectbox("Mois à consulter", df_s["Mois"].unique())
            s_m = df_s[df_s["Mois"] == mois_sel]
            d_m = df_d[df_d["Mois"] == mois_sel] if not df_d.empty else pd.DataFrame()
            
            # Conversion pour calculs
            s_m["Montant_Brut"] = pd.to_numeric(s_m["Montant_Brut"], errors='coerce').fillna(0)
            s_m["Commission"] = pd.to_numeric(s_m["Commission"], errors='coerce').fillna(0)
            d_m["Montant"] = pd.to_numeric(d_m["Montant"], errors='coerce').fillna(0)

            st.subheader("🏠 Performance par Appartement")
            stats = s_m.groupby("Appartement").agg({"Nuits": "sum", "Montant_Brut": "sum"}).rename(columns={"Montant_Brut": "CA Brut"})
            st.dataframe(stats)

            st.divider()
            ca = s_m["Montant_Brut"].sum()
            co = s_m["Commission"].sum()
            de = d_m["Montant"].sum()
            net = ca - co - de
            
            c1, c2, c3 = st.columns(3)
            c1.metric("CA TOTAL", f"{ca:,} F")
            c2.metric("TOTAL COMMISSIONS", f"-{co:,} F")
            c2.metric("TOTAL DÉPENSES", f"-{de:,} F")
            c3.success(f"**BÉNÉFICE NET : {net:,} F CFA**")
