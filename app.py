import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from fpdf import FPDF

# --- CONFIGURATION API ---
API_URL = "https://sheetdb.io/api/v1/in9prjm4jds07" 

st.set_page_config(page_title="Top-Paradiso - Gestion Intégrale", layout="wide")

# --- FONCTION PDF PRO ---
def generer_pdf(df_s, df_d, mois, bilan_stats):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"BILAN MENSUEL AUTOMATIQUE - {mois}", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(200, 10, "Residence Top-Paradiso | Départ limite: 11h00", ln=True, align="C")
    
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. Synthese par Appartement", ln=True)
    pdf.set_font("Arial", "", 9)
    for index, row in bilan_stats.iterrows():
        pdf.cell(0, 8, f"{index} : {row['Nuits']} nuits | CA: {row['Montant_Brut']} F | Com. Demarcheurs: {row['Commission']} F", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "2. Bilan Financier Final", ln=True)
    pdf.set_font("Arial", "", 10)
    rev = df_s["Montant_Brut"].sum()
    com = df_s["Commission"].sum()
    dep = df_d["Montant"].sum() if not df_d.empty else 0
    pdf.cell(0, 8, f"Chiffre d'Affaires Global : {rev:,} F CFA", ln=True)
    pdf.cell(0, 8, f"Total Commissions payees : {com:,} F CFA", ln=True)
    pdf.cell(0, 8, f"Total Depenses (Charges) : {dep:,} F CFA", ln=True)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 10, f"MONTANT NET RESTANT : {rev - com - dep:,} F CFA", ln=True)
    
    return pdf.output(dest="S").encode("latin-1")

# --- FONCTIONS API ---
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}")
        return pd.DataFrame(r.json())
    except: return pd.DataFrame()

def sauver(ligne, onglet):
    return requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]})

def maj(cle, donnee, onglet):
    return requests.patch(f"{API_URL}/Client_Nom/{cle}?sheet={onglet}", json={"data": donnee})

def sup(cle, onglet):
    return requests.delete(f"{API_URL}/Client_Nom/{cle}?sheet={onglet}")

# --- CONNEXION ---
if 'auth' not in st.session_state: st.session_state.auth, st.session_state.role = False, None

if not st.session_state.auth:
    st.title("🔑 Top-Paradiso - Connexion")
    u, p = st.text_input("Identifiant"), st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if u == "admin" and p == "patron2024": st.session_state.auth, st.session_state.role = True, "admin"; st.rerun()
        elif u == "employe" and p == "bienvenue": st.session_state.auth, st.session_state.role = True, "employe"; st.rerun()
        else: st.error("Identifiants incorrects")
