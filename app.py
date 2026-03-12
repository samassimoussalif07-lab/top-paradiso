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
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}")
        if r.status_code == 200: return pd.DataFrame(r.json())
        return pd.DataFrame()
    except: return pd.DataFrame()

def sauver(ligne, onglet):
    try:
        r = requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]})
        return r.status_code == 201
    except: return False

def maj(onglet, col_recherche, valeur_recherche, donnee):
    return requests.patch(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}", json={"data": donnee})

def sup(onglet, col_recherche, valeur_recherche):
    return requests.delete(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}")

# --- LOGIQUE D'ÉTAT (LIBÉRATION AUTOMATIQUE À 11H00) ---
def obtenir_etats():
    df_s = charger("sejours")
    df_m = charger("maintenance")
    now = datetime.now(TZ_BF)
    
    occupes = {}
    bloques = []

    if not df_m.empty:
        for _, row in df_m.iterrows():
            if row.get("Statut") == "Inaccessible": bloques.append(row["Appartement"])

    if not df_s.empty:
        for _, row in df_s.iterrows():
            if row.get("Statut") == "En cours":
                try:
                    # La sortie est toujours à 11h00 à la date prévue
                    date_sortie_dt = datetime.strptime(row["Date_Sortie"], "%Y-%m-%d")
                    heure_liberation = TZ_BF.localize(datetime.combine(date_sortie_dt, time(11, 0)))
                    
                    if now < heure_liberation:
                        occupes[row["Appartement"]] = heure_liberation.strftime("%d/%m/%Y à 11:00")
                except: continue
    return bloques, occupes

# --- GÉNÉRATEUR PDF ---
def imprimer_bilan(mois_nom, df_s, df_d, ca, comm, dep, net):
    pdf = FPDF()
    pdf.add_page(); pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"BILAN MENSUEL - {mois_nom}", ln=True, align="C")
    pdf.ln(10); pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"CHIFFRE D'AFFAIRES BRUT : {int(ca):,} F", ln=True)
    pdf.cell(0, 10, f"TOTAL COMMISSIONS : {int(comm):,} F", ln=True)
    pdf.cell(0, 10, f"TOTAL DEPENSES : {int(dep):,} F", ln=True)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"MONTANT NET RESTANT : {int(net):,} F", ln=True)
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- AUTHENTIFICATION ---
if 'auth' not in st.session_state: st.session_state.auth, st.session_state.role = False, None

if not st.session_state.auth:
    st.title("🔐 Résidence VIP - Connexion")
    u, p = st.text_input("Identifiant"), st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if u == "admin" and p == "patron2024": st.session_state.auth, st.session_state.role = True, "admin"; st.rerun()
        elif u == "employe" and p == "bienvenue": st.session_state.auth, st.session_state.role = True, "employe"; st.rerun()
        else: st.error("Identifiants incorrects")
