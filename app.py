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

st.set_page_config(page_title="Résidence VIP - Dashboard", layout="wide")

# --- FONCTIONS API (OPTIMISÉES) ---
@st.cache_data(ttl=5) # Rafraîchissement automatique toutes les 5 secondes
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
        return requests.delete(f"{API_URL}/{colonne}/{valeur}?sheet={onglet}").status_code == 200
    except: return False

# --- LOGIQUE ETATS ---
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
                if now < h_lib: occupes[row.get("Appartement")] = h_lib.strftime("%d/%m/%Y à 11:00")
            except: continue
    return bloques, occupes

# --- GÉNÉRATEUR PDF (STYLE EXACT) ---
def imprimer_bilan(mois_nom, ca, comm, dep, net, df_dep):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"BILAN MENSUEL - {mois_nom}", ln=True, align="R")
    pdf.ln(20)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"CHIFFRE D'AFFAIRES BRUT : {int(ca):,} F".upper(), ln=True)
    pdf.cell(0, 10, f"TOTAL COMMISSIONS : {int(comm):,} F".upper(), ln=True)
    pdf.cell(0, 10, f"TOTAL DEPENSES : {int(dep):,} F".upper(), ln=True)
    pdf.cell(0, 10, f"MONTANT NET RESTANT : {int(net):,} F".upper(), ln=True)
    pdf.ln(20)
    pdf.cell(0, 10, "DETAIL DES DEPENSES :", ln=True)
    pdf.set_font("Arial", "", 11)
    if not df_dep.empty:
        for _, r in df_dep.iterrows():
            pdf.cell(0, 8, f"- {r.get('Date','')} | {r.get('Motif','')} ({r.get('Appartement','')}) : {int(r.get('Montant',0)):,} F", ln=True)
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- AUTHENTIFICATION ---
if 'auth' not in st.session_state: st.session_state.auth, st.session_state.role = False, None
if not st.session_state.auth:
    st.title("🔐 Connexion Résidence VIP")
    u, p = st.text_input("ID"), st.text_input("Pass", type="password")
    if st.button("Se connecter"):
        if u == "admin" and p == "patron2024": st.session_state.auth, st.session_state.role = True, "admin"; st.rerun()
        elif u == "employe" and p == "bienvenue": st.session_state.auth, st.session_state.role = True, "employe"; st.rerun()
        else: st.error("Invalide")
