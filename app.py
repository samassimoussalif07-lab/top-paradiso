import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta
from fpdf import FPDF
import uuid
import pytz

# --- CONFIGURATION ---
API_URL = "https://sheetdb.io/api/v1/2a307403dpyom" 
PRIX_NUITEE = 15000
APPARTEMENTS = ["Appart A1", "Appart A2", "Appart A3", "Appart A4"]
TZ_BF = pytz.timezone('Africa/Ouagadougou')

st.set_page_config(page_title="Gestion Résidence VIP", layout="wide")

# --- FONCTIONS API ---
@st.cache_data(ttl=5)
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}", timeout=10)
        return pd.DataFrame(r.json()) if r.status_code == 200 else pd.DataFrame()
    except: return pd.DataFrame()

def sauver(ligne, onglet):
    try:
        r = requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]}, timeout=10)
        return r.status_code == 201
    except: return False

# --- LOGIQUE DE DISPONIBILITÉ (11H00) ---
def obtenir_etats():
    df_s, df_m = charger("sejours"), charger("maintenance")
    now = datetime.now(TZ_BF)
    bloques, occupes = [], {}

    if not df_m.empty and "Statut" in df_m.columns:
        bloques = df_m[df_m["Statut"] == "Inaccessible"]["Appartement"].tolist()

    if not df_s.empty and "Statut" in df_s.columns:
        en_cours = df_s[df_s["Statut"] == "En cours"]
        for _, row in en_cours.iterrows():
            try:
                ds = row.get("Date_Sortie")
                h_lib = TZ_BF.localize(datetime.combine(datetime.strptime(ds, "%Y-%m-%d"), time(11, 0)))
                if now < h_lib:
                    occupes[row.get("Appartement")] = h_lib.strftime("%d/%m/%Y à 11:00")
            except: continue
    return bloques, occupes

# --- GÉNÉRATEUR PDF (STYLE EXACT DE L'IMAGE) ---
def imprimer_bilan(mois_nom, ca, comm, dep, net, df_depenses_mois):
    pdf = FPDF()
    pdf.add_page()
    
    # Titre en haut à droite
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"BILAN MENSUEL - {mois_nom}", ln=True, align="R")
    pdf.ln(20)

    # Section des totaux
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"CHIFFRE D'AFFAIRES BRUT : {int(ca):,} F".upper(), ln=True)
    pdf.ln(2)
    pdf.cell(0, 10, f"TOTAL COMMISSIONS : {int(comm):,} F".upper(), ln=True)
    pdf.ln(2)
    pdf.cell(0, 10, f"TOTAL DEPENSES : {int(dep):,} F".upper(), ln=True)
    pdf.ln(2)
    pdf.cell(0, 10, f"MONTANT NET RESTANT : {int(net):,} F".upper(), ln=True)
    
    pdf.ln(20)
    
    # Détail des dépenses
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "DETAIL DES DEPENSES :", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 11)
    if not df_depenses_mois.empty:
        for _, r in df_depenses_mois.iterrows():
            # Format: - Date | Motif (Cible) : Montant F
            ligne = f"- {r.get('Date','')} | {r.get('Motif','')} ({r.get('Appartement','')}) : {int(r.get('Montant',0)):,} F"
            pdf.cell(0, 8, ligne, ln=True)
    else:
        pdf.cell(0, 10, "Aucune dépense enregistrée.", ln=True)
        
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- AUTHENTIFICATION ---
if 'auth' not in st.session_state: st.session_state.auth, st.session_state.role = False, None

if not st.session_state.auth:
    st.title("🔐 Connexion Résidence VIP")
    u, p = st.text_input("Identifiant"), st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if u == "admin" and p == "patron2024": st.session_state.auth, st.session_state.role = True, "admin"; st.rerun()
        elif u == "employe" and p == "bienvenue": st.session_state.auth, st.session_state.role = True, "employe"; st.rerun()
        else: st.error("Identifiants incorrects")
