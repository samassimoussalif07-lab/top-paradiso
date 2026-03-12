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

MOIS_FR = {
    "01": "JANVIER", "02": "FEVRIER", "03": "MARS", "04": "AVRIL",
    "05": "MAI", "06": "JUIN", "07": "JUILLET", "08": "AOUT",
    "09": "SEPTEMBRE", "10": "OCTOBRE", "11": "NOVEMBRE", "12": "DECEMBRE"
}

st.set_page_config(page_title="Résidence VIP - Gestion", layout="wide")

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
        return requests.delete(f"{API_URL}/{colonne}/{valeur}?sheet={onglet}").status_code in [200, 204]
    except: return False

# --- LOGIQUE ETATS (OCCUPATION & MAINTENANCE) ---
def obtenir_etats():
    df_s, df_m = charger("sejours"), charger("maintenance")
    now = datetime.now(TZ_BF)
    bloques, occupes = {}, {}

    # 1. Maintenance : on récupère le statut et la raison
    if not df_m.empty and "Statut" in df_m.columns:
        for _, row in df_m.iterrows():
            if row.get("Statut") == "Inaccessible":
                bloques[row.get("Appartement")] = row.get("Raison", "Maintenance en cours")

    # 2. Occupations : libération à 11h00
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

# --- GÉNÉRATEUR PDF ---
def imprimer_bilan(mois_code, ca, comm, dep, net, df_dep):
    m_num, annee = mois_code.split("-")
    nom_mois = MOIS_FR.get(m_num, "INCONNU")
    titre_bilan = f"BILAN DU MOIS DE {nom_mois} {annee}"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, titre_bilan, ln=True, align="R")
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
        else: st.error("Identifiants incorrects")
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
                if app in bloques: 
                    st.error(f"**{app}**\n\n❌ MAINTENANCE\n\nMotif: {bloques[app]}")
                elif app in occupes: 
                    st.warning(f"**{app}**\n\n🔴 OCCUPÉ\n\nLibre : {occupes[app]}")
                else: 
                    st.success(f"**{app}**\n\n🟢 LIBRE")

    # 2. ENREGISTREMENT CLIENT
    elif menu == "Enregistrement Client":
        st.header("📝 Nouveau Client")
        libres = [a for a in APPARTEMENTS if a not in bloques and a not in occupes]
        if not libres: st.warning("⚠️ Aucun appartement disponible.")
        else:
            with st.form("inscription"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    nom, dnais = st.text_input("Nom Client"), st.date_input("Naissance", value=date(1990,1,1))
                    prov, tel = st.text_input("Provenance"), st.text_input("Tel Client")
                with c2:
                    piece, pnum = st.selectbox("Pièce", ["CNI", "Passeport", "Permis"]), st.text_input("N° Pièce")
                    app, rais_s = st.selectbox("Appartement", libres), st.text_input("Raison du séjour")
                with c3:
                    dent, nuits = st.date_input("Entrée", value=date.today()), st.number_input("Nuits", min_value=1)
                    enom, etel = st.text_input("Nom Employé"), st.text_input("Tel Employé")
                dnom, dtel = st.text_input("Démarcheur"), st.text_input("Tel Démarcheur")
                if st.form_submit_button("VALIDER"):
                    dsor, total = dent + timedelta(days=nuits), nuits * PRIX_NUITEE
                    data = {
                        "id": str(uuid.uuid4())[:8], "Client_Nom": nom, "Date_Naissance": str(dnais), "Provenance": prov,
                        "Piece_Type": piece, "Piece_Num": pnum, "Tel_Client": tel, "Date_Entree": str(dent), "Date_Sortie": str(dsor),
                        "Raison": rais_s, "Appartement": app, "Employe_Nom": enom, "Employe_Tel": etel,
                        "Demarcheur_Nom": dnom if dnom else "Aucun", "Demarcheur_Tel": dtel if dtel else "Aucun",
                        "Montant_Total": total, "Commission": total*0.1 if dnom else 0, "Mois": dent.strftime("%m-%Y"), "Statut": "En cours"
                    }
                    if sauver(data, "sejours"): st.success("Enregistré !"); st.cache_data.clear(); st.rerun()

    # 3. DEPENSES & MAINTENANCE
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Saisir Dépense", "🛠️ Maintenance"])
        with tab1:
            with st.form("f_dep"):
                motif, mont = st.text_input("Motif"), st.number_input("Montant", min_value=0)
                cible = st.selectbox("Cible", ["Général"] + APPARTEMENTS)
                if st.form_submit_button("Sauver Dépense"):
                    sauver({"id":str(uuid.uuid4())[:8], "Date":str(date.today()), "Motif":motif, "Montant":mont, "Appartement":cible, "Mois":datetime.now(TZ_BF).strftime("%m-%Y")}, "depenses")
                    st.success("Dépense enregistrée"); st.cache_data.clear()
        with tab2:
            st.subheader("🛠️ État technique")
            app_m = st.selectbox("Appartement", APPARTEMENTS)
            stat_m = st.selectbox("Statut", ["Disponible", "Inaccessible"])
            rais_m = st.text_input("Raison de l'indisponibilité (ex: Clim gâtée)")
            if st.button("Mettre à jour la maintenance"):
                # Mise à jour avec Statut ET Raison
                res = requests.patch(f"{API_URL}/Appartement/{app_m}?sheet=maintenance", json={"data": {"Statut": stat_m, "Raison": rais_m}})
                if res.status_code not in [200, 204]:
                    sauver({"Appartement": app_m, "Statut": stat_m, "Raison": rais_m}, "maintenance")
                st.success("État mis à jour !"); st.cache_data.clear(); st.rerun()

    # 4. ADMINISTRATION
    elif menu == "ADMINISTRATION":
        if st.session_state.role != "admin": st.error("Accès Admin")
        else:
            onglet = st.selectbox("Table", ["sejours", "depenses", "maintenance"])
            df = charger(onglet)
            if not df.empty:
                st.dataframe(df)
                id_col = "Appartement" if onglet == "maintenance" else "id"
                sel = st.selectbox(f"Sélectionner pour suppression ({id_col})", df[id_col].tolist())
                if st.button("SUPPRIMER L'ENTRÉE"):
                    if supprimer_ligne(onglet, id_col, sel): st.success("Supprimé"); st.cache_data.clear(); st.rerun()

    # 5. RAPPORT PDF
    elif menu == "RAPPORT PDF":
        if st.session_state.role != "admin": st.error("Accès Admin")
        else:
            st.header("📈 Suivi Financier et Bilans")
            df_s, df_d = charger("sejours"), charger("depenses")
            if not df_s.empty:
                mois_list = sorted(df_s["Mois"].unique(), reverse=True)
                sel_m = st.selectbox("Sélectionner le mois", mois_list)
                s_m = df_s[df_s["Mois"] == sel_m]
                d_m = df_d[df_d["Mois"] == sel_m] if not df_d.empty else pd.DataFrame()
                ca = pd.to_numeric(s_m["Montant_Total"]).sum()
                com = pd.to_numeric(s_m["Commission"]).sum()
                dep = pd.to_numeric(d_m["Montant"]).sum() if not d_m.empty else 0
                net = ca - com - dep
                
                st.subheader(f"Suivi financier : {sel_m}")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("CHIFFRE D'AFFAIRE", f"{ca:,.0f} F")
                m2.metric("COMMISSIONS", f"{com:,.0f} F")
                m3.metric("DÉPENSES", f"{dep:,.0f} F")
                m4.metric("MONTANT NET", f"{net:,.0f} F")

                st.divider()
                st.write("**DÉTAIL DES DÉPENSES :**")
                if not d_m.empty: st.table(d_m[["Date", "Motif", "Appartement", "Montant"]])
                pdf_bytes = imprimer_bilan(sel_m, ca, com, dep, net, d_m)
                st.download_button(f"📥 Télécharger BILAN OFFICIEL - {sel_m}", pdf_bytes, f"Bilan_{sel_m}.pdf")