else:
    bloques, occupes = obtenir_etats()
    st.sidebar.info(f"🇧🇫 {datetime.now(TZ_BF).strftime('%H:%M')}")
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Enregistrement Client", "Dépenses & Maintenance", "ADMINISTRATION", "RAPPORT PDF"])
    if st.sidebar.button("Déconnexion"): st.session_state.auth = False; st.rerun()

    # 1. DASHBOARD
    if menu == "Dashboard":
        st.header("📊 État des Appartements")
        cols = st.columns(4)
        for i, app in enumerate(APPARTEMENTS):
            with cols[i]:
                if app in bloques: st.error(f"**{app}**\n\n❌ BLOQUÉ")
                elif app in occupes: st.warning(f"**{app}**\n\n🔴 OCCUPÉ\n\nLibre : {occupes[app]}")
                else: st.success(f"**{app}**\n\n🟢 LIBRE")

    # 2. ENREGISTREMENT
    elif menu == "Enregistrement Client":
        st.header("📝 Nouveau Client")
        libres = [a for a in APPARTEMENTS if a not in bloques and a not in occupes]
        if not libres: st.warning("Complet !")
        else:
            with st.form("inscription"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    nom = st.text_input("Nom Client")
                    dnais = st.date_input("Naissance", value=date(1990,1,1))
                    prov = st.text_input("Provenance")
                    tel = st.text_input("Tel Client")
                with c2:
                    piece = st.selectbox("Pièce", ["CNI", "Passeport", "Permis"])
                    pnum = st.text_input("N° Pièce")
                    app = st.selectbox("Appartement", libres)
                    rais = st.text_input("Raison")
                with c3:
                    dent = st.date_input("Entrée", value=date.today())
                    nuits = st.number_input("Nuits", min_value=1)
                    enom = st.text_input("Nom Employé")
                    etel = st.text_input("Tel Employé")
                dnom, dtel = st.text_input("Démarcheur"), st.text_input("Tel Démarcheur")
                if st.form_submit_button("VALIDER"):
                    dsor = dent + timedelta(days=nuits)
                    total = nuits * PRIX_NUITEE
                    data = {
                        "id": str(uuid.uuid4())[:8], "Client_Nom": nom, "Date_Naissance": str(dnais), "Provenance": prov,
                        "Piece_Type": piece, "Piece_Num": pnum, "Tel_Client": tel, "Date_Entree": str(dent), "Date_Sortie": str(dsor),
                        "Raison": rais, "Appartement": app, "Employe_Nom": enom, "Employe_Tel": etel,
                        "Demarcheur_Nom": dnom if dnom else "Aucun", "Demarcheur_Tel": dtel if dtel else "Aucun",
                        "Montant_Total": total, "Commission": total*0.1 if dnom else 0, "Mois": dent.strftime("%m-%Y"), "Statut": "En cours"
                    }
                    if sauver(data, "sejours"): st.success("OK !"); st.cache_data.clear(); st.rerun()

    # 3. DEPENSES
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Dépenses", "🛠️ Maintenance"])
        with tab1:
            with st.form("f_dep"):
                motif, mont = st.text_input("Motif"), st.number_input("Montant", min_value=0)
                cible = st.selectbox("Cible", ["Général"] + APPARTEMENTS)
                if st.form_submit_button("Sauver"):
                    sauver({"id":str(uuid.uuid4())[:8], "Date":str(date.today()), "Motif":motif, "Montant":mont, "Appartement":cible, "Mois":datetime.now(TZ_BF).strftime("%m-%Y")}, "depenses")
                    st.success("Enregistré"); st.cache_data.clear()
        with tab2:
            app_m = st.selectbox("Appartement", APPARTEMENTS)
            stat_m = st.selectbox("Statut", ["Disponible", "Inaccessible"])
            if st.button("Mise à jour"):
                requests.patch(f"{API_URL}/Appartement/{app_m}?sheet=maintenance", json={"data": {"Statut": stat_m}})
                st.cache_data.clear(); st.rerun()

    # 4. ADMINISTRATION
    elif menu == "ADMINISTRATION":
        if st.session_state.role != "admin": st.error("Accès Admin")
        else:
            onglet = st.selectbox("Table", ["sejours", "depenses"])
            df = charger(onglet)
            if not df.empty:
                st.dataframe(df)
                sel = st.selectbox("ID à supprimer", df["id"].tolist())
                if st.button("SUPPRIMER"):
                    if supprimer_ligne(onglet, "id", sel): st.success("Supprimé"); st.cache_data.clear(); st.rerun()

    # 5. RAPPORT PDF (VERSION TEMPS RÉEL)
    elif menu == "RAPPORT PDF":
        if st.session_state.role != "admin": st.error("Accès Admin")
        else:
            st.header("📈 Suivi Financier en Temps Réel")
            df_s, df_d = charger("sejours"), charger("depenses")
            
            if not df_s.empty:
                mois_list = sorted(df_s["Mois"].unique(), reverse=True)
                sel_m = st.selectbox("Sélectionner le mois à surveiller", mois_list)
                
                # Filtrage
                s_m = df_s[df_s["Mois"] == sel_m]
                d_m = df_d[df_d["Mois"] == sel_m] if not df_d.empty else pd.DataFrame()
                
                # Calculs automatiques
                ca = pd.to_numeric(s_m["Montant_Total"]).sum()
                com = pd.to_numeric(s_m["Commission"]).sum()
                dep = pd.to_numeric(d_m["Montant"]).sum() if not d_m.empty else 0
                net = ca - com - dep
                
                # AFFICHAGE DU BILAN PROGRESSIF
                st.subheader(f"Bilan de {sel_m}")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("CHIFFRE D'AFFAIRE", f"{ca:,.0f} F", delta_color="normal")
                m2.metric("COMMISSIONS", f"{com:,.0f} F", delta_color="inverse")
                m3.metric("DÉPENSES", f"{dep:,.0f} F", delta_color="inverse")
                m4.metric("MONTANT NET", f"{net:,.0f} F", delta=f"{net:,.0f} F")

                st.divider()
                
                # Affichage des dépenses détaillées
                st.write("**DÉTAIL DES DÉPENSES DU MOIS :**")
                if not d_m.empty:
                    st.table(d_m[["Date", "Motif", "Appartement", "Montant"]])
                else:
                    st.info("Aucune dépense pour ce mois.")

                st.divider()
                
                # Génération du PDF final
                pdf_bytes = imprimer_bilan(sel_m, ca, com, dep, net, d_m)
                st.download_button(f"📥 Télécharger le rapport PDF Officiel - {sel_m}", pdf_bytes, f"Bilan_{sel_m}.pdf")
            else:
                st.warning("Aucune donnée disponible pour générer un bilan.")
