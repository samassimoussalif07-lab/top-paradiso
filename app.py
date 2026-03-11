import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from fpdf import FPDF

# --- CONFIGURATION ---
# REMPLACEZ PAR VOTRE LIEN SHEETDB
API_URL = "https://sheetdb.io/api/v1/VOTRE_CODE_ICI" 
LISTE_APPARTEMENTS = ["Appart A1", "Appart A2", "Appart A3", "Appart A4"]
PRIX_NUITEE = 15000

st.set_page_config(page_title="Top-Paradiso - GESTION TOTALE", layout="wide")

# --- FONCTIONS TECHNIQUES (API) ---
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}")
        return pd.DataFrame(r.json())
    except: return pd.DataFrame()

def sauver(ligne, onglet):
    return requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]})

def maj(cle_nom, donnee, onglet):
    return requests.patch(f"{API_URL}/Client_Nom/{cle_nom}?sheet={onglet}", json={"data": donnee})

def sup(cle_nom, onglet):
    return requests.delete(f"{API_URL}/Client_Nom/{cle_nom}?sheet={onglet}")

# --- NETTOYAGE DES CHIFFRES ---
def to_num(val):
    try:
        return float(pd.to_numeric(val, errors='coerce'))
    except:
        return 0.0

# --- GÉNÉRATION DU PDF ---
def generer_pdf(df_s, df_d, mois, ca, comm, dep, net):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"BILAN MENSUEL - {mois}", ln=True, align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(200, 10, "RESIDENCE TOP-PARADISO | DEPART LIMITE: 11H00", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "RESUME FINANCIER :", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"- Chiffre d'Affaires Brut : {ca:,.0f} F CFA", ln=True)
    pdf.cell(0, 8, f"- Total Commissions : {comm:,.0f} F CFA", ln=True)
    pdf.cell(0, 8, f"- Total Depenses : {dep:,.0f} F CFA", ln=True)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"- BENEFICE NET : {net:,.0f} F CFA", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "DETAIL DES SEJOURS :", ln=True)
    pdf.set_font("Arial", "", 9)
    for _, row in df_s.iterrows():
        pdf.cell(0, 7, f"{row['Appartement']} | {row['Client_Nom']} | Du {row['Date_Entree']} au {row['Date_Sortie']} (11h00) | CA: {row['Montant_Brut']} F", ln=True)
    
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- AUTHENTIFICATION ---
if 'auth' not in st.session_state: st.session_state.auth, st.session_state.role = False, None

if not st.session_state.auth:
    st.title("🔑 Top-Paradiso - Accès Réservé")
    with st.form("Login"):
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Se connecter"):
            if u == "admin" and p == "patron2024":
                st.session_state.auth, st.session_state.role = True, "admin"
                st.rerun()
            elif u == "employe" and p == "bienvenue":
                st.session_state.auth, st.session_state.role = True, "employe"
                st.rerun()
            else: st.error("Identifiants incorrects")
