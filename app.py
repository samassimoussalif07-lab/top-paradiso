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
TZ_BF = pytz.timezone('Africa/Ouagadougou') # Fuseau horaire Burkina Faso

st.set_page_config(page_title="Gestion Résidence VIP", layout="wide")

# --- FONCTIONS API (AVEC CACHE POUR LA VITESSE) ---
@st.cache_data(ttl=10) # Rafraîchissement toutes les 10 secondes
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}", timeout=10)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def sauver(ligne, onglet):
    try:
        r = requests.post(f"{API_URL}?sheet={onglet}", json={"data": [ligne]}, timeout=10)
        return r.status_code == 201
    except:
        return False

# --- LOGIQUE DE DISPONIBILITÉ (REGLE 11H00) ---
def obtenir_etats():
    df_s = charger("sejours")
    df_m = charger("maintenance")
    now = datetime.now(TZ_BF)
    
    occupes = {}
    bloques = []

    # 1. Vérifier Maintenance
    if not df_m.empty:
        for _, row in df_m.iterrows():
            if row.get("Statut") == "Inaccessible":
                bloques.append(row.get("Appartement"))

    # 2. Vérifier Occupations (Sortie à 11h00)
    if not df_s.empty:
        # Filtrer uniquement ceux qui sont marqués "En cours"
        en_cours = df_s[df_s["Statut"] == "En cours"]
        for _, row in en_cours.iterrows():
            try:
                # On récupère la date de sortie prévue
                ds = row.get("Date_Sortie")
                # On crée l'heure de libération précise : Date de sortie à 11h00 AM
                heure_liberation = TZ_BF.localize(datetime.combine(datetime.strptime(ds, "%Y-%m-%d"), time(11, 0)))
                
                # Si l'heure actuelle est avant 11h00 le jour du départ, c'est occupé
                if now < heure_liberation:
                    occupes[row.get("Appartement")] = heure_liberation.strftime("%d/%m/%Y à 11:00")
            except:
                continue
    return bloques, occupes

# --- GÉNÉRATEUR PDF ---
def imprimer_bilan(mois_nom, ca, comm, dep, net):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"BILAN MENSUEL - {mois_nom}", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"CA BRUT : {int(ca):,} F", ln=True)
    pdf.cell(0, 10, f"COMMISSIONS : {int(comm):,} F", ln=True)
    pdf.cell(0, 10, f"DEPENSES : {int(dep):,} F", ln=True)
    pdf.cell(0, 10, f"NET : {int(net):,} F", ln=True)
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- AUTHENTIFICATION ---
if 'auth' not in st.session_state:
    st.session_state.auth, st.session_state.role = False, None

if not st.session_state.auth:
    st.title("🔐 Résidence VIP - Connexion")
    u = st.text_input("Identifiant")
    p = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if u == "admin" and p == "patron2024": st.session_state.auth, st.session_state.role = True, "admin"; st.rerun()
        elif u == "employe" and p == "bienvenue": st.session_state.auth, st.session_state.role = True, "employe"; st.rerun()
        else: st.error("Identifiants incorrects")
