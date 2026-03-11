import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from fpdf import FPDF

# --- CONFIGURATION API ---
# Remplacez bien par votre lien SheetDB
API_URL = "https://sheetdb.io/api/v1/in9prjm4jds07" 

st.set_page_config(page_title="Top-Paradiso - Gestion Professionnelle", layout="wide")

# --- FONCTIONS TECHNIQUES (NE PAS TOUCHER) ---
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}")
        data = r.json()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def sauver(ligne, onglet):
    return requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]})

def maj(cle, donnee, onglet):
    return requests.patch(f"{API_URL}/Client_Nom/{cle}?sheet={onglet}", json={"data": donnee})

def sup(cle, onglet):
    return requests.delete(f"{API_URL}/Client_Nom/{cle}?sheet={onglet}")

# --- FONCTION PDF ---
def generer_pdf(df_s, df_d, mois, stats):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"BILAN MENSUEL - {mois}", ln=True, align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(200, 10, "Residence Top-Paradiso | Depart limite: 11h00", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Synthese par Appartement :", ln=True)
    pdf.set_font("Arial", "", 10)
    for index, row in stats.iterrows():
        pdf.cell(0, 8, f"{index}: {row['Montant_Brut']} F encaisses ({row['Nuits']} nuits)", ln=True)
    return pdf.output(dest="S").encode("latin-1")

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

    # --- 1. TABLEAU DE BORD ---
    if menu == "Tableau de Bord":
        st.header("📊 État des Appartements")
        df_s = charger("sejours")
        occ = df_s["Appartement"].unique() if not df_s.empty else []
        cols = st.columns(4)
        for i, n in enumerate(["Appart A1", "Appart A2", "Appart A3", "Appart A4"]):
            with cols[i]: st.metric(n, "🔴 Occupé" if n in occ else "🟢 Libre")

    # --- 2. ENREGISTREMENT ---
    elif menu == "Enregistrement Client":
        st.header("📝 Nouvelle Fiche Client")
        with st.form("Inscription"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom et Prénom")
                tel = st.text_input("Téléphone")
                prov = st.text_input("Provenance")
                dnais = st.date_input("Date Naissance", min_value=date(1915,1,1), value=date(1995,1,1))
                piece = st.text_input("N° de pièce")
            with c2:
                app = st.selectbox("Appartement", ["Appart A1", "Appart A2", "Appart A3", "Appart A4"])
                dent = st.date_input("Arrivée")
                dsor = st.date_input("Départ (11h00)")
                gard = st.text_input("Employé de garde")
                dem = st.text_input("Démarcheur (Si aucun, vide)")
            
            # Champs demarcheur complets
            dtel = st.text_input("Tel Démarcheur")
            dpiece = st.text_input("Pièce Démarcheur")

            if st.form_submit_button("VALIDER L'ENREGISTREMENT"):
                nuits = max((dsor - dent).days, 1)
                brut = nuits * 15000
                sauver({
                    "Client_Nom": nom, "Tel_Client": tel, "Provenance": prov, "Piece_Num": piece,
                    "Appartement": app, "Date_Entree": str(dent), "Date_Sortie": str(dsor),
                    "Employe_Garde": gard, "Montant_Brut": brut, "Demarcheur_Nom": dem if dem else "Aucun",
                    "Commission": (brut*0.1) if dem else 0, "Mois": dent.strftime("%B %Y")
                }, "sejours")
                st.success(f"Enregistré ! Total : {brut:,} F")

    # --- 3. DÉPENSES ---
    elif menu == "Saisir une Dépense":
        st.header("💸 Sortie de Caisse")
        with st.form("Depense_Form"):
            app_d = st.selectbox("Concerne", ["Général", "Appart A1", "Appart A2", "Appart A3", "Appart A4"])
            mont = st.number_input("Montant", min_value=0)
            motif = st.text_input("Motif")
            if st.form_submit_button("Enregistrer la dépense"):
                sauver({"Date": str(date.today()), "Description": f"{motif} ({app_d})", "Montant": mont, "Mois": date.today().strftime("%B %Y")}, "depenses")
                st.success("Dépense enregistrée.")

    # --- 4. MODIFIER / GÉRER (ADMIN) - VERSION CORRIGÉE ---
    elif menu == "Modifier / Gérer (Admin)":
        st.header("⚙️ Espace Correction Patron")
        df = charger("sejours")
        if not df.empty:
            sel = st.selectbox("Choisir le client à corriger", df["Client_Nom"].tolist())
            d = df[df["Client_Nom"] == sel].iloc[0]
            
            # Sécurité pour les chiffres (évite le ValueError)
            def safe_int(val):
                try: return int(pd.to_numeric(val, errors='coerce'))
                except: return 0

            with st.form("Form_Correction"):
                st.write(f"Modification de : **{sel}**")
                new_app = st.selectbox("Appartement", ["Appart A1", "Appart A2", "Appart A3", "Appart A4"], 
                                      index=["Appart A1", "Appart A2", "Appart A3", "Appart A4"].index(d["Appartement"]) if d["Appartement"] in ["Appart A1", "Appart A2", "Appart A3", "Appart A4"] else 0)
                new_mnt = st.number_input("Corriger Montant", value=safe_int(d["Montant_Brut"]))
                new_com = st.number_input("Corriger Commission", value=safe_int(d["Commission"]))
                
                # Le bouton d'envoi doit être unique et clair
                submit = st.form_submit_button("💾 SAUVEGARDER LES MODIFICATIONS")
                
                if submit:
                    maj(sel, {"Appartement": new_app, "Montant_Brut": new_mnt, "Commission": new_com}, "sejours")
                    st.success("Modifié avec succès !"); st.rerun()
            
            st.divider()
            st.warning("Zone de suppression")
            if st.button("🗑️ SUPPRIMER TOTALEMENT CETTE FICHE"):
                sup(sel, "sejours")
                st.error("Fiche supprimée !"); st.rerun()
        else: st.info("Aucune donnée.")

    # --- 5. BILAN MENSUEL ---
    elif menu == "Bilan Mensuel (Admin)":
        st.header("📊 Bilan Financier")
        df_s = charger("sejours")
        df_d = charger("depenses")
        if not df_s.empty:
            # Nettoyage des données pour calcul
            df_s["Montant_Brut"] = pd.to_numeric(df_s["Montant_Brut"], errors='coerce').fillna(0)
            df_s["Commission"] = pd.to_numeric(df_s["Commission"], errors='coerce').fillna(0)
            
            mois = st.selectbox("Mois", df_s["Mois"].unique())
            s_m = df_s[df_s["Mois"] == mois]
            
            stats = s_m.groupby("Appartement").agg({"Montant_Brut": "sum", "Client_Nom": "count"}).rename(columns={"Client_Nom": "Séjours"})
            st.table(stats)
            
            ca = s_m["Montant_Brut"].sum()
            st.metric("Chiffre d'Affaires Brut", f"{ca:,} F CFA")
            
            pdf_data = generer_pdf(s_m, df_d, mois, stats)
            st.download_button("📥 Télécharger Rapport PDF", pdf_data, f"Bilan_{mois}.pdf", "application/pdf")