else:
    bloques, occupes = obtenir_etats()
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    st.sidebar.info(f"🇧🇫 Ouaga : {datetime.now(TZ_BF).strftime('%H:%M')}")
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Enregistrement Client", "Dépenses & Maintenance", "ADMINISTRATION", "RAPPORT PDF"])
    if st.sidebar.button("Déconnexion"): st.session_state.auth = False; st.rerun()

    # 1. DASHBOARD
    if menu == "Dashboard":
        st.header("📊 État de la Résidence")
        cols = st.columns(4)
        for i, app in enumerate(APPARTEMENTS):
            with cols[i]:
                if app in bloques: st.error(f"**{app}**\n\n❌ MAINTENANCE")
                elif app in occupes: st.warning(f"**{app}**\n\n🔴 OCCUPÉ\n\nLibre le : {occupes[app]}")
                else: st.success(f"**{app}**\n\n🟢 LIBRE")

    # 2. ENREGISTREMENT CLIENT
    elif menu == "Enregistrement Client":
        st.header("📝 Nouveau Client")
        libres = [a for a in APPARTEMENTS if a not in bloques and a not in occupes]
        if not libres: st.warning("⚠️ Aucun appartement disponible.")
        else:
            with st.form("inscription"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    nom = st.text_input("Client_Nom")
                    dnais = st.date_input("Date_Naissance", value=date(1990,1,1))
                    prov = st.text_input("Provenance")
                    tel = st.text_input("Tel_Client")
                with c2:
                    piece = st.selectbox("Piece_Type", ["CNI", "Passeport", "Permis"])
                    pnum = st.text_input("Piece_Num")
                    app = st.selectbox("Appartement", libres)
                    rais = st.text_input("Raison")
                with c3:
                    dent = st.date_input("Date_Entree", value=date.today())
                    nuits = st.number_input("Nombre de nuits", min_value=1)
                    enom = st.text_input("Employe_Nom")
                    etel = st.text_input("Employe_Tel")
                dnom = st.text_input("Demarcheur_Nom")
                dtel = st.text_input("Demarcheur_Tel")

                if st.form_submit_button("VALIDER"):
                    dsor = dent + timedelta(days=nuits)
                    total = nuits * PRIX_NUITEE
                    comm = total * 0.10 if dnom else 0
                    data = {
                        "id": str(uuid.uuid4())[:8], "Client_Nom": nom, "Date_Naissance": str(dnais),
                        "Provenance": prov, "Piece_Type": piece, "Piece_Num": pnum,
                        "Tel_Client": tel, "Date_Entree": str(dent), "Date_Sortie": str(dsor),
                        "Raison": rais, "Appartement": app, "Employe_Nom": enom, "Employe_Tel": etel,
                        "Demarcheur_Nom": dnom if dnom else "Aucun", "Demarcheur_Tel": dtel if dtel else "Aucun",
                        "Montant_Total": total, "Commission": comm, "Mois": dent.strftime("%m-%Y"), "Statut": "En cours"
                    }
                    if sauver(data, "sejours"):
                        st.success("✅ Enregistré !"); st.cache_data.clear(); st.rerun()

    # 3. DÉPENSES & MAINTENANCE
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Saisir Dépense", "🛠️ Maintenance"])
        with tab1:
            with st.form("f_dep"):
                motif = st.text_input("Motif")
                montant = st.number_input("Montant", min_value=0)
                cible = st.selectbox("Cible", ["Général"] + APPARTEMENTS)
                emp = st.text_input("Votre Nom")
                if st.form_submit_button("ENREGISTRER"):
                    sauver({"id":str(uuid.uuid4())[:8], "Date":str(date.today()), "Motif":motif, "Montant":montant, "Appartement":cible, "Employe":emp, "Mois":datetime.now(TZ_BF).strftime("%m-%Y")}, "depenses")
                    st.success("Dépense enregistrée."); st.cache_data.clear()
        with tab2:
            app_m = st.selectbox("Appartement", APPARTEMENTS)
            stat_m = st.selectbox("Statut", ["Disponible", "Inaccessible"])
            if st.button("Mettre à jour"):
                requests.patch(f"{API_URL}/Appartement/{app_m}?sheet=maintenance", json={"data": {"Statut": stat_m}})
                st.cache_data.clear(); st.rerun()

    # 4. RAPPORT PDF (LOGIQUE DE CALCUL ET AFFICHAGE)
    elif menu == "RAPPORT PDF":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            st.header("📊 Génération du Bilan Mensuel")
            df_s = charger("sejours")
            df_d = charger("depenses")
            
            if not df_s.empty:
                mois_dispo = df_s["Mois"].unique()
                sel_m = st.selectbox("Choisir le mois", mois_dispo)
                
                # Filtrage des données du mois sélectionné
                s_m = df_s[df_s["Mois"] == sel_m]
                d_m = df_d[df_d["Mois"] == sel_m] if not df_d.empty else pd.DataFrame()
                
                # Calculs
                ca = pd.to_numeric(s_m["Montant_Total"], errors='coerce').sum()
                com = pd.to_numeric(s_m["Commission"], errors='coerce').sum()
                dep = pd.to_numeric(d_m["Montant"], errors='coerce').sum() if not d_m.empty else 0
                net = ca - com - dep
                
                # Affichage Aperçu
                st.subheader(f"Bilan de {sel_m}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("CA Brut", f"{ca:,.0f} F")
                c2.metric("Commissions", f"{com:,.0f} F")
                c3.metric("Dépenses", f"{dep:,.0f} F")
                c4.metric("Net Restant", f"{net:,.0f} F")
                
                # Bouton de téléchargement
                pdf_bytes = imprimer_bilan(sel_m, ca, com, dep, net, d_m)
                st.download_button(f"📥 Télécharger PDF {sel_m}", pdf_bytes, f"Bilan_{sel_m}.pdf", "application/pdf")