else:
    # Sidebar
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
                if app in bloques: st.error(f"**{app}**\n\n❌ BLOQUÉ")
                elif app in occupes: st.warning(f"**{app}**\n\n🔴 OCCUPÉ\n\nLibre : {occupes[app]}")
                else: st.success(f"**{app}**\n\n🟢 LIBRE")

    # 2. ENREGISTREMENT CLIENT
    elif menu == "Enregistrement Client":
        st.header("📝 Nouveau Client")
        # Filtrage : On n'affiche que les appartements qui ne sont ni bloqués ni occupés
        app_libres = [a for a in APPARTEMENTS if a not in bloques and a not in occupes]
        
        if not app_libres:
            st.warning("⚠️ Aucun appartement n'est libre pour le moment.")
        else:
            with st.form("Inscription"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    nom = st.text_input("Nom Complet")
                    dnais = st.date_input("Date Naissance", min_value=date(1940,1,1))
                    prov = st.text_input("Provenance")
                    tel = st.text_input("Téléphone Client")
                with c2:
                    piece = st.selectbox("Type Pièce", ["CNI", "Passeport", "Permis"])
                    pnum = st.text_input("Numéro Pièce")
                    app = st.selectbox("Appartement disponible", app_libres)
                    rais = st.text_input("Raison du séjour")
                with c3:
                    dent = st.date_input("Date d'Arrivée", value=date.today())
                    nuits = st.number_input("Nombre de nuits", min_value=1, step=1)
                    enom = st.text_input("Nom de l'Employé")
                    etel = st.text_input("Tel de l'Employé")
                
                col_d1, col_d2 = st.columns(2)
                with col_d1: dnom = st.text_input("Démarcheur (Si aucun, laisser vide)")
                with col_d2: dtel = st.text_input("Tel Démarcheur")

                if st.form_submit_button("VALIDER L'ENREGISTREMENT"):
                    # Calcul automatique de la sortie (Règle : lendemain 11h)
                    dsor = dent + timedelta(days=nuits)
                    total = nuits * PRIX_NUITEE
                    comm = total * 0.10 if dnom else 0
                    
                    # Correspondance exacte avec vos colonnes Excel
                    donnees = {
                        "id": str(uuid.uuid4())[:8],
                        "Client_Nom": nom,
                        "Date_Naissance": str(dnais),
                        "Provenance": prov,
                        "Piece_Type": piece,
                        "Piece_Num": pnum,
                        "Tel_Client": tel,
                        "Date_Entree": str(dent),
                        "Date_Sortie": str(dsor),
                        "Raison": rais,
                        "Appartement": app,
                        "Employe_Nom": enom,
                        "Employe_Tel": etel,
                        "Demarcheur_Nom": dnom if dnom else "Aucun",
                        "Demarcheur_Tel": dtel if dtel else "Aucun",
                        "Montant_Total": total,
                        "Commission": comm,
                        "Mois": dent.strftime("%m-%Y"),
                        "Statut": "En cours"
                    }
                    
                    if sauver(donnees, "sejours"):
                        st.success(f"✅ Enregistré ! Sortie prévue le {dsor.strftime('%d/%m/%Y')} à 11h00.")
                        st.cache_data.clear() # Vider le cache pour voir l'appartement occupé de suite
                        st.rerun()
                    else:
                        st.error("❌ Erreur API : Vérifiez que les titres des colonnes Excel sont corrects.")

    # 3. DÉPENSES
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Dépenses", "🛠️ Maintenance"])
        with tab1:
            with st.form("f_dep"):
                motif = st.text_input("Motif")
                montant = st.number_input("Montant", min_value=0)
                cible = st.selectbox("Cible", ["Général"] + APPARTEMENTS)
                emp = st.text_input("Votre Nom")
                if st.form_submit_button("Enregistrer"):
                    if sauver({"id":str(uuid.uuid4())[:8], "Date":str(date.today()), "Motif":motif, "Montant":montant, "Appartement":cible, "Employe":emp, "Mois":datetime.now(TZ_BF).strftime("%m-%Y")}, "depenses"):
                        st.success("Dépense notée.")
                        st.cache_data.clear()
        with tab2:
            st.subheader("Signaler une Maintenance")
            app_m = st.selectbox("Appartement", APPARTEMENTS, key="main_app")
            stat_m = st.selectbox("Action", ["Disponible", "Inaccessible"])
            if st.button("Confirmer Changement"):
                requests.patch(f"{API_URL}/Appartement/{app_m}?sheet=maintenance", json={"data": {"Statut": stat_m}})
                st.cache_data.clear()
                st.rerun()

    # 4. ADMINISTRATION
    elif menu == "ADMINISTRATION":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            df_s = charger("sejours")
            if not df_s.empty:
                st.dataframe(df_s)
                sel = st.selectbox("Sélectionner Nom Client pour SUPPRIMER", df_s["Client_Nom"].tolist())
                if st.button("🗑️ Supprimer cette ligne"):
                    requests.delete(f"{API_URL}/Client_Nom/{sel}?sheet=sejours")
                    st.cache_data.clear()
                    st.rerun()

    # 5. RAPPORT PDF
    elif menu == "RAPPORT PDF":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            df_s = charger("sejours")
            if not df_s.empty:
                sel_m = st.selectbox("Mois du bilan", df_s["Mois"].unique())
                # Filtrage simple pour calcul
                s_m = df_s[df_s["Mois"] == sel_m]
                ca = pd.to_numeric(s_m["Montant_Total"]).sum()
                com = pd.to_numeric(s_m["Commission"]).sum()
                st.metric("Chiffre d'Affaire", f"{ca} F")
                pdf_bytes = imprimer_bilan(sel_m, ca, com, 0, ca-com)
                st.download_button(f"📥 Télécharger Bilan {sel_m}", pdf_bytes, f"Bilan_{sel_m}.pdf")
