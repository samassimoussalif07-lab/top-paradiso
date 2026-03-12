import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from fpdf import FPDF
import uuid

# --- CONFIGURATION ---
# REMPLACEZ PAR VOTRE LIEN RÉEL SHEETDB
API_URL = "https://sheetdb.io/api/v1/2a307403dpyom" 
PRIX_NUITEE = 15000
APPARTEMENTS = ["Appart A1", "Appart A2", "Appart A3", "Appart A4"]

st.set_page_config(page_title="Gestion Résidence VIP", layout="wide")

# --- FONCTIONS API ---
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}")
        if r.status_code == 200:
            data = r.json()
            return pd.DataFrame(data)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def sauver(ligne, onglet):
    try:
        r = requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]})
        return r.status_code == 201
    except:
        return False

def maj(onglet, col_recherche, valeur_recherche, donnee):
    return requests.patch(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}", json={"data": donnee})

def sup(onglet, col_recherche, valeur_recherche):
    return requests.delete(f"{API_URL}/{col_recherche}/{valeur_recherche}?sheet={onglet}")

# --- GÉNÉRATEUR PDF ---
def imprimer_bilan(mois_nom, df_s, df_d, ca, comm, dep, net):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"BILAN MENSUEL - {mois_nom}", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"CHIFFRE D'AFFAIRES BRUT : {int(ca):,} F", ln=True)
    pdf.cell(0, 10, f"TOTAL COMMISSIONS : {int(comm):,} F", ln=True)
    pdf.cell(0, 10, f"TOTAL DEPENSES : {int(dep):,} F", ln=True)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"MONTANT NET RESTANT : {int(net):,} F", ln=True)
    
    pdf.ln(10)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 10, "DETAIL DES DEPENSES :", ln=True)
    pdf.set_font("Arial", "", 10)
    
    if not df_d.empty:
        for _, r in df_d.iterrows():
            pdf.cell(0, 7, f"- {r.get('Date','')} | {r.get('Motif','')} ({r.get('Appartement','')}) : {r.get('Montant','0')} F", ln=True)
    else:
        pdf.cell(0, 10, "Aucune depense ce mois-ci.", ln=True)
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- AUTHENTIFICATION ---
if 'auth' not in st.session_state: st.session_state.auth, st.session_state.role = False, None

if not st.session_state.auth:
    st.title("🔐 Résidence VIP - Connexion")
    u = st.text_input("Identifiant")
    p = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if u == "admin" and p == "patron2024": st.session_state.auth, st.session_state.role = True, "admin"; st.rerun()
        elif u == "employe" and p == "bienvenue": st.session_state.auth, st.session_state.role = True, "employe"; st.rerun()
        else: st.error("Identifiants incorrects")