else:
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    st.sidebar.info(f"🇧🇫 Heure Ouaga : {datetime.now(TZ_BF).strftime('%H:%M')}")
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Enregistrement Client", "Dépenses & Maintenance", "ADMINISTRATION", "RAPPORT PDF"])
    if st.sidebar.button("Déconnexion"): st.session_state.auth = False; st.rerun()

    bloques, occupes = obtenir_etats()

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
        app_disponibles = [a for a in APPARTEMENTS if a not in bloques and a not in occupes]
        
        if not app_disponibles:
            st.warning("⚠️ Aucun appartement disponible.")
        else:
            with st.form("Inscription"):
                c1, c2 = st.columns(2)
                with c1:
                    nom = st.text_input("Nom Complet")
                    dnais = st.date_input("Date Naissance", min_value=date(1945,1,1))
                    tel = st.text_input("Téléphone")
                    piece = st.selectbox("Type Pièce", ["CNI", "Passeport", "Permis"])
                    pnum = st.text_input("Numéro Pièce")
                with c2:
                    app = st.selectbox("Appartement Disponible", app_disponibles)
                    dent = st.date_input("Date d'arrivée", value=date.today())
                    nb_nuits = st.number_input("Nombre de nuits", min_value=1, step=1)
                    rais = st.text_input("Raison du séjour")
                    enom = st.text_input("Votre Nom (Employé)")
                dem_nom = st.text_input("Démarcheur (Laisser vide si aucun)")
                
                # Calcul automatique de la sortie
                date_sortie_calculee = dent + timedelta(days=nb_nuits)
                
                if st.form_submit_button("VALIDER"):
                    total = nb_nuits * PRIX_NUITEE
                    comm = total * 0.10 if dem_nom else 0
                    
                    success = sauver({
                        "id": str(uuid.uuid4())[:8], "Client_Nom": nom, "Date_Naissance": str(dnais),
                        "Tel_Client": tel, "Piece_Type": piece, "Piece_Num": pnum,
                        "Date_Entree": str(dent), "Date_Sortie": str(date_sortie_calculee), 
                        "Raison": rais, "Appartement": app, "Employe_Nom": enom, 
                        "Demarcheur_Nom": dem_nom if dem_nom else "Aucun",
                        "Montant_Total": total, "Commission": comm, 
                        "Mois": dent.strftime("%m-%Y"), "Statut": "En cours"
                    }, "sejours")
                    
                    if success: 
                        st.success(f"✅ Enregistré ! Sortie prévue le {date_sortie_calculee.strftime('%d/%m/%Y')} à 11:00")
                        st.rerun()
                    else: st.error("❌ Erreur API")

    # 3. DÉPENSES
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Saisir Dépense", "🛠️ Maintenance"])
        with tab1:
            with st.form("f_dep"):
                motif, montant = st.text_input("Motif"), st.number_input("Montant", min_value=0)
                cible, emp = st.selectbox("Cible", ["Général"] + APPARTEMENTS), st.text_input("Nom")
                if st.form_submit_button("ENREGISTRER"):
                    sauver({"id": str(uuid.uuid4())[:8], "Date": str(date.today()), "Motif": motif, "Montant": montant, "Appartement": cible, "Employe": emp, "Mois": datetime.now(TZ_BF).strftime("%m-%Y")}, "depenses")
                    st.success("Dépense enregistrée.")
        with tab2:
            app_m = st.selectbox("Appartement", APPARTEMENTS)
            stat_m = st.selectbox("Statut", ["Disponible", "Inaccessible"])
            rais_m = st.text_input("Raison")
            if st.button("Mettre à jour"):
                df_c = charger("maintenance")
                if not df_c.empty and "Appartement" in df_c.columns and app_m in df_c["Appartement"].tolist():
                    maj("maintenance", "Appartement", app_m, {"Statut": stat_m, "Raison": rais_m})
                else: sauver({"Appartement": app_m, "Statut": stat_m, "Raison": rais_m}, "maintenance")
                st.rerun()

    # 4. ADMINISTRATION
    elif menu == "ADMINISTRATION":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            target = st.selectbox("Onglet", ["sejours", "depenses"])
            df_edit = charger(target)
            if not df_edit.empty:
                st.dataframe(df_edit)
                sel = st.selectbox("Supprimer", df_edit.iloc[:, 0].tolist())
                if st.button("🗑️ SUPPRIMER"):
                    sup(target, "id" if target=="depenses" else "Client_Nom", sel)
                    st.rerun()

    # 5. RAPPORT PDF
    elif menu == "RAPPORT PDF":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            df_s, df_d = charger("sejours"), charger("depenses")
            if not df_s.empty:
                sel_m = st.selectbox("Mois", df_s["Mois"].unique())
                s_m = df_s[df_s["Mois"] == sel_m]
                d_m = df_d[df_d["Mois"] == sel_m] if not df_d.empty else pd.DataFrame()
                for c in ["Montant_Total", "Commission"]: s_m[c] = pd.to_numeric(s_m[c], errors='coerce').fillna(0)
                if not d_m.empty: d_m["Montant"] = pd.to_numeric(d_m["Montant"], errors='coerce').fillna(0)
                ca, com, dep = s_m["Montant_Total"].sum(), s_m["Commission"].sum(), (d_m["Montant"].sum() if not d_m.empty else 0)
                st.metric("NET", f"{ca - com - dep:,.0f} F")
                if st.download_button("📥 PDF", imprimer_bilan(sel_m, s_m, d_m, ca, com, dep, ca-com-dep), f"Bilan_{sel_m}.pdf"): pass
