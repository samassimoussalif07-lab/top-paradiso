import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from fpdf import FPDF
import base64

# --- CONFIGURATION API ---
API_URL = "https://sheetdb.io/api/v1/in9prjm4jds07" 

st.set_page_config(page_title="Top-Paradiso - Gestion Pro", layout="wide")

# --- FONCTION PDF ---
def generer_pdf(df_sejours, df_depenses, mois_sel):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"Rapport Mensuel - {mois_sel}", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(200, 10, "Residence Top-Paradiso | Heure limite de depart: 11h00", ln=True, align="C")
    
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Detail des Sejours :", ln=True)
    pdf.set_font("Arial", "", 9)
    
    for index, row in df_sejours.iterrows():
        txt = f"Appart: {row['Appartement']} | Client: {row['Client_Nom']} | Entree: {row['Date_Entree']} | Sortie: {row['Date_Sortie']} (11h00) | Montant: {row['Montant_Brut']} F"
        pdf.cell(0, 8, txt, ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Detail des Depenses :", ln=True)
    pdf.set_font("Arial", "", 9)
    for index, row in df_depenses.iterrows():
        pdf.cell(0, 8, f"{row['Date']} - {row['Description']} : {row['Montant']} F", ln=True)
    
    return pdf.output(dest="S").encode("latin-1")

# --- FONCTIONS API ---
def charger_donnees(onglet):
    try:
        response = requests.get(f"{API_URL}?sheet={onglet}")
        return pd.DataFrame(response.json())
    except: return pd.DataFrame()

def sauvegarder_ligne(nouvelle_ligne, onglet):
    return requests.post(f"{API_URL}?sheet={onglet}", json={"data": [nouvelle_ligne]})

def mettre_a_jour_ligne(nom_client, nouvelle_donnee, onglet):
    return requests.patch(f"{API_URL}/Client_Nom/{nom_client}?sheet={onglet}", json={"data": nouvelle_donnee})

def supprimer_ligne(nom_client, onglet):
    return requests.delete(f"{API_URL}/Client_Nom/{nom_client}?sheet={onglet}")

# --- INITIALISATION ---
LISTE_APPARTEMENTS = ["Appart A1", "Appart A2", "Appart A3", "Appart A4"]

if 'authentifie' not in st.session_state:
    st.session_state.authentifie, st.session_state.role = False, None

# --- CONNEXION ---
if not st.session_state.authentifie:
    st.title("🔐 Top-Paradiso - Accès Sécurisé")
    u = st.text_input("Identifiant")
    p = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if u == "admin" and p == "patron2024":
            st.session_state.authentifie, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "employe" and p == "bienvenue":
            st.session_state.authentifie, st.session_state.role = True, "employe"
            st.rerun()
        else: st.error("Erreur d'identifiants")
else:
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    options = ["🏠 Tableau de Bord", "📝 Enregistrement Client", "💸 Saisir une Dépense"]
    if st.session_state.role == "admin":
        options += ["✏️ Modifier / Tout Gérer", "📊 Rapport & PDF"]
    
    menu = st.sidebar.radio("Navigation", options)
    if st.sidebar.button("Déconnexion"):
        st.session_state.authentifie = False
        st.rerun()

    # --- 1. TABLEAU DE BORD ---
    if "Tableau de Bord" in menu:
        st.header("📊 État des Appartements")
        df_s = charger_donnees("sejours")
        occ = df_s["Appartement"].unique() if not df_s.empty else []
        cols = st.columns(4)
        for i, name in enumerate(LISTE_APPARTEMENTS):
            with cols[i]: st.metric(name, "🔴 Occupé" if name in occ else "🟢 Libre")

    # --- 2. ENREGISTREMENT ---
    elif "Enregistrement Client" in menu:
        st.header("📝 Nouvelle Fiche (Départ prévu à 11h00)")
        with st.form("Inscription"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom complet")
                tel = st.text_input("Téléphone")
                prov = st.text_input("Provenance (Pays/Ville)")
                date_n = st.date_input("Date Naissance", min_value=date(1915,1,1), value=date(1995,1,1))
                piece = st.text_input("Type et N° de pièce")
            with c2:
                app = st.selectbox("Appartement", LISTE_APPARTEMENTS)
                d_e = st.date_input("Arrivée")
                d_s = st.date_input("Départ")
                gard = st.text_input("Employé de garde")
                dem = st.text_input("Démarcheur (Si aucun, vide)")
            
            if st.form_submit_button("VALIDER"):
                nuits = max((d_s - d_e).days, 1)
                brut = nuits * 15000
                nouvelle_ligne = {
                    "Client_Nom": nom, "Tel_Client": tel, "Provenance": prov, "Date_Naissance": str(date_n),
                    "Piece_Num": piece, "Appartement": app, "Date_Entree": str(d_e),
                    "Date_Sortie": str(d_s), "Employe_Garde": gard, "Montant_Brut": brut,
                    "Commission": (brut*0.1) if dem else 0, "Demarcheur_Nom": dem if dem else "Aucun",
                    "Mois": d_e.strftime("%B %Y")
                }
                sauvegarder_ligne(nouvelle_ligne, "sejours")
                st.success(f"Enregistré ! Fin de séjour à 11h00. Total : {brut} F")

    # --- 3. DÉPENSES ---
    elif "Saisir une Dépense" in menu:
        st.header("💸 Sortie de Caisse")
        with st.form("Dep"):
            app_d = st.selectbox("Cible", ["Général"] + LISTE_APPARTEMENTS)
            montant = st.number_input("Montant", min_value=0)
            motif = st.text_input("Motif de la dépense (Electricité, TV, Réparation...)")
            if st.form_submit_button("Enregistrer"):
                sauvegarder_ligne({"Date": str(date.today()), "Description": f"{motif} ({app_d})", "Montant": montant, "Mois": date.today().strftime("%B %Y")}, "depenses")
                st.success("Dépense enregistrée.")

    # --- 4. MODIFIER TOUT (ADMIN) ---
    elif "Modifier" in menu:
        st.header("✏️ Modification Totale par le Patron")
        df = charger_donnees("sejours")
        if not df.empty:
            sel = st.selectbox("Choisir l'entrée à corriger", df["Client_Nom"].tolist())
            d = df[df["Client_Nom"] == sel].iloc[0]
            with st.form("Edit"):
                new_nom = st.text_input("Nom Client", value=d["Client_Nom"])
                new_app = st.selectbox("Appartement", LISTE_APPARTEMENTS, index=LISTE_APPARTEMENTS.index(d["Appartement"]))
                new_ent = st.text_input("Date Entrée", value=d["Date_Entree"])
                new_sor = st.text_input("Date Sortie", value=d["Date_Sortie"])
                new_mnt = st.number_input("Montant Brut", value=int(d["Montant_Brut"]))
                new_gard = st.text_input("Employé de garde", value=d["Employe_Garde"])
                
                c_mod, c_sup = st.columns(2)
                if c_mod.form_submit_button("💾 SAUVEGARDER TOUT"):
                    mettre_a_jour_ligne(sel, {"Client_Nom": new_nom, "Appartement": new_app, "Date_Entree": new_ent, "Date_Sortie": new_sor, "Montant_Brut": new_mnt, "Employe_Garde": new_gard}, "sejours")
                    st.success("Mise à jour réussie")
                    st.rerun()
                if c_sup.form_submit_button("❌ SUPPRIMER DÉFINITIVEMENT"):
                    supprimer_ligne(sel, "sejours")
                    st.error("Supprimé !")
                    st.rerun()

    # --- 5. RAPPORT & PDF (ADMIN) ---
    elif "Rapport" in menu:
        st.header("📊 Bilan Mensuel & Impression")
        df_s = charger_donnees("sejours")
        df_d = charger_donnees("depenses")
        if not df_s.empty:
            mois = st.selectbox("Mois", df_s["Mois"].unique())
            s_m = df_s[df_s["Mois"] == mois]
            d_m = df_d[df_d["Mois"] == mois] if not df_d.empty else pd.DataFrame()
            
            st.dataframe(s_m)
            
            # Calculs
            ca = pd.to_numeric(s_m["Montant_Brut"]).sum()
            de = pd.to_numeric(d_m["Montant"]).sum() if not d_m.empty else 0
            st.write(f"**Revenu Brut : {ca:,} F | Dépenses : {de:,} F | Net : {ca-de:,} F**")
            
            # BOUTON PDF
            pdf_data = generer_pdf(s_m, d_m, mois)
            st.download_button(label="📥 Télécharger le Rapport PDF", data=pdf_data, file_name=f"Rapport_{mois}.pdf", mime="application/pdf")
