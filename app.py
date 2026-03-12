import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from fpdf import FPDF
import uuid

# --- CONFIGURATION ---
# REMPLACEZ PAR VOTRE LIEN RÉEL
API_URL = "https://sheetdb.io/api/v1/d2j1p5qefxvli" 
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
    return requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]})

def maj(onglet, col_recherche, valeur_recherche, donnee):
    return requests.patch(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}", json={"data": donnee})

def sup(onglet, col_recherche, valeur_recherche):
    return requests.delete(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}")

# --- FONCTION PDF ---
def imprimer_bilan(mois, df_s, df_d, ca, comm, dep, net):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"BILAN MENSUEL - {mois}", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(10)
    pdf.cell(0, 10, f"Chiffre d'Affaires Global : {ca:,.0f} F", ln=True)
    pdf.cell(0, 10, f"Total Frais Demarcheurs : {comm:,.0f} F", ln=True)
    pdf.cell(0, 10, f"Total Depenses : {dep:,.0f} F", ln=True)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"MONTANT NET RESTANT : {net:,.0f} F", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 10, "Detail des Depenses :", ln=True)
    pdf.set_font("Arial", "", 9)
    if not df_d.empty:
        for _, r in df_d.iterrows():
            pdf.cell(0, 7, f"- {r.get('Date','')} : {r.get('Motif','')} ({r.get('Appartement','')}) = {r.get('Montant','')} F", ln=True)
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
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Enregistrement Client", "Réservations", "Dépenses & Maintenance", "MODIFICATIONS (Admin)", "RAPPORTS PDF (Admin)"])
    if st.sidebar.button("Déconnexion"): st.session_state.auth = False; st.rerun()

    # 1. DASHBOARD
    if menu == "Dashboard":
        st.header("📊 État de la Résidence")
        df_s, df_m = charger("sejours"), charger("maintenance")
        cols = st.columns(4)
        for i, app in enumerate(APPARTEMENTS):
            with cols[i]:
                maintenance_active = False
                if not df_m.empty and "Appartement" in df_m.columns:
                    m_info = df_m[df_m["Appartement"] == app]
                    if not m_info.empty and m_info.iloc[0].get("Statut") == "Inaccessible":
                        st.error(f"**{app}**\n\n❌ INACCESSIBLE\n\nMotif: {m_info.iloc[0].get('Raison', 'Maintenance')}")
                        maintenance_active = True
                if not maintenance_active:
                    occupe = False
                    if not df_s.empty and "Appartement" in df_s.columns and "Statut" in df_s.columns:
                        if app in df_s[df_s["Statut"] == "En cours"]["Appartement"].tolist():
                            st.warning(f"**{app}**\n\n🔴 OCCUPÉ")
                            occupe = True
                    if not occupe: st.success(f"**{app}**\n\n🟢 LIBRE")

    # 2. ENREGISTREMENT
    elif menu == "Enregistrement Client":
        st.header("📝 Nouvelle Fiche Client")
        with st.form("Inscription"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom et Prénom")
                dnais = st.date_input("Date Naissance", min_value=date(1945,1,1), value=date(1990,1,1))
                prov = st.text_input("Provenance (Pays, Ville)")
                tel = st.text_input("Téléphone (avec indicatif)")
                piece = st.selectbox("Pièce", ["Passeport", "Permis", "Carte Séjour", "CNI"])
                pnum = st.text_input("N° de Pièce")
            with c2:
                app = st.selectbox("Appartement", APPARTEMENTS)
                dent = st.date_input("Date Entrée")
                dsor = st.date_input("Date Sortie (si prévue)")
                raison = st.text_input("Raison du séjour")
                enom = st.text_input("Employé de garde")
                etel = st.text_input("Tel Employé")
            st.subheader("🤝 Démarcheur")
            dem_nom = st.text_input("Nom Démarcheur")
            dem_tel = st.text_input("Tel Démarcheur")
            if st.form_submit_button("VALIDER"):
                nuits = max((dsor - dent).days, 1)
                total = nuits * PRIX_NUITEE
                comm = total * 0.10 if dem_nom else 0
                sauver({
                    "id": str(uuid.uuid4())[:8], "Client_Nom": nom, "Date_Naissance": str(dnais), "Provenance": prov,
                    "Piece_Type": piece, "Piece_Num": pnum, "Tel_Client": tel, "Date_Entree": str(dent),
                    "Date_Sortie": str(dsor), "Raison": raison, "Appartement": app, "Employe_Nom": enom,
                    "Employe_Tel": etel, "Demarcheur_Nom": dem_nom if dem_nom else "Aucun",
                    "Demarcheur_Tel": dem_tel, "Montant_Total": total, "Commission": comm,
                    "Mois": dent.strftime("%m-%Y"), "Statut": "En cours"
                }, "sejours")
                st.success(f"✅ Enregistré ! Total : {total:,} F")

    # 3. RÉSERVATIONS
    elif menu == "Réservations":
        st.header("📅 Réservations")
        with st.form("res"):
            r_nom = st.text_input("Nom/Réf Client")
            r_app = st.selectbox("Appartement", APPARTEMENTS)
            r_date = st.date_input("Date prévue")
            if st.form_submit_button("Réserver"):
                sauver({"id": str(uuid.uuid4())[:8], "Client_Ref": r_nom, "Appartement": r_app, "Date_Reservation": str(date.today()), "Date_Prevue": str(r_date)}, "reservations")
                st.success("Réservé.")

    # 4. DÉPENSES & MAINTENANCE
    elif menu == "Dépenses & Maintenance":
        t1, t2 = st.tabs(["💸 Dépenses", "🛠️ Maintenance"])
        with t1:
            with st.form("dep"):
                m_dep = st.text_input("Motif")
                v_dep = st.number_input("Montant", min_value=0)
                a_dep = st.selectbox("Cible", ["Général"] + APPARTEMENTS)
                e_dep = st.text_input("Employé")
                if st.form_submit_button("Sauver"):
                    sauver({"id": str(uuid.uuid4())[:8], "Date": str(date.today()), "Motif": m_dep, "Montant": v_dep, "Appartement": a_dep, "Employe": e_dep, "Mois": date.today().strftime("%m-%Y")}, "depenses")
                    st.success("Enregistré.")
        with t2:
            st.subheader("État Inaccessible")
            app_m = st.selectbox("Appartement", APPARTEMENTS)
            stat_m = st.selectbox("Statut", ["Disponible", "Inaccessible"])
            rais_m = st.text_input("Raison")
            if st.button("Valider État"):
                df_c = charger("maintenance")
                if not df_c.empty and "Appartement" in df_c.columns and app_m in df_c["Appartement"].tolist():
                    maj("maintenance", "Appartement", app_m, {"Statut": stat_m, "Raison": rais_m})
                else: sauver({"Appartement": app_m, "Statut": stat_m, "Raison": rais_m}, "maintenance")
                st.success("Mis à jour.")

    # 5. MODIFICATIONS (ADMIN)
    elif menu == "MODIFICATIONS (Admin)":
        if st.session_state.role != "admin": st.error("Réservé")
        else:
            st.header("⚙️ Modifications & Suppressions")
            target = st.selectbox("Cible", ["sejours", "reservations", "depenses"])
            df_edit = charger(target)
            if not df_edit.empty:
                col_ref = "Client_Nom" if target == "sejours" else "id"
                sel = st.selectbox("Élément", df_edit[col_ref].tolist())
                with st.form("edit"):
                    st.write(f"Edition de {sel}")
                    new_val = st.number_input("Corriger Montant", value=0)
                    if st.form_submit_button("Corriger"):
                        maj(target, col_ref, sel, {"Montant_Total": new_val} if target=="sejours" else {"Montant": new_val})
                        st.success("Corrigé.")
                if st.button("🗑️ SUPPRIMER"):
                    sup(target, col_ref, sel)
                    st.error("Supprimé.")
                    st.rerun()

    # 6. RAPPORTS PDF (ADMIN)
    elif menu == "RAPPORTS PDF (Admin)":
        st.header("📊 Rapports PDF de fin de mois")
        df_s, df_d = charger("sejours"), charger("depenses")
        if not df_s.empty:
            mois_sel = st.selectbox("Mois", df_s["Mois"].unique() if "Mois" in df_s.columns else [])
            if mois_sel:
                s_m = df_s[df_s["Mois"] == mois_sel]
                d_m = df_d[df_d["Mois"] == mois_sel] if not df_d.empty and "Mois" in df_d.columns else pd.DataFrame()
                
                # Calculs numériques
                for c in ["Montant_Total", "Commission"]: s_m[c] = pd.to_numeric(s_m[c], errors='coerce').fillna(0)
                if not d_m.empty: d_m["Montant"] = pd.to_numeric(d_m["Montant"], errors='coerce').fillna(0)
                
                ca, com = s_m["Montant_Total"].sum(), s_m["Commission"].sum()
                dep = d_m["Montant"].sum() if not d_m.empty else 0
                net = ca - com - dep
                
                st.metric("Bénéfice Net", f"{net:,.0f} F")
                st.write("**Récapitulatif par Appartement :**")
                stats = s_m.groupby("Appartement").agg({"Montant_Total": "sum", "Commission": "sum"})
                st.table(stats)
                
                # Bouton PDF
                pdf_bytes = imprimer_bilan(mois_sel, s_m, d_m, ca, com, dep, net)
                st.download_button(f"📥 Télécharger Rapport PDF {mois_sel}", pdf_bytes, f"Bilan_{mois_sel}.pdf", "application/pdf")
