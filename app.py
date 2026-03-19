import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta
from fpdf import FPDF
import uuid
import pytz

# --- CONFIGURATION INITIALE ---
st.set_page_config(page_title="Résidence VIP - Gestion", page_icon="🏢", layout="wide")

CONFIG = {
    "API_URL": "https://sheetdb.io/api/v1/2a307403dpyom",
    "PRIX_NUITEE": 15000,
    "APPARTEMENTS": ["Appart A1", "Appart A2", "Appart A3", "Appart A4"],
    "TZ_BF": pytz.timezone('Africa/Ouagadougou')
}

MOIS_FR = {
    "01": "JANVIER", "02": "FEVRIER", "03": "MARS", "04": "AVRIL",
    "05": "MAI", "06": "JUIN", "07": "JUILLET", "08": "AOUT",
    "09": "SEPTEMBRE", "10": "OCTOBRE", "11": "NOVEMBRE", "12": "DECEMBRE"
}

# --- SESSION API OPTIMISEE ---
# Gérer une session unique (Keep-Alive) rend les requêtes vers SheetDB beaucoup plus rapides
if "api_session" not in st.session_state:
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    st.session_state.api_session = session

# --- INJECTION CSS (STYLE DES CARTES) ---
st.markdown("""
<style>
    div.card {
        padding: 20px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    div.card-maintenance { background-color: #c0392b; } /* Rouge foncé */
    div.card-occupe { background-color: #e67e22; }      /* Orange */
    div.card-libre { background-color: #27ae60; }       /* Vert */
    
    div.card h3 { margin: 0 0 10px 0; color: white; }
    div.card p { margin: 0; font-size: 16px; font-weight: 500;}
    div.card small { opacity: 0.8; font-size: 14px;}
</style>
""", unsafe_allow_html=True)


# --- FONCTIONS API ---
@st.cache_data(ttl=5) # Cache très court
def charger(onglet: str) -> pd.DataFrame:
    try:
        r = st.session_state.api_session.get(f"{CONFIG['API_URL']}?sheet={onglet}", timeout=10)
        return pd.DataFrame(r.json()) if r.status_code == 200 else pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur de réseau : {e}")
        return pd.DataFrame()

def sauver(ligne: dict, onglet: str) -> bool:
    try:
        r = st.session_state.api_session.post(f"{CONFIG['API_URL']}?sheet={onglet}", json={"data": [ligne]}, timeout=10)
        return r.status_code == 201
    except:
        return False

def supprimer_ligne(onglet: str, colonne: str, valeur: str) -> bool:
    try:
        r = st.session_state.api_session.delete(f"{CONFIG['API_URL']}/{colonne}/{valeur}?sheet={onglet}")
        return r.status_code in [200, 204]
    except:
        return False

# --- LOGIQUE ETATS (OCCUPATION & MAINTENANCE) ---
def obtenir_etats() -> tuple[dict, dict]:
    df_s = charger("sejours")
    df_m = charger("maintenance")
    now = datetime.now(CONFIG["TZ_BF"])
    bloques, occupes = {}, {}

    if not df_m.empty and "Statut" in df_m.columns:
        for _, row in df_m.iterrows():
            if str(row.get("Statut")).lower() == "inaccessible":
                bloques[str(row.get("Appartement"))] = str(row.get("Raison", "Maintenance technique"))

    if not df_s.empty and "Statut" in df_s.columns:
        en_cours = df_s[df_s["Statut"] == "En cours"]
        for _, row in en_cours.iterrows():
            try:
                ds = str(row.get("Date_Sortie"))
                h_lib = CONFIG["TZ_BF"].localize(datetime.combine(datetime.strptime(ds, "%Y-%m-%d"), time(11, 0)))
                if now < h_lib: 
                    occupes[str(row.get("Appartement"))] = h_lib.strftime("%d/%m/%Y à 11h00")
            except:
                continue
    return bloques, occupes