else:
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = st.sidebar.radio("Navigation", ["Tableau de Bord", "Enregistrement Client", "Saisir une Dépense", "Modifier / Gérer (Admin)", "Bilan Mensuel (Admin)"])
    if st.sidebar.button("Déconnexion"): st.session_state.auth = False; st.rerun()

    # 1. TABLEAU DE BORD
    if menu == "Tableau de Bord":
        st.header("📊 État des Appartements")
        df_s = charger("sejours")
        occ = df_s["Appartement"].unique() if not df_s.empty else []
        cols = st.columns(4)
        for i, n in enumerate(["Appart A1", "Appart A2", "Appart A3", "Appart A4"]):
            with cols[i]: st.metric(n, "🔴 Occupé" if n in occ else "🟢 Libre")

    # 2. ENREGISTREMENT (COMPLET SELON CAHIER DE CHARGE)
    elif menu == "Enregistrement Client":
        st.header("📝 Fiche d'Enregistrement Complète")
        with st.form("F"):
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("👤 Le Client")
                nom = st.text_input("Nom et Prénom")
                tel = st.text_input("Téléphone")
                prov = st.text_input("Provenance (Pays/Ville)")
                dnais = st.date_input("Date Naissance", min_value=date(1915,1,1), value=date(1995,1,1))
                lnais = st.text_input("Lieu Naissance")
                piece = st.text_input("Type et N° de pièce d'identité")
                st.subheader("🛡️ Employé de garde")
                enom = st.text_input("Nom Employé")
                etel = st.text_input("Tel Employé")
            with c2:
                st.subheader("🏠 Le Séjour")
                app = st.selectbox("Appartement", ["Appart A1", "Appart A2", "Appart A3", "Appart A4"])
                dent = st.date_input("Arrivée")
                dsor = st.date_input("Départ prévu (11h00)")
                rais = st.text_area("Raison du séjour")
                st.subheader("🤝 Le Démarcheur (Si applicable)")
                dnom = st.text_input("Nom du démarcheur")
                dtel = st.text_input("Tel démarcheur")
                dnais_d = st.text_input("Date/Lieu Naissance démarcheur")
                dpie_d = st.text_input("N° Pièce démarcheur")
            
            if st.form_submit_button("VALIDER L'ENREGISTREMENT"):
                nuits = max((dsor - dent).days, 1)
                brut = nuits * 15000
                comm = (brut * 0.10) if dnom else 0
                sauver({
                    "Client_Nom": nom, "Tel_Client": tel, "Date_Naissance": str(dnais), "Lieu_Naissance": lnais,
                    "Provenance": prov, "Piece_Num": piece, "Appartement": app, "Date_Entree": str(dent),
                    "Date_Sortie": str(dsor), "Raison": rais, "Employe_Garde": enom, "Employe_Tel": etel,
                    "Nuits": nuits, "Montant_Brut": brut, "Commission": comm,
                    "Demarcheur_Nom": dnom if dnom else "Aucun", "Demarcheur_Tel": dtel,
                    "Demarcheur_Naissance": dnais_d, "Demarcheur_Piece": dpie_d,
                    "Mois": dent.strftime("%B %Y")
                }, "sejours")
                st.success(f"Enregistré ! Montant total : {brut:,} F (Départ 11h00)")

    # 3. DÉPENSES LIBRES
    elif menu == "Saisir une Dépense":
        st.header("💸 Sortie de Caisse")
        with st.form("D"):
            app_d = st.selectbox("Concerne quel appartement ?", ["Général", "Appart A1", "Appart A2", "Appart A3", "Appart A4"])
            mont = st.number_input("Montant de la dépense", min_value=0)
            motif = st.text_input("Motif libre (ex: Réparation clim, Canal+, Electricité...)")
            if st.form_submit_button("Enregistrer la dépense"):
                sauver({"Date": str(date.today()), "Description": f"{motif} ({app_d})", "Montant": mont, "Mois": date.today().strftime("%B %Y")}, "depenses")
                st.success("Dépense enregistrée.")

    # 4. MODIFIER / TOUT GÉRER (ADMIN)
    elif menu == "Modifier / Gérer (Admin)":
        st.header("⚙️ Espace Correction Patron")
        df = charger("sejours")
        if not df.empty:
            sel = st.selectbox("Choisir le client à corriger", df["Client_Nom"].tolist())
            d = df[df["Client_Nom"] == sel].iloc[0]
            with st.form("Edit"):
                new_app = st.selectbox("Appartement", ["Appart A1", "Appart A2", "Appart A3", "Appart A4"], index=0)
                new_mnt = st.number_input("Corriger Montant", value=int(d["Montant_Brut"]))
                new_com = st.number_input("Corriger Commission", value=int(d["Commission"]))
                st.info("Note: Pour changer d'autres infos, utilisez directement Google Sheets.")
                c_m, c_s = st.columns(2)
                if c_m.form_submit_button("💾 SAUVEGARDER"):
                    maj(sel, {"Appartement": new_app, "Montant_Brut": new_mnt, "Commission": new_com}, "sejours")
                    st.success("Modifié !"); st.rerun()
                if c_s.form_submit_button("🗑️ SUPPRIMER TOUT"):
                    sup(sel, "sejours"); st.error("Supprimé !"); st.rerun()

    # 5. BILAN MENSUEL AUTOMATIQUE (ADMIN)
    elif menu == "Bilan Mensuel (Admin)":
        st.header("📊 Bilan Automatique de Fin de Mois")
        df_s = charger("sejours")
        df_d = charger("depenses")
        if not df_s.empty:
            mois = st.selectbox("Sélectionner le mois", df_s["Mois"].unique())
            s_m = df_s[df_s["Mois"] == mois]
            d_m = df_d[df_d["Mois"] == mois] if not df_d.empty else pd.DataFrame()
            
            # Conversion numérique
            for c in ["Montant_Brut", "Commission", "Nuits"]: s_m[c] = pd.to_numeric(s_m[c])
            if not d_m.empty: d_m["Montant"] = pd.to_numeric(d_m["Montant"])
            
            # Synthese par appartement
            st.subheader("📉 Synthèse par Appartement")
            stats = s_m.groupby("Appartement").agg({
                "Nuits": "sum",
                "Montant_Brut": "sum",
                "Commission": "sum",
                "Client_Nom": "count"
            }).rename(columns={"Client_Nom": "Nombre Séjours"})
            st.table(stats)
            
            # Bilan Financier
            st.subheader("💰 Bilan Financier Global")
            ca = s_m["Montant_Brut"].sum()
            com = s_m["Commission"].sum()
            dep = d_m["Montant"].sum() if not d_m.empty else 0
            net = ca - com - dep
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("C.A. Brut", f"{ca:,} F")
            c2.metric("Commissions", f"-{com:,} F")
            c3.metric("Dépenses", f"-{dep:,} F")
            c4.metric("BÉNÉFICE NET", f"{net:,} F", delta_color="normal")
            
            # Bouton PDF
            pdf_data = generer_pdf(s_m, d_m, mois, stats)
            st.download_button("📥 Télécharger le Bilan PDF", pdf_data, f"Bilan_{mois}.pdf", "application/pdf")
        else: st.info("Aucune donnée disponible.")
