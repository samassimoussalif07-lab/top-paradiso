import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from fpdf import FPDF
import uuid

# --- CONFIGURATION ---
# REMPLACEZ PAR VOTRE LIEN RÉEL
API_URL = "https://sheetdb.io/api/v1/pext6md8mdy32" 
PRIX_NUITEE = 15000
APPARTEMENTS = ["Appart A1", "Appart A2", "Appart A3", "Appart A4"]

st.set_page_config(page_title="Gestion Résidence VIP", layout="wide")

# --- FONCTIONS API ---
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}")
        data = r.json()
        if not data or "error" in data: return pd.DataFrame()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def sauver(ligne, onglet):
    # Envoi des données vers SheetDB
    return requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]})

def maj(onglet, col_recherche, valeur_recherche, donnee):
    return requests.patch(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}", json={"data": donnee})

def sup(onglet, col_recherche, valeur_recherche):
    return requests.delete(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}")

# --- FONCTION PDF CORRIGÉE ---
def imprimer_bilan(mois_nom, df_s, df_d, ca, comm, dep, net):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"BILAN MENSUEL - {mois_nom}", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"CHIFFRE D'AFFAIRES BRUT : {ca:,.0f} F", ln=True)
    pdf.cell(0, 10, f"TOTAL COMMISSIONS DEMARCHEURS : {comm:,.0f} F", ln=True)
    pdf.cell(0, 10, f"TOTAL DEPENSES (CHARGES) : {dep:,.0f} F", ln=True)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(0, 100, 0)
    pdf.cell(0, 10, f"MONTANT NET RESTANT : {net:,.0f} F", ln=True)
    pdf.set_text_color(0, 0, 0)
    
    pdf.ln(10)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 10, "DETAIL DES DEPENSES DU MOIS :", ln=True)
    pdf.set_font("Arial", "", 10)
    
    if not df_d.empty:
        for _, r in df_d.iterrows():
            motif = str(r.get('Motif', 'Sans motif'))
            montant = str(r.get('Montant', '0'))
            app = str(r.get('Appartement', 'Général'))
            date_d = str(r.get('Date', ''))
            pdf.cell(0, 7, f"- {date_d} | {motif} ({app}) : {montant} F", ln=True)
    else:
        pdf.cell(0, 10, "Aucune depense enregistree pour ce mois.", ln=True)
        
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- AUTHENTIFICATION ---
if 'auth' not in st.session_state: st.session_state.auth, st.session_state.role = False, None

if not st.session_state.auth:
    st.title("🔐 Résidence - Accès Sécurisé")
    u = st.text_input("Utilisateur")
    p = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if u == "admin" and p == "patron2024": st.session_state.auth, st.session_state.role = True, "admin"; st.rerun()
        elif u == "employe" and p == "bienvenue": st.session_state.auth, st.session_state.role = True, "employe"; st.rerun()
        else: st.error("Identifiants incorrects")