else:
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Enregistrement Client", "Dépenses & Maintenance", "ADMINISTRATION", "RAPPORT PDF"])
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
                        st.error(f"**{app}**\n\n❌ BLOQUÉ\n\n{m_info.iloc[0].get('Raison', '')}")
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
        st.header("📝 Nouveau Client")
        with st.form("Inscription"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom Complet")
                dnais = st.date_input("Date Naissance", min_value=date(1945,1,1))
                tel = st.text_input("Téléphone")
                piece = st.selectbox("Type Pièce", ["CNI", "Passeport", "Permis"])
                pnum = st.text_input("Numéro Pièce")
            with c2:
                app = st.selectbox("Appartement", APPARTEMENTS)
                dent = st.date_input("Date Arrivée")
                dsor = st.date_input("Date Départ")
                rais = st.text_input("Raison du séjour")
                enom = st.text_input("Employé")
            dem_nom = st.text_input("Démarcheur (Laisser vide si aucun)")
            
            if st.form_submit_button("VALIDER"):
                nuits = max((dsor - dent).days, 1)
                total = nuits * PRIX_NUITEE
                comm = total * 0.10 if dem_nom else 0
                success = sauver({
                    "id": str(uuid.uuid4())[:8], "Client_Nom": nom, "Date_Naissance": str(dnais),
                    "Tel_Client": tel, "Piece_Type": piece, "Piece_Num": pnum,
                    "Date_Entree": str(dent), "Date_Sortie": str(dsor), "Raison": rais,
                    "Appartement": app, "Employe_Nom": enom, "Demarcheur_Nom": dem_nom if dem_nom else "Aucun",
                    "Montant_Total": total, "Commission": comm, "Mois": dent.strftime("%m-%Y"), "Statut": "En cours"
                }, "sejours")
                if success: st.success("✅ Client enregistré dans Excel !")
                else: st.error("❌ Erreur de connexion au fichier Excel")

    # 3. DÉPENSES (PARTIE CRITIQUE)
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Saisir Dépense", "🛠️ Maintenance"])
        with tab1:
            st.subheader("Enregistrer un frais")
            with st.form("f_dep"):
                motif = st.text_input("Motif de la dépense")
                montant = st.number_input("Montant (F CFA)", min_value=0)
                cible = st.selectbox("Cible", ["Général"] + APPARTEMENTS)
                emp = st.text_input("Votre Nom")
                # Important: On fixe le mois sur la date du jour
                mois_dep = date.today().strftime("%m-%Y")
                
                if st.form_submit_button("ENREGISTRER DÉPENSE"):
                    if not motif or montant == 0:
                        st.warning("Veuillez remplir le motif et le montant")
                    else:
                        donnees = {
                            "id": str(uuid.uuid4())[:8],
                            "Date": str(date.today()),
                            "Motif": motif,
                            "Montant": montant,
                            "Appartement": cible,
                            "Employe": emp,
                            "Mois": mois_dep
                        }
                        resultat = sauver(donnees, "depenses")
                        if resultat:
                            st.success(f"✅ Dépense de {montant} F enregistrée avec succès !")
                        else:
                            st.error("❌ Échec de l'enregistrement. Vérifiez vos titres de colonnes dans l'onglet 'depenses'.")
        with tab2:
            st.subheader("État Appartement")
            app_m = st.selectbox("Appartement", APPARTEMENTS, key="am")
            stat_m = st.selectbox("Statut", ["Disponible", "Inaccessible"])
            rais_m = st.text_input("Raison si inaccessible")
            if st.button("Mettre à jour"):
                df_c = charger("maintenance")
                if not df_c.empty and "Appartement" in df_c.columns and app_m in df_c["Appartement"].tolist():
                    maj("maintenance", "Appartement", app_m, {"Statut": stat_m, "Raison": rais_m})
                else: sauver({"Appartement": app_m, "Statut": stat_m, "Raison": rais_m}, "maintenance")
                st.success("État mis à jour.")

    # 4. ADMINISTRATION
    elif menu == "ADMINISTRATION":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            st.header("⚙️ Gestion des erreurs")
            target = st.selectbox("Choisir l'onglet", ["sejours", "depenses", "reservations"])
            df_edit = charger(target)
            if not df_edit.empty:
                st.dataframe(df_edit)
                col_ref = "Client_Nom" if target == "sejours" else ("Motif" if target == "depenses" else "id")
                sel = st.selectbox("Élément à supprimer", df_edit[col_ref].tolist())
                if st.button("🗑️ SUPPRIMER"):
                    sup(target, col_ref, sel)
                    st.rerun()

    # 5. RAPPORT PDF
    elif menu == "RAPPORT PDF":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            st.header("📊 Bilan Mensuel")
            df_s, df_d = charger("sejours"), charger("depenses")
            if not df_s.empty:
                mois_list = df_s["Mois"].unique()
                sel_m = st.selectbox("Choisir le mois", mois_list)
                
                # Filtrage
                s_m = df_s[df_s["Mois"] == sel_m]
                d_m = df_d[df_d["Mois"] == sel_m] if not df_d.empty else pd.DataFrame()
                
                # Conversions
                for c in ["Montant_Total", "Commission"]: s_m[c] = pd.to_numeric(s_m[c], errors='coerce').fillna(0)
                if not d_m.empty: d_m["Montant"] = pd.to_numeric(d_m["Montant"], errors='coerce').fillna(0)
                
                ca = s_m["Montant_Total"].sum()
                com = s_m["Commission"].sum()
                dep = d_m["Montant"].sum() if not d_m.empty else 0
                net = ca - com - dep
                
                st.subheader(f"Bilan de {sel_m}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Revenus", f"{ca:,.0f} F")
                c2.metric("Commissions", f"{com:,.0f} F")
                c3.metric("Dépenses", f"{dep:,.0f} F")
                st.metric("NET RESTANT", f"{net:,.0f} F", delta_color="normal")
                
                # Liste des dépenses pour vérification visuelle
                if not d_m.empty:
                    st.write("**Liste des dépenses du mois :**")
                    st.table(d_m[["Date", "Motif", "Montant", "Appartement"]])
                
                pdf_bytes = imprimer_bilan(sel_m, s_m, d_m, ca, com, dep, net)
                st.download_button(f"📥 Télécharger PDF {sel_m}", pdf_bytes, f"Bilan_{sel_m}.pdf", "application/pdf")



