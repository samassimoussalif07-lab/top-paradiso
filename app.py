import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time
from fpdf import FPDF
import uuid
import pytz  # Pour la gestion du fuseau horaire

# --- CONFIGURATION ---
API_URL = "https://sheetdb.io/api/v1/2a307403dpyom" 
PRIX_NUITEE = 15000
APPARTEMENTS = ["Appart A1", "Appart A2", "Appart A3", "Appart A4"]

# Configuration du fuseau horaire Burkina Faso (GMT)
TZ_BF = pytz.timezone('Africa/Ouagadougou')

st.set_page_config(page_title="Gestion Résidence VIP", layout="wide")

# --- FONCTIONS API ---
def charger(onglet):
    try:
        r = requests.get(f"{API_URL}?sheet={onglet}")
        if r.status_code == 200:
            return pd.DataFrame(r.json())
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

# --- LOGIQUE D'ÉTAT DES APPARTEMENTS ---
def obtenir_etats():
    df_s = charger("sejours")
    df_m = charger("maintenance")
    now = datetime.now(TZ_BF)
    
    occupes = {}
    bloques = []

    # 1. Vérifier la maintenance
    if not df_m.empty:
        for _, row in df_m.iterrows():
            if row.get("Statut") == "Inaccessible":
                bloques.append(row["Appartement"])

    # 2. Vérifier les occupations (Logique 11h00)
    if not df_s.empty:
        for _, row in df_s.iterrows():
            if row.get("Statut") == "En cours":
                try:
                    # On considère que la sortie est à 11h00 le jour indiqué
                    date_sortie = datetime.strptime(row["Date_Sortie"], "%Y-%m-%d")
                    heure_liberation = TZ_BF.localize(datetime.combine(date_sortie, time(11, 0)))
                    
                    if now < heure_liberation:
                        occupes[row["Appartement"]] = heure_liberation.strftime("%d/%m/%Y à 11:00")
                except:
                    continue
    
    return bloques, occupes

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
    # Affichage de l'heure locale au Burkina
    st.sidebar.info(f"🇧🇫 Heure locale : {datetime.now(TZ_BF).strftime('%H:%M')}")
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Enregistrement Client", "Dépenses & Maintenance", "ADMINISTRATION", "RAPPORT PDF"])
    if st.sidebar.button("Déconnexion"): st.session_state.auth = False; st.rerun()

    # Récupération des états en temps réel pour tout le monde
    bloques, occupes = obtenir_etats()

    # 1. DASHBOARD
    if menu == "Dashboard":
        st.header("📊 État de la Résidence")
        cols = st.columns(4)
        for i, app in enumerate(APPARTEMENTS):
            with cols[i]:
                if app in bloques:
                    st.error(f"**{app}**\n\n❌ MAINTENANCE")
                elif app in occupes:
                    st.warning(f"**{app}**\n\n🔴 OCCUPÉ\n\nLibre le : {occupes[app]}")
                else:
                    st.success(f"**{app}**\n\n🟢 LIBRE")

    # 2. ENREGISTREMENT CLIENT
    elif menu == "Enregistrement Client":
        st.header("📝 Nouveau Client")
        
        # Filtrage des appartements disponibles
        app_disponibles = [a for a in APPARTEMENTS if a not in bloques and a not in occupes]
        
        if not app_disponibles:
            st.warning("⚠️ Aucun appartement n'est disponible pour le moment (tous occupés ou en maintenance).")
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
                    dent = st.date_input("Date Arrivée")
                    dsor = st.date_input("Date Départ (Libération à 11h00)")
                    rais = st.text_input("Raison du séjour")
                    enom = st.text_input("Employé")
                dem_nom = st.text_input("Démarcheur (Laisser vide si aucun)")
                
                if st.form_submit_button("VALIDER"):
                    if dsor <= dent:
                        st.error("La date de départ doit être après la date d'arrivée.")
                    else:
                        nuits = (dsor - dent).days
                        total = nuits * PRIX_NUITEE
                        comm = total * 0.10 if dem_nom else 0
                        
                        success = sauver({
                            "id": str(uuid.uuid4())[:8], "Client_Nom": nom, "Date_Naissance": str(dnais),
                            "Tel_Client": tel, "Piece_Type": piece, "Piece_Num": pnum,
                            "Date_Entree": str(dent), "Date_Sortie": str(dsor), "Raison": rais,
                            "Appartement": app, "Employe_Nom": enom, "Demarcheur_Nom": dem_nom if dem_nom else "Aucun",
                            "Montant_Total": total, "Commission": comm, "Mois": dent.strftime("%m-%Y"), "Statut": "En cours"
                        }, "sejours")
                        if success: 
                            st.success(f"✅ Client enregistré ! L'appartement {app} sera bloqué jusqu'au {dsor.strftime('%d/%m/%Y')} à 11h00.")
                            st.rerun()
                        else: st.error("❌ Erreur de connexion")

    # 3. DÉPENSES
    elif menu == "Dépenses & Maintenance":
        tab1, tab2 = st.tabs(["💸 Saisir Dépense", "🛠️ Maintenance"])
        with tab1:
            st.subheader("Enregistrer un frais")
            with st.form("f_dep"):
                motif = st.text_input("Motif de la dépense")
                montant = st.number_input("Montant (F CFA)", min_value=0)
                cible = st.selectbox("Cible", ["Général"] + APPARTEMENTS)
                emp = st.text_input("Votre Nom")
                mois_dep = datetime.now(TZ_BF).strftime("%m-%Y")
                
                if st.form_submit_button("ENREGISTRER DÉPENSE"):
                    if not motif or montant == 0: st.warning("Remplissez tout")
                    else:
                        sauver({"id": str(uuid.uuid4())[:8], "Date": str(date.today()), "Motif": motif, "Montant": montant, "Appartement": cible, "Employe": emp, "Mois": mois_dep}, "depenses")
                        st.success("Dépense enregistrée.")
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
                st.rerun()

    # 4. ADMINISTRATION
    elif menu == "ADMINISTRATION":
        if st.session_state.role != "admin": st.error("Accès Admin requis")
        else:
            st.header("⚙️ Gestion")
            target = st.selectbox("Choisir l'onglet", ["sejours", "depenses"])
            df_edit = charger(target)
            if not df_edit.empty:
                st.dataframe(df_edit)
                col_ref = "Client_Nom" if target == "sejours" else "id"
                sel = st.selectbox("Élément à supprimer (ID/Nom)", df_edit[col_ref].tolist())
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
                s_m = df_s[df_s["Mois"] == sel_m]
                d_m = df_d[df_d["Mois"] == sel_m] if not df_d.empty else pd.DataFrame()
                for c in ["Montant_Total", "Commission"]: s_m[c] = pd.to_numeric(s_m[c], errors='coerce').fillna(0)
                if not d_m.empty: d_m["Montant"] = pd.to_numeric(d_m["Montant"], errors='coerce').fillna(0)
                ca, com = s_m["Montant_Total"].sum(), s_m["Commission"].sum()
                dep = d_m["Montant"].sum() if not d_m.empty else 0
                net = ca - com - dep
                st.metric("NET RESTANT", f"{net:,.0f} F")
                pdf_bytes = imprimer_bilan(sel_m, s_m, d_m, ca, com, dep, net)
                st.download_button(f"📥 Télécharger PDF {sel_m}", pdf_bytes, f"Bilan_{sel_m}.pdf", "application/pdf")