# --- GÉNÉRATEUR PDF ROBUSTE (Latin-1) ---
def imprimer_bilan(mois_code: str, ca: float, comm: float, dep: float, net: float, df_dep: pd.DataFrame) -> bytes:
    m_num, annee = mois_code.split("-")
    nom_mois = MOIS_FR.get(m_num, "INCONNU")
    titre_bilan = f"BILAN DU MOIS DE {nom_mois} {annee}"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    # Nettoyage des accents pour FPDF (qui ne gère nativement que latin-1)
    def clean_txt(text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    pdf.cell(0, 10, clean_txt(titre_bilan), ln=True, align="R")
    pdf.ln(20)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, clean_txt(f"CHIFFRE D'AFFAIRES BRUT : {int(ca):,} F"), ln=True)
    pdf.cell(0, 10, clean_txt(f"TOTAL COMMISSIONS : {int(comm):,} F"), ln=True)
    pdf.cell(0, 10, clean_txt(f"TOTAL DEPENSES : {int(dep):,} F"), ln=True)
    pdf.cell(0, 10, clean_txt(f"MONTANT NET RESTANT : {int(net):,} F"), ln=True)
    pdf.ln(20)
    
    pdf.cell(0, 10, clean_txt("DETAIL DES DEPENSES :"), ln=True)
    pdf.set_font("Arial", "", 11)
    if not df_dep.empty:
        for _, r in df_dep.iterrows():
            ligne_depense = f"- {r.get('Date','')} | {r.get('Motif','')} ({r.get('Appartement','')}) : {int(r.get('Montant',0)):,} F"
            pdf.cell(0, 8, clean_txt(ligne_depense), ln=True)
            
    return pdf.output(dest="S").encode('latin-1', 'replace')

import extra_streamlit_components as stx

cookie_manager = stx.CookieManager(key="cookie_manager")

# --- AUTHENTIFICATION & NAVIGATION ---
if 'auth' not in st.session_state: 
    st.session_state.auth, st.session_state.role = False, None

# Try to auto-login via cookie
cookie_role = cookie_manager.get(cookie="auth_role")
if not st.session_state.auth and cookie_role in ["admin", "employe"]:
    st.session_state.auth = True
    st.session_state.role = cookie_role

# Gestion de la redirection depuis le Dashboard
if 'page_active' not in st.session_state:
    st.session_state.page_active = "🏠 Dashboard"
if 'appart_cible' not in st.session_state:
    st.session_state.appart_cible = None

if not st.session_state.auth:
    st.title("🔐 Résidence VIP - Interface Sécurisée")
    st.markdown("Veuillez entrer vos identifiants pour accéder à l'interface de gestion.")
    
    l_col, _ = st.columns([1, 2])
    with l_col:
        with st.form("login_form"):
            u = st.text_input("Identifiant")
            p = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Se connecter 🚀")
            
            if submitted:
                if u == "admin" and p == "patron2024": 
                    st.session_state.auth, st.session_state.role = True, "admin"
                    cookie_manager.set("auth_role", "admin", expires_at=datetime.now() + timedelta(days=30))
                    import time as time_mod
                    time_mod.sleep(0.5)
                    st.rerun()
                elif u == "employe" and p == "bienvenue": 
                    st.session_state.auth, st.session_state.role = True, "employe"
                    cookie_manager.set("auth_role", "employe", expires_at=datetime.now() + timedelta(days=30))
                    import time as time_mod
                    time_mod.sleep(0.5)
                    st.rerun()
                else: 
                    st.error("❌ Identifiants incorrects. Accès refusé.")
