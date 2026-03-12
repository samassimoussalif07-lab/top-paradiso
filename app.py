import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from fpdf import FPDF
import uuid

# --- CONFIGURATION ---
API_URL = "https://sheetdb.io/api/v1/in9prjm4jds07" 
PRIX_NUITEE = 15000
APPARTEMENTS = ["Appart A1", "Appart A2", "Appart A3", "Appart A4"]

st.set_page_config(page_title="Gestion Résidence VIP", layout="wide")

# --- FONCTIONS API ---
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}")
        return pd.DataFrame(r.json())
    except: return pd.DataFrame()

def sauver(ligne, onglet):
    return requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]})

def maj(onglet, col_recherche, valeur_recherche, donnee):
    return requests.patch(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}", json={"data": donnee})

def sup(onglet, col_recherche, valeur_recherche):
    return requests.delete(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}")

# --- UTILITAIRES ---
def to_n(val):
    try: return float(pd.to_numeric(val, errors='coerce'))
    except: return 0.0

# --- GÉNÉRATION DU PDF ---
def imprimer_bilan(mois, df_s, df_d, ca, comm, dep, net):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"BILAN MENSUEL - {mois}", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(10)
    pdf.cell(0, 10, f"Chiffre d'Affaires : {ca:,.0f} F", ln=True)
    pdf.cell(0, 10, f"Frais Demarcheurs : {comm:,.0f} F", ln=True)
    pdf.cell(0, 10, f"Depenses Totales : {dep:,.0f} F", ln=True)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"MONTANT RESTANT : {net:,.0f} F", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 10, "Details des Depenses :", ln=True)
    pdf.set_font("Arial", "", 9)
    for _, r in df_d.iterrows():
        pdf.cell(0, 7, f"- {r['Date']} : {r['Motif']} ({r['Appartement']}) = {r['Montant']} F", ln=True)
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
        df_s = charger("sejours")
        df_m = charger("maintenance")
        cols = st.columns(4)
        for i, app in enumerate(APPARTEMENTS):
            with cols[i]:
                # Vérifier maintenance
                m_info = df_m[df_m["Appartement"] == app]
                if not m_info.empty and m_info.iloc[0]["Statut"] == "Inaccessible":
                    st.error(f"**{app}**\n\n❌ INACCESSIBLE\n\nMotif: {m_info.iloc[0]['Raison']}")
                elif not df_s.empty and app in df_s[df_s["Statut"] == "En cours"]["Appartement"].tolist():
                    st.warning(f"**{app}**\n\n🔴 OCCUPÉ")
                else:
                    st.success(f"**{app}**\n\n🟢 LIBRE")

    # 2. ENREGISTREMENT CLIENT
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
                dsor = st.date_input("Date Sortie (si prévue)", value=date.today())
                raison = st.text_input("Raison du séjour")
                enom = st.text_input("Employé de garde")
                etel = st.text_input("Tel Employé")
            
            st.subheader("🤝 Démarcheur")
            dem_nom = st.text_input("Nom Démarcheur")
            dem_tel = st.text_input("Tel Démarcheur")

            if st.form_submit_button("VALIDER"):
                # Calcul auto
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
                st.success(f"✅ Enregistré ! Montant total calculé : {total:,} F")

    # 3. RÉSERVATIONS
    elif menu == "Réservations":
        st.header("📅 Gestion des Réservations")
        with st.form("Resa"):
            res_cli = st.text_input("Référence/Nom Client")
            res_app = st.selectbox("Appartement", APPARTEMENTS)
            res_date = st.date_input("Date de séjour prévue")
            if st.form_submit_button("Enregistrer Réservation"):
                sauver({"id": str(uuid.uuid4())[:8], "Client_Ref": res_cli, "Appartement": res_app, "Date_Reservation": str(date.today()), "Date_Prevue": str(res_date)}, "reservations")
                st.success("Réservation ajoutée.")

    # 4. DÉPENSES & MAINTENANCE
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Saisir Dépense", "🛠️ État Appartement"])
        with tab1:
            with st.form("Dep"):
                d_motif = st.text_input("Motif dépense (Libre)")
                d_mont = st.number_input("Montant", min_value=0)
                d_app = st.selectbox("Concerne quel appartement ?", ["Général"] + APPARTEMENTS)
                d_emp = st.text_input("Employé qui effectue la dépense")
                if st.form_submit_button("Enregistrer Dépense"):
                    sauver({"id": str(uuid.uuid4())[:8], "Date": str(date.today()), "Motif": d_motif, "Montant": d_mont, "Appartement": d_app, "Employe": d_emp, "Mois": date.today().strftime("%m-%Y")}, "depenses")
                    st.success("Dépense enregistrée.")
        with tab2:
            st.subheader("Signaler un appartement inaccessible")
            app_m = st.selectbox("Appartement", APPARTEMENTS, key="m1")
            stat_m = st.selectbox("Statut", ["Disponible", "Inaccessible"])
            rais_m = st.text_input("Raison (ex: Maintenance, dégât des eaux...)")
            if st.button("Mettre à jour l'état"):
                maj("maintenance", "Appartement", app_m, {"Statut": stat_m, "Raison": rais_m})
                st.success("État mis à jour.")

    # 5. MODIFICATIONS (ADMIN SEUL)
    elif menu == "MODIFICATIONS (Admin)":
        if st.session_state.role != "admin": st.error("Accès réservé")
        else:
            st.header("🛠️ Correction des erreurs")
            target = st.selectbox("Onglet à modifier", ["sejours", "reservations", "depenses"])
            df_edit = charger(target)
            if not df_edit.empty:
                col_id = "Client_Nom" if target == "sejours" else "id"
                sel_id = st.selectbox("Choisir l'élément à modifier", df_edit[col_id].tolist())
                
                with st.form("EditForm"):
                    st.write(f"Modification de {sel_id}")
                    # Ici l'admin peut corriger les champs clés
                    new_app = st.selectbox("Appartement", APPARTEMENTS)
                    new_mnt = st.number_input("Corriger Montant", value=0)
                    if st.form_submit_button("Appliquer Correction"):
                        maj(target, col_id, sel_id, {"Appartement": new_app, "Montant_Total": new_mnt} if target == "sejours" else {"Montant": new_mnt})
                        st.success("Correction effectuée.")
                
                if st.button("🗑️ SUPPRIMER DÉFINITIVEMENT"):
                    sup(target, col_id, sel_id)
                    st.error("Élément supprimé.")
                    st.rerun()

    # 6. RAPPORTS PDF (ADMIN SEUL)
    elif menu == "RAPPORTS PDF (Admin)":
        st.header("📊 Rapports de Fin de Mois")
        df_s = charger("sejours")
        df_d = charger("depenses")
        if not df_s.empty:
            mois_sel = st.selectbox("Mois du rapport", df_s["Mois"].unique())
            s_m = df_s[df_s["Mois"] == mois_sel]
            d_m = df_d[df_d["Mois"] == mois_sel] if not df_d.empty else pd.DataFrame()
            
            # Calculs
            for c in ["Montant_Total", "Commission", "Nuits"]: s_m[c] = pd.to_numeric(s_m[c], errors='coerce').fillna(0)
            if not d_m.empty: d_m["Montant"] = pd.to_numeric(d_m["Montant"], errors='coerce').fillna(0)
            
            ca_total = s_m["Montant_Total"].sum()
            com_total = s_m["Commission"].sum()
            dep_total = d_m["Montant"].sum() if not d_m.empty else 0
            net = ca_total - com_total - dep_total
            
            st.subheader(f"Bénéfice Net : {net:,.0f} F")
            
            # Affichage des stats demandées
            st.write("**Détails par appartement :**")
            stats = s_m.groupby("Appartement").agg({"Montant_Total": "sum", "Commission": "sum"}).rename(columns={"Montant_Total": "CA Brut", "Commission": "Frais Démarcheur"})
            st.table(stats)
            
            # Bouton PDF
            pdf_data = imprimer_bilan(mois_sel, s_m, d_m, ca_total, com_total, dep_total, net)
            st.download_button(f"📥 Télécharger Bilan {mois_sel} (PDF)", pdf_data, f"Bilan_{mois_sel}.pdf", "application/pdf")