else:
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Enregistrement Client", "Dépenses & Maintenance", "MODIFICATIONS (Admin)", "RAPPORTS PDF (Admin)"])
    if st.sidebar.button("Déconnexion"): st.session_state.auth = False; st.rerun()

    # 1. DASHBOARD
    if menu == "Dashboard":
        st.header("📊 État de la Résidence")
        df_s, df_m = charger("sejours"), charger("maintenance")
        cols = st.columns(4)
        for i, app in enumerate(APPARTEMENTS):
            with cols[i]:
                m_active = False
                if not df_m.empty and "Appartement" in df_m.columns:
                    m_info = df_m[df_m["Appartement"] == app]
                    if not m_info.empty and m_info.iloc[0].get("Statut") == "Inaccessible":
                        st.error(f"**{app}**\n\n❌ INACCESSIBLE\n\n{m_info.iloc[0].get('Raison', '')}")
                        m_active = True
                if not m_active:
                    occupe = False
                    if not df_s.empty and "Appartement" in df_s.columns and "Statut" in df_s.columns:
                        if app in df_s[df_s["Statut"] == "En cours"]["Appartement"].tolist():
                            st.warning(f"**{app}**\n\n🔴 OCCUPÉ")
                            occupe = True
                    if not occupe: st.success(f"**{app}**\n\n🟢 LIBRE")

    # 2. ENREGISTREMENT CLIENT
    elif menu == "Enregistrement Client":
        st.header("📝 Fiche Client")
        with st.form("Inscription"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom et Prénom")
                dnais = st.date_input("Date Naissance", min_value=date(1945,1,1), value=date(1990,1,1))
                prov = st.text_input("Provenance (Pays, Ville)")
                tel = st.text_input("Téléphone client")
                piece = st.selectbox("Pièce", ["CNI", "Passeport", "Permis", "Carte Séjour"])
                pnum = st.text_input("N° de Pièce")
            with c2:
                app = st.selectbox("Appartement", APPARTEMENTS)
                dent = st.date_input("Date Entrée")
                dsor = st.date_input("Date Sortie prévue")
                raison = st.text_input("Raison du séjour")
                enom = st.text_input("Employé de garde")
            
            dem_nom = st.text_input("Nom Démarcheur (Optionnel)")
            if st.form_submit_button("VALIDER L'ENREGISTREMENT"):
                nuits = max((dsor - dent).days, 1)
                total = nuits * PRIX_NUITEE
                comm = total * 0.10 if dem_nom else 0
                sauver({
                    "id": str(uuid.uuid4())[:8], "Client_Nom": nom, "Date_Naissance": str(dnais), "Provenance": prov,
                    "Piece_Type": piece, "Piece_Num": pnum, "Tel_Client": tel, "Date_Entree": str(dent),
                    "Date_Sortie": str(dsor), "Raison": raison, "Appartement": app, "Employe_Nom": enom,
                    "Demarcheur_Nom": dem_nom if dem_nom else "Aucun", "Montant_Total": total, "Commission": comm,
                    "Mois": dent.strftime("%m-%Y"), "Statut": "En cours"
                }, "sejours")
                st.success(f"✅ Enregistré ! Total : {total:,} F")

    # 3. DÉPENSES & MAINTENANCE
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Saisir Dépense", "🛠️ État Appartement"])
        with tab1:
            st.subheader("Nouvelle Dépense")
            with st.form("form_dep"):
                motif = st.text_input("Motif de la dépense (ex: Electricité, détergent...)")
                montant = st.number_input("Montant de la dépense (F)", min_value=0)
                cible = st.selectbox("Appartement concerné", ["Général"] + APPARTEMENTS)
                responsable = st.text_input("Employé responsable")
                if st.form_submit_button("ENREGISTRER LA DÉPENSE"):
                    # Formatage du mois identique au séjour pour le filtrage
                    mois_actuel = date.today().strftime("%m-%Y")
                    sauver({
                        "id": str(uuid.uuid4())[:8], 
                        "Date": str(date.today()), 
                        "Motif": motif, 
                        "Montant": montant, 
                        "Appartement": cible, 
                        "Employe": responsable, 
                        "Mois": mois_actuel
                    }, "depenses")
                    st.success(f"✅ Dépense de {montant} F enregistrée dans Excel !")

        with tab2:
            st.subheader("Maintenance")
            app_m = st.selectbox("Appartement", APPARTEMENTS)
            stat_m = st.selectbox("Statut", ["Disponible", "Inaccessible"])
            rais_m = st.text_input("Raison")
            if st.button("Mettre à jour l'état"):
                df_c = charger("maintenance")
                if not df_c.empty and "Appartement" in df_c.columns and app_m in df_c["Appartement"].tolist():
                    maj("maintenance", "Appartement", app_m, {"Statut": stat_m, "Raison": rais_m})
                else: sauver({"Appartement": app_m, "Statut": stat_m, "Raison": rais_m}, "maintenance")
                st.success("État mis à jour.")

    # 4. MODIFICATIONS (ADMIN)
    elif menu == "MODIFICATIONS (Admin)":
        if st.session_state.role != "admin": st.error("Accès réservé")
        else:
            st.header("⚙️ Administration des données")
            target = st.selectbox("Choisir l'onglet", ["sejours", "depenses"])
            df_edit = charger(target)
            if not df_edit.empty:
                col_id = "Client_Nom" if target == "sejours" else "Motif"
                sel = st.selectbox("Élément à modifier", df_edit[col_id].tolist())
                if st.button("🗑️ SUPPRIMER CET ÉLÉMENT"):
                    sup(target, col_id, sel)
                    st.error("Supprimé.")
                    st.rerun()

    # 5. RAPPORTS PDF (ADMIN)
    elif menu == "RAPPORTS PDF (Admin)":
        st.header("📊 Rapports PDF Mensuels")
        df_s, df_d = charger("sejours"), charger("depenses")
        
        if not df_s.empty:
            mois_disponibles = df_s["Mois"].unique()
            mois_sel = st.selectbox("Sélectionner le mois", mois_disponibles)
            
            # Filtrage des séjours et dépenses par mois
            s_m = df_s[df_s["Mois"] == mois_sel]
            d_m = df_d[df_d["Mois"] == mois_sel] if not df_d.empty else pd.DataFrame()
            
            # Calculs financiers
            for c in ["Montant_Total", "Commission"]: s_m[c] = pd.to_numeric(s_m[c], errors='coerce').fillna(0)
            if not d_m.empty: d_m["Montant"] = pd.to_numeric(d_m["Montant"], errors='coerce').fillna(0)
            
            ca, com = s_m["Montant_Total"].sum(), s_m["Commission"].sum()
            dep = d_m["Montant"].sum() if not d_m.empty else 0
            net = ca - com - dep
            
            st.subheader(f"Bilan {mois_sel}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Revenus Bruts", f"{ca:,.0f} F")
            c2.metric("Dépenses", f"{dep:,.0f} F")
            c3.metric("Net Restant", f"{net:,.0f} F")

            # Bouton PDF
            pdf_bytes = imprimer_bilan(mois_sel, s_m, d_m, ca, com, dep, net)
            st.download_button(f"📥 Télécharger le Rapport PDF ({mois_sel})", pdf_bytes, f"Bilan_{mois_sel}.pdf", "application/pdf")