else:
    bloques, occupes = obtenir_etats()
    
    st.sidebar.image("https://img.icons8.com/color/96/city-buildings.png", width=64)
    st.sidebar.markdown(f"**Rôle Actif:** `{st.session_state.role.upper()}`")
    st.sidebar.info(f"📍 Ouagadougou : {datetime.now(CONFIG['TZ_BF']).strftime('%H:%M')}")
    
    # Callback pour synchroniser les changements de page via la sidebar
    def sync_menu():
        st.session_state.page_active = st.session_state._menu_radio
        
    menu = st.sidebar.radio("Navigation", [
        "🏠 Dashboard", 
        "📝 Enregistrement Client", 
        "🛠️ Dépenses & Maintenance", 
        "⚙️ ADMINISTRATION", 
        "📈 RAPPORT PDF"
    ], index=["🏠 Dashboard", "📝 Enregistrement Client", "🛠️ Dépenses & Maintenance", "⚙️ ADMINISTRATION", "📈 RAPPORT PDF"].index(st.session_state.page_active), key="_menu_radio", on_change=sync_menu)
    
    if st.sidebar.button("Se Déconnecter 🚪"): 
        cookie_manager.delete("auth_role")
        st.session_state.auth = False
        st.session_state.role = None
        st.session_state.page_active = "🏠 Dashboard"
        import time as time_mod
        time_mod.sleep(0.5)
        st.rerun()

    # --- 1. DASHBOARD OVERHAUL ---
    if st.session_state.page_active == "🏠 Dashboard":
        st.header("État du Parc Immobilier")
        st.markdown("Aperçu en temps réel de la disponibilité des **appartements VIP**.")
        st.divider()
        
        cols = st.columns(4)
        for i, app in enumerate(CONFIG["APPARTEMENTS"]):
            with cols[i]:
                if app in bloques:
                    html_card = f"""<div class='card card-maintenance'>
                                    <h3>{app}</h3><p>❌ MAINTENANCE</p>
                                    <small>{bloques[app]}</small></div>"""
                    st.markdown(html_card, unsafe_allow_html=True)
                elif app in occupes:
                    html_card = f"""<div class='card card-occupe'>
                                    <h3>{app}</h3><p>🔴 OCCUPÉ</p>
                                    <small>Libre le :<br>{occupes[app]}</small></div>"""
                    st.markdown(html_card, unsafe_allow_html=True)
                    if st.button("Mettre fin au séjour", key=f"fin_{app}", use_container_width=True):
                        df_s = charger("sejours")
                        if not df_s.empty and "Statut" in df_s.columns:
                            en_cours = df_s[(df_s["Appartement"] == app) & (df_s["Statut"] == "En cours")]
                            if not en_cours.empty:
                                id_sej = en_cours.iloc[0]["id"]
                                st.session_state.api_session.patch(
                                    f"{CONFIG['API_URL']}/id/{id_sej}?sheet=sejours",
                                    json={"data": {"Statut": "Terminé", "Date_Sortie": str(datetime.now(CONFIG["TZ_BF"]).date())}}
                                )
                                st.toast(f"Séjour de {app} terminé. Actualisation...", icon="✅")
                                st.cache_data.clear()
                                import time as time_mod
                                time_mod.sleep(2)
                                st.rerun()
                else:
                    html_card = f"""<div class='card card-libre'>
                                    <h3>{app}</h3><p>🟢 LIBRE</p></div>"""
                    st.markdown(html_card, unsafe_allow_html=True)
                    if st.button(f"Enregistrer Client", key=f"btn_{app}", use_container_width=True):
                        st.session_state.appart_cible = app
                        st.session_state.page_active = "📝 Enregistrement Client"
                        st.rerun()

    # --- 2. ENREGISTREMENT CLIENT ---
    elif st.session_state.page_active == "📝 Enregistrement Client":
        st.header("Nouvelle Fiche Client")
        libres = [a for a in CONFIG["APPARTEMENTS"] if a not in bloques and a not in occupes]
        
        # Si un appartement a été cliqué depuis le dashboard, on le présélectionne
        idx_appart = 0
        if st.session_state.appart_cible and st.session_state.appart_cible in libres:
            idx_appart = libres.index(st.session_state.appart_cible)
            # On affiche un petit rappel
            st.info(f"Logement pré-attribué depuis le Dashboard : **{st.session_state.appart_cible}**")
            
        if not libres: 
            st.error("⚠️ Impossible d'enregistrer : Tous les appartements sont occupés ou en maintenance.")
        else:
            with st.form("inscription_form", clear_on_submit=True):
                st.subheader("Informations Générales")
                c1, c2, c3 = st.columns(3)
                with c1:
                    nom = st.text_input("Nom Client *", placeholder="Ex: Jean Dupont")
                    dnais = st.date_input("Date de Naissance", value=date(1990,1,1), min_value=date(1920,1,1))
                    prov = st.text_input("Provenance (Pays/Ville)")
                with c2:
                    tel = st.text_input("Telephone Client *", placeholder="+226 ...")
                    piece = st.selectbox("Type Pièce", ["CNI", "Passeport", "Permis", "Carte Séjour"])
                    pnum = st.text_input("N° Pièce *")
                with c3:
                    dent = st.date_input("Date d'Entrée", value=date.today())
                    nuits = st.number_input("Nombre de Nuits *", min_value=1, step=1)
                    app = st.selectbox("Appartement Attribué", libres, index=idx_appart)

                st.subheader("Acteurs du Dossier")
                c_act1, c_act2 = st.columns(2)
                with c_act1:
                    rais_s = st.text_area("Raison du séjour", height=100)
                    enom = st.text_input("Employé de Garde Responsable")
                    etel = st.text_input("Téléphone de l'Employé")
                with c_act2:
                    st.info("💡 Ne remplir le démarcheur que s'il y a lieu de lui verser une commission (10%).")
                    dnom = st.text_input("Nom du Démarcheur (Optionnel)")
                    dtel = st.text_input("Téléphone du Démarcheur")

                if st.form_submit_button("VALIDER L'ENREGISTREMENT ✅"):
                    if not nom or not tel or not pnum:
                        st.warning("Veuillez remplir les champs obligatoires (*)")
                    else:
                        dsor = dent + timedelta(days=nuits)
                        total = nuits * CONFIG["PRIX_NUITEE"]
                        comm = (total * 0.1) if dnom else 0
                        # Identifiant Propre
                        nouvel_id = f"VIP-{uuid.uuid4().hex[:6].upper()}"
                        
                        data = {
                            "id": nouvel_id, "Client_Nom": nom, "Date_Naissance": str(dnais), "Provenance": prov,
                            "Piece_Type": piece, "Piece_Num": pnum, "Tel_Client": tel, "Date_Entree": str(dent), 
                            "Date_Sortie": str(dsor), "Raison": rais_s, "Appartement": app, "Employe_Nom": enom, 
                            "Employe_Tel": etel, "Demarcheur_Nom": "Aucun" if not dnom else dnom, 
                            "Demarcheur_Tel": "Aucun" if not dtel else dtel, "Montant_Total": total, 
                            "Commission": comm, "Mois": dent.strftime("%m-%Y"), "Statut": "En cours"
                        }
                        
                        if sauver(data, "sejours"): 
                            st.toast("Enregistrement réussi !", icon="✅")
                            # Réinitialiser la présélection après un succès
                            st.session_state.appart_cible = None 
                            st.cache_data.clear()
                            st.rerun()

    # --- 3. DEPENSES & MAINTENANCE ---
    elif st.session_state.page_active == "🛠️ Dépenses & Maintenance":
        st.header("Gestion Logistique")
        tab1, tab2 = st.tabs(["💸 Trésorerie (Sortie)", "🛠️ Suivi Maintenance"])
        
        with tab1:
            st.markdown("---")
            with st.form("form_depenses", clear_on_submit=True):
                col_dcf1, col_dcf2 = st.columns(2)
                with col_dcf1:
                    motif = st.text_input("Motif de la dépense *", placeholder="Ex: Électricité facture")
                    mont = st.number_input("Montant Consommé (F) *", min_value=1, step=500)
                with col_dcf2:
                    cible = st.selectbox("Cible de la dépense", ["Général (Fond de Caisse)"] + CONFIG["APPARTEMENTS"])
                    # Cacher le bouton technique
                    submit_dep = st.form_submit_button("Décaisser les Fonds 💸")
                
                if submit_dep:
                    nouvel_id = f"DEP-{uuid.uuid4().hex[:5].upper()}"
                    cible_propre = "Général" if "Général" in cible else cible
                    d_obj = {"id": nouvel_id, "Date": str(date.today()), "Motif": motif, "Montant": mont, "Appartement": cible_propre, "Mois": datetime.now(CONFIG["TZ_BF"]).strftime("%m-%Y")}
                    if sauver(d_obj, "depenses"):
                        st.toast("Sortie de caisse confirmée.", icon="💵")
                        st.cache_data.clear()

        with tab2:
            st.markdown("---")
            st.write("Si un appartement nécessite des réparations (climatisation, plomberie...), il faut le déclarer ici pour **bloquer automatiquement l'attribution à un nouveau client**.")
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                app_m = st.selectbox("Sélectionnez l'appartement visé", CONFIG["APPARTEMENTS"])
                stat_m = st.selectbox("Nouvel État Logistique", ["Inaccessible", "Disponible (Fin de maintenance)"])
            with m_col2:
                rais_m = st.text_area("Observations / Motifs", height=110, placeholder="Ex: Climatiseur abîmé par l'ancien locataire. Technicien commandé.")
            
            if st.button("Actualiser la Maintenance 🛠️", use_container_width=True):
                res = st.session_state.api_session.patch(f"{CONFIG['API_URL']}/Appartement/{app_m}?sheet=maintenance", json={"data": {"Statut": stat_m, "Raison": rais_m}})
                if res.status_code not in [200, 204]:
                    sauver({"Appartement": app_m, "Statut": stat_m, "Raison": rais_m}, "maintenance")
                
                st.toast(f"Statut technique de {app_m} mis à jour.", icon="🔧")
                st.cache_data.clear()
                st.rerun()

    # --- 4. ADMINISTRATION ---
    elif st.session_state.page_active == "⚙️ ADMINISTRATION":
        if st.session_state.role != "admin": 
            st.error("⛔ Zone Accès Réservé à la Direction.")
        else:
            st.header("Centre de Contrôle & Supression")
            onglet = st.selectbox("Tables de Base de données", ["sejours", "depenses", "maintenance"])
            df = charger(onglet)
            
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.subheader("Correction Rapide (Suppression)")
                id_col = "Appartement" if onglet == "maintenance" else "id"
                sel = st.selectbox(f"Identifiant ({id_col}) de la ligne à purger", df[id_col].tolist())
                
                c_warn, _ = st.columns([1,2])
                with c_warn:
                    if st.button("SUPPRIMER L'ENTRÉE SÉLECTIONNÉE 🗑️", type="primary"):
                        if supprimer_ligne(onglet, id_col, sel): 
                            st.toast("Ligne définitivement supprimée de SheetDB.", icon="✅")
                            st.cache_data.clear()
                            st.rerun()
            else:
                st.info(f"La table '{onglet}' est actuellement vide.")

    # --- 5. RAPPORT PDF ---
    elif st.session_state.page_active == "📈 RAPPORT PDF":
        if st.session_state.role != "admin": 
            st.error("⛔ Zone de comptabilité confidentielle (Direction Uniquement).")
        else:
            st.header("Bilan Comptable Mensuel")
            
            df_s = charger("sejours")
            df_d = charger("depenses")
            
            if not df_s.empty:
                mois_list = sorted(df_s["Mois"].dropna().unique(), reverse=True)
                sel_m = st.selectbox("Sélectionner la période", mois_list)
                
                if sel_m:
                    s_m = df_s[df_s["Mois"] == sel_m].copy()
                    d_m = df_d[df_d["Mois"] == sel_m].copy() if not df_d.empty else pd.DataFrame()
                    
                    ca = pd.to_numeric(s_m["Montant_Total"], errors='coerce').fillna(0).sum()
                    com = pd.to_numeric(s_m["Commission"], errors='coerce').fillna(0).sum()
                    dep = pd.to_numeric(d_m["Montant"], errors='coerce').fillna(0).sum() if not d_m.empty else 0
                    net = ca - com - dep
                    
                    # Cartes de Finance (Affichage élégant avec Markdown)
                    st.write("")
                    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                    f_col1.metric("CHIFFRE D'AFFAIRES", f"{ca:,.0f} F")
                    f_col2.metric("COMMISSIONS A REVERSER", f"{com:,.0f} F", delta_color="inverse")
                    f_col3.metric("DEPENSES", f"{dep:,.0f} F", delta_color="inverse")
                    f_col4.metric("BENEFICE NET", f"{net:,.0f} F", delta="Calculé")

                    st.markdown("---")
                    st.subheader("📋 Récapitulatif des sorties (Dépenses)")
                    if not d_m.empty: 
                        st.dataframe(d_m[["Date", "Motif", "Appartement", "Montant"]], use_container_width=True, hide_index=True)
                    else:
                        st.info("Aucune dépense enregistrée sur cette période.")
                        
                    st.markdown("---")
                    pdf_bytes = imprimer_bilan(sel_m, ca, com, dep, net, d_m)
                    st.download_button(
                        label=f"📥 ÉDITER LE BILAN PDF GLOBAL - {sel_m}",
                        data=pdf_bytes,
                        file_name=f"Bilan_Residence_{sel_m}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )
