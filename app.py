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

def supprimer_ligne(onglet, colonne, valeur):
    try:
        r = requests.delete(f"{API_URL}/{colonne}/{valeur}?sheet={onglet}")
        return r.status_code == 200
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

# --- GÉNÉRATEUR PDF (STYLE IMAGE) ---
def imprimer_bilan(mois_nom, ca, comm, dep, net, df_depenses_mois):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"BILAN MENSUEL - {mois_nom}", ln=True, align="R")
    pdf.ln(20)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"CHIFFRE D'AFFAIRES BRUT : {int(ca):,} F".upper(), ln=True)
    pdf.ln(2)
    pdf.cell(0, 10, f"TOTAL COMMISSIONS : {int(comm):,} F".upper(), ln=True)
    pdf.ln(2)
    pdf.cell(0, 10, f"TOTAL DEPENSES : {int(dep):,} F".upper(), ln=True)
    pdf.ln(2)
    pdf.cell(0, 10, f"MONTANT NET RESTANT : {int(net):,} F".upper(), ln=True)
    pdf.ln(20)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "DETAIL DES DEPENSES :", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "", 11)
    if not df_depenses_mois.empty:
        for _, r in df_depenses_mois.iterrows():
            ligne = f"- {r.get('Date','')} | {r.get('Motif','')} ({r.get('Appartement','')}) : {int(r.get('Montant',0)):,} F"
            pdf.cell(0, 8, ligne, ln=True)
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
                elif app in occupes: st.warning(f"**{app}**\n\n🔴 OCCUPÉ\n\nLibre : {occupes[app]}")
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
                    nom = st.text_input("Nom Complet du Client")
                    dnais = st.date_input("Date Naissance", value=date(1990,1,1))
                    prov = st.text_input("Provenance")
                    tel = st.text_input("Tel Client")
                with c2:
                    piece = st.selectbox("Type Pièce", ["CNI", "Passeport", "Permis"])
                    pnum = st.text_input("Numéro Pièce")
                    app = st.selectbox("Choisir Appartement", libres)
                    rais = st.text_input("Raison du séjour")
                with c3:
                    dent = st.date_input("Date d'Arrivée", value=date.today())
                    nuits = st.number_input("Nombre de nuits", min_value=1, step=1)
                    enom = st.text_input("Nom Employé")
                    etel = st.text_input("Tel Employé")
                dnom = st.text_input("Démarcheur")
                dtel = st.text_input("Tel Démarcheur")

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
                    else: st.error("❌ Erreur API")

    # 3. DÉPENSES & MAINTENANCE
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Saisir Dépense", "🛠️ Maintenance"])
        with tab1:
            with st.form("f_dep"):
                motif = st.text_input("Motif")
                montant = st.number_input("Montant", min_value=0)
                cible = st.selectbox("Cible", ["Général"] + APPARTEMENTS)
                if st.form_submit_button("ENREGISTRER"):
                    sauver({"id":str(uuid.uuid4())[:8], "Date":str(date.today()), "Motif":motif, "Montant":montant, "Appartement":cible, "Mois":datetime.now(TZ_BF).strftime("%m-%Y")}, "depenses")
                    st.success("Dépense enregistrée."); st.cache_data.clear()
        with tab2:
            app_m = st.selectbox("Appartement", APPARTEMENTS)
            stat_m = st.selectbox("Statut", ["Disponible", "Inaccessible"])
            if st.button("Mettre à jour"):
                requests.patch(f"{API_URL}/Appartement/{app_m}?sheet=maintenance", json={"data": {"Statut": stat_m}})
                st.cache_data.clear(); st.rerun()

    # 4. ADMINISTRATION (MODIFICATIONS / SUPPRESSIONS)
    elif menu == "ADMINISTRATION":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            st.header("⚙️ Gestion & Corrections")
            onglet = st.selectbox("Choisir la table", ["sejours", "depenses"])
            df_admin = charger(onglet)
            
            if not df_admin.empty:
                st.write(f"Données actuelles dans **{onglet}** :")
                st.dataframe(df_admin)
                
                st.divider()
                st.subheader("🗑️ Supprimer une entrée")
                col_id = "id" # On utilise l'ID unique pour supprimer sans erreur
                valeurs = df_admin[col_id].tolist()
                selection = st.selectbox("Choisir l'ID à supprimer", valeurs)
                
                if st.button("SUPPRIMER DÉFINITIVEMENT"):
                    if supprimer_ligne(onglet, col_id, selection):
                        st.success("Ligne supprimée !"); st.cache_data.clear(); st.rerun()
                    else: st.error("Erreur lors de la suppression")

    # 5. RAPPORT PDF
    elif menu == "RAPPORT PDF":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            st.header("📊 Bilan Mensuel")
            df_s, df_d = charger("sejours"), charger("depenses")
            if not df_s.empty:
                sel_m = st.selectbox("Mois", df_s["Mois"].unique())
                s_m = df_s[df_s["Mois"] == sel_m]
                d_m = df_d[df_d["Mois"] == sel_m] if not df_d.empty else pd.DataFrame()
                ca = pd.to_numeric(s_m["Montant_Total"]).sum()
                com = pd.to_numeric(s_m["Commission"]).sum()
                dep = pd.to_numeric(d_m["Montant"]).sum() if not d_m.empty else 0
                net = ca - com - dep
                pdf_bytes = imprimer_bilan(sel_m, ca, com, dep, net, d_m)
                st.download_button(f"📥 Télécharger PDF {sel_m}", pdf_bytes, f"Bilan_{sel_m}.pdf")