else:
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = st.sidebar.radio("Navigation", ["Tableau de Bord", "Enregistrement Client", "Saisir une Dépense", "MODIFIER / TOUT GÉRER (Admin)", "BILAN & PDF (Admin)"])
    if st.sidebar.button("Se déconnecter"): st.session_state.auth = False; st.rerun()

    # 1. TABLEAU DE BORD
    if menu == "Tableau de Bord":
        st.header("📊 État des Appartements")
        df_s = charger("sejours")
        occ = df_s["Appartement"].unique() if not df_s.empty else []
        cols = st.columns(4)
        for i, n in enumerate(LISTE_APPARTEMENTS):
            with cols[i]: st.metric(n, "🔴 OCCUPÉ" if n in occ else "🟢 LIBRE")

    # 2. ENREGISTREMENT (TOUS LES DÉTAILS DU CAHIER DE CHARGE)
    elif menu == "Enregistrement Client":
        st.header("📝 Fiche d'Enregistrement")
        with st.form("Inscription"):
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("👤 Client")
                nom = st.text_input("Nom et Prénom")
                tel = st.text_input("Téléphone")
                prov = st.text_input("Provenance (Pays/Ville)")
                dnais = st.date_input("Date Naissance", min_value=date(1915,1,1), value=date(1995,1,1))
                lnais = st.text_input("Lieu de Naissance")
                piece = st.text_input("Type et N° de pièce")
            with c2:
                st.subheader("🏠 Séjour")
                app = st.selectbox("Appartement", LISTE_APPARTEMENTS)
                d_e = st.date_input("Arrivée")
                d_s = st.date_input("Départ (11h00)")
                rais = st.text_area("Raison du séjour")
                gard = st.text_input("Employé de garde")
            
            st.divider()
            st.subheader("🤝 Démarcheur (Optionnel)")
            d_nom = st.text_input("Nom démarcheur")
            d_tel = st.text_input("Tel démarcheur")
            d_infos = st.text_input("Infos naissance / Pièce démarcheur")

            if st.form_submit_button("VALIDER L'ENREGISTREMENT"):
                if not nom: st.error("Le nom du client est obligatoire")
                else:
                    nuits = max((d_s - d_e).days, 1)
                    brut = nuits * PRIX_NUITEE
                    sauver({
                        "Client_Nom": nom, "Tel_Client": tel, "Provenance": prov, "Date_Naissance": str(dnais),
                        "Lieu_Naissance": lnais, "Piece_Num": piece, "Appartement": app, 
                        "Date_Entree": str(d_e), "Date_Sortie": str(d_s), "Raison": rais, 
                        "Employe_Garde": gard, "Montant_Brut": brut, "Commission": (brut*0.1) if d_nom else 0,
                        "Demarcheur_Nom": d_nom if d_nom else "Aucun", "Demarcheur_Tel": d_tel,
                        "Demarcheur_Infos": d_infos, "Mois": d_e.strftime("%B %Y")
                    }, "sejours")
                    st.success(f"✅ Enregistré ! Total : {brut:,} F (Départ à 11h00)")

    # 3. DÉPENSES
    elif menu == "Saisir une Dépense":
        st.header("💸 Enregistrer un Frais")
        with st.form("Depense_Form"):
            cible = st.selectbox("Cible", ["Général"] + LISTE_APPARTEMENTS)
            mont = st.number_input("Montant (F)", min_value=0)
            motif = st.text_input("Motif libre (ex: Réparation clim, Electricité, Abonnement TV...)")
            if st.form_submit_button("SAUVEGARDER LA DÉPENSE"):
                sauver({
                    "Date": str(date.today()), "Description": f"{motif} ({cible})", 
                    "Montant": mont, "Mois": date.today().strftime("%B %Y")
                }, "depenses")
                st.success("Dépense enregistrée sur Google Sheets.")

    # 4. MODIFIER / TOUT GÉRER (ADMIN SEUL)
    elif menu == "MODIFIER / TOUT GÉRER (Admin)":
        st.header("⚙️ Espace Correction Patron")
        df_s = charger("sejours")
        if not df_s.empty:
            sel_nom = st.selectbox("Choisir la fiche client à modifier", df_s["Client_Nom"].tolist())
            d = df_s[df_s["Client_Nom"] == sel_nom].iloc[0]
            
            with st.form("Modif_Pro"):
                st.write(f"Modification de : **{sel_nom}**")
                col1, col2 = st.columns(2)
                with col1:
                    m_nom = st.text_input("Nom Client", value=d["Client_Nom"])
                    m_tel = st.text_input("Téléphone", value=d["Tel_Client"])
                    m_app = st.selectbox("Appartement", LISTE_APPARTEMENTS, index=LISTE_APPARTEMENTS.index(d["Appartement"]) if d["Appartement"] in LISTE_APPARTEMENTS else 0)
                    m_ent = st.text_input("Date Entrée (AAAA-MM-JJ)", value=d["Date_Entree"])
                with col2:
                    m_sor = st.text_input("Date Sortie (AAAA-MM-JJ)", value=d["Date_Sortie"])
                    m_mnt = st.number_input("Montant Total (F)", value=int(to_num(d["Montant_Brut"])))
                    m_com = st.number_input("Commission Démarcheur", value=int(to_num(d["Commission"])))
                    m_gard = st.text_input("Employé de garde", value=d["Employe_Garde"])
                
                if st.form_submit_button("💾 ENREGISTRER LES CHANGEMENTS"):
                    maj(sel_nom, {
                        "Client_Nom": m_nom, "Tel_Client": m_tel, "Appartement": m_app,
                        "Date_Entree": m_ent, "Date_Sortie": m_sor, "Montant_Brut": m_mnt,
                        "Commission": m_com, "Employe_Garde": m_gard
                    }, "sejours")
                    st.success("Données mises à jour !"); st.rerun()
            
            st.divider()
            if st.button("🗑️ SUPPRIMER DÉFINITIVEMENT CETTE FICHE"):
                sup(sel_nom, "sejours")
                st.error("Fiche effacée !"); st.rerun()
        else: st.info("Aucune donnée à modifier.")

    # 5. BILAN AUTOMATIQUE & PDF (ADMIN SEUL)
    elif menu == "BILAN & PDF (Admin)":
        st.header("📊 Bilan Financier Mensuel Automatique")
        df_s = charger("sejours")
        df_d = charger("depenses")
        
        if not df_s.empty:
            # Nettoyage
            df_s["Montant_Brut"] = df_s["Montant_Brut"].apply(to_num)
            df_s["Commission"] = df_s["Commission"].apply(to_num)
            if not df_d.empty: df_d["Montant"] = df_d["Montant"].apply(to_num)
            
            mois_list = df_s["Mois"].unique()
            sel_mois = st.selectbox("Choisir le mois du bilan", mois_list)
            
            s_m = df_s[df_s["Mois"] == sel_mois]
            d_m = df_d[df_d["Mois"] == sel_mois] if not df_d.empty else pd.DataFrame()
            
            # Calculs
            ca_total = s_m["Montant_Brut"].sum()
            comm_total = s_m["Commission"].sum()
            dep_total = d_m["Montant"].sum() if not d_m.empty else 0
            net = ca_total - comm_total - dep_total
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("C.A. Brut", f"{ca_total:,.0f} F")
            c2.metric("Commissions", f"-{comm_total:,.0f} F")
            c3.metric("Dépenses", f"-{dep_total:,.0f} F")
            c4.metric("BÉNÉFICE NET", f"{net:,.0f} F", delta_color="normal")
            
            st.divider()
            st.subheader("Détails des séjours du mois")
            st.dataframe(s_m[["Appartement", "Client_Nom", "Date_Entree", "Date_Sortie", "Montant_Brut"]])
            
            # Bouton PDF
            pdf_out = generer_pdf(s_m, d_m, sel_mois, ca_total, comm_total, dep_total, net)
            st.download_button("📥 TÉLÉCHARGER LE BILAN PDF", pdf_out, f"Bilan_{sel_mois}.pdf", "application/pdf")
        else: st.info("Pas encore de données pour générer un bilan.")
