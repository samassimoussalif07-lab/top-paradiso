import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta
from fpdf import FPDF
import uuid
import pytz
import urllib.parse
import json
import os
import sqlite3

# --- CONFIGURATION INITIALE ---
st.set_page_config(page_title="Résidence PARADISO - Gestion", page_icon="🏢", layout="wide")

CONFIG = {
    "API_URL": "https://sheetdb.io/api/v1/2a307403dpyom",
    "PRIX_NUITEE": 15000,
    "APPARTEMENTS": ["Appart A1", "Appart A2", "Appart A3", "Appart A4"],
    "TZ_BF": pytz.timezone('Africa/Ouagadougou')
}

MODES_PAIEMENT = ["Espèces", "Orange Money", "Moov Money", "Wave"]

MOIS_FR = {
    "01": "JANVIER", "02": "FEVRIER", "03": "MARS", "04": "AVRIL",
    "05": "MAI", "06": "JUIN", "07": "JUILLET", "08": "AOUT",
    "09": "SEPTEMBRE", "10": "OCTOBRE", "11": "NOVEMBRE", "12": "DECEMBRE"
}

DB_PATH = "residence_data.db"

# --- INITIALISATION BASE DE DONNÉES SQLITE LOCALE (OFFLINE-FIRST) ---
def init_sqlite_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sejours (
            id TEXT PRIMARY KEY,
            Client_Nom TEXT,
            Date_Naissance TEXT,
            Provenance TEXT,
            Piece_Type TEXT,
            Piece_Num TEXT,
            Tel_Client TEXT,
            Date_Entree TEXT,
            Date_Sortie TEXT,
            Raison TEXT,
            Appartement TEXT,
            Employe_Nom TEXT,
            Employe_Tel TEXT,
            Demarcheur_Nom TEXT,
            Demarcheur_Tel TEXT,
            Montant_Total REAL,
            Commission REAL,
            Mois TEXT,
            Statut TEXT,
            Paiement TEXT,
            Mode_Paiement TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS depenses (
            id TEXT PRIMARY KEY,
            Date TEXT,
            Motif TEXT,
            Montant REAL,
            Appartement TEXT,
            Mois TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS maintenance (
            Appartement TEXT PRIMARY KEY,
            Statut TEXT,
            Raison TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_sqlite_db()

# --- SESSION API OPTIMISEE ---
if "api_session" not in st.session_state:
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    st.session_state.api_session = session

# --- INJECTION CSS (STYLE DES CARTES & UI) ---
st.markdown("""
<style>
    /* Masquage des badges Streamlit Cloud */
    [data-testid="stGitHubIcon"],
    .viewerBadge_container__1QSob,
    .styles_viewerBadge__1yB5_,
    .viewerBadge_link__1S137,
    .viewerBadge_text__1JaDK,
    a[href^="https://github.com/"] {
        display: none !important;
        visibility: hidden !important;
    }

    div.card {
        padding: 20px;
        border-radius: 16px;
        color: white;
        text-align: center;
        margin-bottom: 15px;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    div.card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 20px rgba(0, 0, 0, 0.2);
    }
    div.card-maintenance { 
        background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); 
    }
    div.card-occupe { 
        background: linear-gradient(135deg, #e67e22 0%, #d35400 100%); 
    }
    div.card-depart-today {
        background: linear-gradient(135deg, #f39c12 0%, #f1c40f 100%);
        color: #111111 !important;
    }
    div.card-depart-today h3, div.card-depart-today p, div.card-depart-today small {
        color: #111111 !important;
    }
    div.card-retard {
        background: linear-gradient(135deg, #c0392b 0%, #8e44ad 100%);
        animation: pulseAlert 2s infinite;
    }
    @keyframes pulseAlert {
        0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); }
        70% { box-shadow: 0 0 0 12px rgba(231, 76, 60, 0); }
        100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); }
    }
    div.card-libre { 
        background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%); 
    }
    
    div.card h3 { 
        margin: 0 0 10px 0; 
        font-size: 22px; 
        font-weight: 700;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    div.card p { 
        margin: 0; 
        font-size: 16px; 
        font-weight: 600;
        text-transform: uppercase;
    }
    div.card small { 
        opacity: 0.95; 
        font-size: 13px;
        display: block;
        margin-top: 8px;
        line-height: 1.4;
    }
</style>
""", unsafe_allow_html=True)


# --- FONCTIONS DE SYNCHRONISATION SQLITE & SHEETDB ---
def sync_sqlite_from_df(df: pd.DataFrame, onglet: str):
    if df.empty:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        if onglet == "sejours":
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                id_val = str(row_dict.get("id", "")).strip()
                if not id_val: continue
                conn.execute('''
                    INSERT OR REPLACE INTO sejours 
                    (id, Client_Nom, Date_Naissance, Provenance, Piece_Type, Piece_Num, Tel_Client,
                     Date_Entree, Date_Sortie, Raison, Appartement, Employe_Nom, Employe_Tel,
                     Demarcheur_Nom, Demarcheur_Tel, Montant_Total, Commission, Mois, Statut, Paiement, Mode_Paiement)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    id_val,
                    str(row_dict.get("Client_Nom", "")),
                    str(row_dict.get("Date_Naissance", "")),
                    str(row_dict.get("Provenance", "")),
                    str(row_dict.get("Piece_Type", "")),
                    str(row_dict.get("Piece_Num", "")),
                    str(row_dict.get("Tel_Client", "")),
                    str(row_dict.get("Date_Entree", "")),
                    str(row_dict.get("Date_Sortie", "")),
                    str(row_dict.get("Raison", "")),
                    str(row_dict.get("Appartement", "")),
                    str(row_dict.get("Employe_Nom", "")),
                    str(row_dict.get("Employe_Tel", "")),
                    str(row_dict.get("Demarcheur_Nom", "")),
                    str(row_dict.get("Demarcheur_Tel", "")),
                    float(row_dict.get("Montant_Total", 0) or 0),
                    float(row_dict.get("Commission", 0) or 0),
                    str(row_dict.get("Mois", "")),
                    str(row_dict.get("Statut", "")),
                    str(row_dict.get("Paiement", "")),
                    str(row_dict.get("Mode_Paiement", "Espèces"))
                ))
        elif onglet == "depenses":
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                id_val = str(row_dict.get("id", "")).strip()
                if not id_val: continue
                conn.execute('''
                    INSERT OR REPLACE INTO depenses (id, Date, Motif, Montant, Appartement, Mois)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    id_val,
                    str(row_dict.get("Date", "")),
                    str(row_dict.get("Motif", "")),
                    float(row_dict.get("Montant", 0) or 0),
                    str(row_dict.get("Appartement", "")),
                    str(row_dict.get("Mois", ""))
                ))
        elif onglet == "maintenance":
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                app_val = str(row_dict.get("Appartement", "")).strip()
                if not app_val: continue
                conn.execute('''
                    INSERT OR REPLACE INTO maintenance (Appartement, Statut, Raison)
                    VALUES (?, ?, ?)
                ''', (
                    app_val,
                    str(row_dict.get("Statut", "")),
                    str(row_dict.get("Raison", ""))
                ))
        conn.commit()
    except Exception as ex:
        pass
    finally:
        conn.close()

def charger_sqlite(onglet: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(f"SELECT * FROM {onglet}", conn)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()

@st.cache_data(ttl=5)
def charger(onglet: str) -> pd.DataFrame:
    try:
        r = st.session_state.api_session.get(f"{CONFIG['API_URL']}?sheet={onglet}", timeout=5)
        if r.status_code == 200:
            df = pd.DataFrame(r.json())
            sync_sqlite_from_df(df, onglet)
            return df
        else:
            return charger_sqlite(onglet)
    except Exception:
        return charger_sqlite(onglet)

def sauver(ligne: dict, onglet: str) -> bool:
    df_single = pd.DataFrame([ligne])
    sync_sqlite_from_df(df_single, onglet)
    try:
        r = st.session_state.api_session.post(f"{CONFIG['API_URL']}?sheet={onglet}", json={"data": [ligne]}, timeout=5)
        return True
    except Exception:
        return True

def patch_sejour(id_sej: str, patch_data: dict) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        set_clauses = ", ".join([f"{k} = ?" for k in patch_data.keys()])
        values = list(patch_data.values()) + [id_sej]
        conn.execute(f"UPDATE sejours SET {set_clauses} WHERE id = ?", values)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

    try:
        res = st.session_state.api_session.patch(
            f"{CONFIG['API_URL']}/id/{id_sej}?sheet=sejours",
            json={"data": patch_data},
            timeout=5
        )
        return True
    except Exception:
        return True

def supprimer_ligne(onglet: str, colonne: str, valeur: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(f"DELETE FROM {onglet} WHERE {colonne} = ?", (valeur,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

    try:
        st.session_state.api_session.delete(f"{CONFIG['API_URL']}/{colonne}/{valeur}?sheet={onglet}", timeout=5)
    except Exception:
        pass
    return True

def actualiser_maintenance(appartement: str, statut: str, raison: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT OR REPLACE INTO maintenance (Appartement, Statut, Raison) VALUES (?, ?, ?)",
                     (appartement, statut, raison))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

    url = f"{CONFIG['API_URL']}/Appartement/{appartement}?sheet=maintenance"
    payload = {"data": {"Statut": statut, "Raison": raison}}
    try:
        res = st.session_state.api_session.patch(url, json=payload, timeout=5)
        if res.status_code not in [200, 204]:
            sauver({"Appartement": appartement, "Statut": statut, "Raison": raison}, "maintenance")
    except Exception:
        sauver({"Appartement": appartement, "Statut": statut, "Raison": raison}, "maintenance")
    return True


# --- FONCTIONS MESSAGERIE (CHAT) ---
CHAT_DB_PATH = "chat_db.json"
CHAT_MEDIA_DIR = "chat_media"

if not os.path.exists(CHAT_MEDIA_DIR):
    os.makedirs(CHAT_MEDIA_DIR)

def get_chat_messages():
    if not os.path.exists(CHAT_DB_PATH):
        return []
    with open(CHAT_DB_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []

def save_chat_message(msg):
    msgs = get_chat_messages()
    msgs.append(msg)
    with open(CHAT_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False, indent=2)

def delete_chat_message(msg_id):
    msgs = get_chat_messages()
    to_delete = next((m for m in msgs if m["id"] == msg_id), None)
    if to_delete:
        msgs.remove(to_delete)
        if to_delete.get("type") in ["image", "audio"]:
            path = to_delete.get("content")
            if path and os.path.exists(path):
                try: os.remove(path)
                except: pass
        with open(CHAT_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(msgs, f, ensure_ascii=False, indent=2)


# --- LOGIQUE ETATS (OCCUPATION, MAINTENANCE & ALERTES 11H00) ---
def obtenir_etats() -> tuple[dict, dict]:
    df_s = charger("sejours")
    df_m = charger("maintenance")
    now = datetime.now(CONFIG["TZ_BF"])
    bloques, occupes = {}, {}

    if not df_m.empty and "Statut" in df_m.columns:
        for _, row in df_m.iterrows():
            appart = str(row.get("Appartement"))
            statut = str(row.get("Statut", "")).lower()
            if statut == "inaccessible":
                bloques[appart] = str(row.get("Raison", "Maintenance technique"))
            else:
                if appart in bloques:
                    del bloques[appart]

    if not df_s.empty and "Statut" in df_s.columns:
        en_cours = df_s[df_s["Statut"] == "En cours"]
        for _, row in en_cours.iterrows():
            try:
                ds_str = str(row.get("Date_Sortie"))
                ds_dt = datetime.strptime(ds_str, "%Y-%m-%d")
                h_lib = CONFIG["TZ_BF"].localize(datetime.combine(ds_dt.date(), time(11, 0)))
                
                de = str(row.get("Date_Entree", ""))
                debut_str = "/".join(de.split("-")[::-1]) if "-" in de else de
                
                retard = (now >= h_lib)
                depart_aujourdhui = (now.date() == ds_dt.date() and not retard)
                
                occupes[str(row.get("Appartement"))] = {
                    "debut": debut_str,
                    "fin": h_lib.strftime("%d/%m/%Y à 11h00"),
                    "paiement": str(row.get("Paiement", "Non Payé")),
                    "mode_paiement": str(row.get("Mode_Paiement", "Espèces")),
                    "id_sej": str(row.get("id", "")),
                    "client": str(row.get("Client_Nom", "")),
                    "montant": float(row.get("Montant_Total", 0) or 0),
                    "tel": str(row.get("Tel_Client", "")),
                    "retard": retard,
                    "depart_aujourdhui": depart_aujourdhui
                }
            except Exception:
                continue
    return bloques, occupes


# --- GÉNÉRATEUR PDF ROBUSTE (Latin-1) ---
def imprimer_bilan(mois_code: str, ca: float, ca_paye: float, ca_attente: float, comm: float, dep: float, net: float, df_dep: pd.DataFrame, df_s_mois: pd.DataFrame) -> bytes:
    m_num, annee = mois_code.split("-")
    nom_mois = MOIS_FR.get(m_num, "INCONNU")
    titre_bilan = f"BILAN MENSUEL - {nom_mois} {annee}"

    pdf = FPDF()
    pdf.add_page()
    
    def clean_txt(text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    # En-tête professionnel
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 12, clean_txt("RÉSIDENCE PARADISO"), ln=True, align="C")
    
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(127, 140, 141)
    pdf.cell(0, 6, clean_txt("Téléphone de la résidence : +226 64353550"), ln=True, align="C")
    
    pdf.ln(5)
    pdf.set_draw_color(189, 195, 199)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)

    # Titre du bilan
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, clean_txt(titre_bilan), ln=True, align="C")
    pdf.ln(8)
    
    # Résumé Financier (Tableau)
    pdf.set_font("Arial", "B", 11)
    pdf.set_fill_color(236, 240, 241)
    pdf.set_draw_color(189, 195, 199)
    
    w1, w2 = 95, 95
    
    pdf.cell(w1, 10, clean_txt("CHIFFRE D'AFFAIRES (CA) GLOBAL"), border=1, align="L", fill=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(w2, 10, clean_txt(f"{int(ca):,} F CFA".replace(',', ' ')), border=1, align="R", ln=True)
    
    pdf.set_font("Arial", "I", 10)
    pdf.cell(w1, 8, clean_txt("   Dont CA Encaissé (Payé)"), border="LR", align="L")
    pdf.cell(w2, 8, clean_txt(f"{int(ca_paye):,} F CFA".replace(',', ' ')), border="LR", align="R", ln=True)
    pdf.cell(w1, 8, clean_txt("   Dont CA En Attente (Non Payé)"), border="LRB", align="L")
    pdf.cell(w2, 8, clean_txt(f"{int(ca_attente):,} F CFA".replace(',', ' ')), border="LRB", align="R", ln=True)
    
    pdf.set_font("Arial", "B", 11)
    pdf.cell(w1, 10, clean_txt("TOTAL COMMISSIONS"), border=1, align="L", fill=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(w2, 10, clean_txt(f"{int(comm):,} F CFA".replace(',', ' ')), border=1, align="R", ln=True)
    
    pdf.set_font("Arial", "B", 11)
    pdf.cell(w1, 10, clean_txt("TOTAL DÉPENSES"), border=1, align="L", fill=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(w2, 10, clean_txt(f"{int(dep):,} F CFA".replace(',', ' ')), border=1, align="R", ln=True)
    
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(39, 174, 96)
    pdf.cell(w1, 10, clean_txt("BÉNÉFICE NET RESTANT"), border=1, align="L", fill=True)
    pdf.cell(w2, 10, clean_txt(f"{int(net):,} F CFA".replace(',', ' ')), border=1, align="R", ln=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    
    # Détail des revenus
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, clean_txt("DÉTAIL DES REVENUS DU MOIS (PRORATA) :"), ln=True)
    
    if not df_s_mois.empty:
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(236, 240, 241)
        ws1, ws2, ws3, ws4, ws5 = 45, 25, 65, 20, 35
        pdf.cell(ws1, 8, clean_txt("Client"), border=1, align="C", fill=True)
        pdf.cell(ws2, 8, clean_txt("Appart."), border=1, align="C", fill=True)
        pdf.cell(ws3, 8, clean_txt("Période globale"), border=1, align="C", fill=True)
        pdf.cell(ws4, 8, clean_txt("Nuits"), border=1, align="C", fill=True)
        pdf.cell(ws5, 8, clean_txt("Montant (Mois)"), border=1, align="C", fill=True, ln=True)
        
        pdf.set_font("Arial", "", 9)
        for _, r in df_s_mois.iterrows():
            pdf.cell(ws1, 8, clean_txt(str(r.get('Client',''))[:25]), border=1, align="L")
            pdf.cell(ws2, 8, clean_txt(str(r.get('Appart',''))), border=1, align="C")
            pdf.cell(ws3, 8, clean_txt(str(r.get('Dates',''))), border=1, align="C")
            pdf.cell(ws4, 8, clean_txt(str(r.get('Nuits',''))), border=1, align="C")
            pdf.cell(ws5, 8, clean_txt(f"{int(r.get('Montant',0)):,} F".replace(',', ' ')), border=1, align="R", ln=True)
    else:
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 10, clean_txt("Aucun revenu enregistré sur ce mois."), ln=True)
        
    pdf.ln(5)

    # Détail des dépenses
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, clean_txt("DÉTAIL DES DÉPENSES :"), ln=True)
    
    if not df_dep.empty:
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(236, 240, 241)
        w_date, w_motif, w_app, w_mont = 25, 95, 30, 40
        
        pdf.cell(w_date, 8, clean_txt("Date"), border=1, align="C", fill=True)
        pdf.cell(w_motif, 8, clean_txt("Motif"), border=1, align="C", fill=True)
        pdf.cell(w_app, 8, clean_txt("Appart."), border=1, align="C", fill=True)
        pdf.cell(w_mont, 8, clean_txt("Montant"), border=1, align="C", fill=True, ln=True)
        
        pdf.set_font("Arial", "", 10)
        for _, r in df_dep.iterrows():
            pdf.cell(w_date, 8, clean_txt(r.get('Date','')), border=1, align="C")
            pdf.cell(w_motif, 8, clean_txt(str(r.get('Motif',''))[:50]), border=1, align="L")
            pdf.cell(w_app, 8, clean_txt(r.get('Appartement','')), border=1, align="C")
            pdf.cell(w_mont, 8, clean_txt(f"{int(r.get('Montant',0)):,} F".replace(',', ' ')), border=1, align="R", ln=True)
    else:
        pdf.set_font("Arial", "I", 11)
        pdf.cell(0, 10, clean_txt("Aucune dépense enregistrée sur ce mois."), ln=True)
            
    # Pied de page
    pdf.ln(15)
    pdf.set_draw_color(189, 195, 199)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(127, 140, 141)
    pdf.cell(0, 10, clean_txt("Document généré automatiquement par le système Résidence PARADISO."), ln=True, align="C")
    
    return pdf.output(dest="S").encode('latin-1', 'replace')

def generer_recu_pdf(info: dict, appart: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    
    def clean_txt(text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    # En-tête professionnel
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 12, clean_txt("RÉSIDENCE PARADISO"), ln=True, align="C")
    
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(127, 140, 141)
    pdf.cell(0, 6, clean_txt("Téléphone de la résidence : +226 64353550"), ln=True, align="C")
    
    pdf.ln(5)
    pdf.set_draw_color(189, 195, 199)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    # Titre du document
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, clean_txt("REÇU DE SÉJOUR"), ln=True, align="C")
    pdf.ln(8)
    
    # Info Client
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, clean_txt(f"Client : {info.get('client', '')}"), ln=True)
    pdf.cell(0, 6, clean_txt(f"Téléphone : {info.get('tel', '')}"), ln=True)
    pdf.cell(0, 6, clean_txt(f"Début du séjour : {info.get('debut', '')}"), ln=True)
    pdf.cell(0, 6, clean_txt(f"Fin du séjour : {info.get('fin', '')}"), ln=True)
    mode_p = info.get('mode_paiement', 'Espèces')
    pdf.cell(0, 6, clean_txt(f"Mode de règlement : {mode_p}"), ln=True)
    pdf.ln(8)
    
    # Détails Financiers (Tableau Quadrillé)
    montant = int(info.get('montant', 0))
    prix_unitaire = CONFIG["PRIX_NUITEE"]
    nuits = montant // prix_unitaire if prix_unitaire else 0
    
    pdf.set_font("Arial", "B", 11)
    pdf.set_fill_color(236, 240, 241)
    pdf.set_draw_color(189, 195, 199)
    
    w_des, w_pu, w_qte, w_tot = 80, 35, 25, 50
    
    pdf.cell(w_des, 8, clean_txt("Désignation"), border=1, align="C", fill=True)
    pdf.cell(w_pu, 8, clean_txt("Prix Unitaire"), border=1, align="C", fill=True)
    pdf.cell(w_qte, 8, clean_txt("Nuits"), border=1, align="C", fill=True)
    pdf.cell(w_tot, 8, clean_txt("Total"), border=1, align="C", fill=True, ln=True)
    
    pdf.set_font("Arial", "", 11)
    pdf.cell(w_des, 10, clean_txt(f"Séjour - {appart}"), border=1)
    pdf.cell(w_pu, 10, clean_txt(f"{prix_unitaire:,} F".replace(',', ' ')), border=1, align="R")
    pdf.cell(w_qte, 10, clean_txt(str(nuits)), border=1, align="C")
    pdf.cell(w_tot, 10, clean_txt(f"{montant:,} F CFA".replace(',', ' ')), border=1, align="R", ln=True)
    
    pdf.ln(8)
    
    val_paye = str(info.get('paiement', '')).strip().lower()
    est_paye = (val_paye == "payé" or val_paye == "paye")
    statut_str = f"RÉGLÉ ({mode_p.upper()})" if est_paye else "NON RÉGLÉ"
    
    if est_paye:
        pdf.set_text_color(39, 174, 96)
    else:
        pdf.set_text_color(192, 57, 43)
        
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 8, clean_txt(f"STATUT PAIE. : {statut_str}"), align="R", ln=True)
    pdf.set_text_color(0, 0, 0)
    
    pdf.ln(15)
    pdf.set_draw_color(189, 195, 199)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(127, 140, 141)
    pdf.cell(0, 10, clean_txt("Merci de votre confiance. Contactez-nous pour toute assistance."), ln=True, align="C")
    
    pdf.ln(5)
    y_sig = pdf.get_y()
    pdf.cell(0, 5, clean_txt("La Direction PARADISO."), ln=True, align="R")
    
    if os.path.exists("signature.png"):
        pdf.image("signature.png", x=150, y=y_sig + 5, w=40)
    elif os.path.exists("signature.jpg"):
        pdf.image("signature.jpg", x=150, y=y_sig + 5, w=40)
        
    return pdf.output(dest="S").encode('latin-1', 'replace')

import extra_streamlit_components as stx

cookie_manager = stx.CookieManager(key="cookie_manager")

# --- AUTHENTIFICATION & NAVIGATION ---
if 'auth' not in st.session_state: 
    st.session_state.auth, st.session_state.role = False, None
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

# Auto-login via cookie
cookie_role = cookie_manager.get(cookie="auth_role")
if not st.session_state.auth and cookie_role in ["admin", "employe"]:
    st.session_state.auth = True
    st.session_state.role = cookie_role

cookie_user_name = cookie_manager.get(cookie="auth_user_name")
if cookie_user_name:
    st.session_state.user_name = cookie_user_name

if 'page_active' not in st.session_state:
    st.session_state.page_active = "🏠 Tableau de bord"
if 'appart_cible' not in st.session_state:
    st.session_state.appart_cible = None

if not st.session_state.auth:
    st.title("🔐 Résidence PARADISO - Interface Sécurisée")
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

elif not st.session_state.user_name or st.session_state.user_name == "":
    st.title("👤 Configuration de votre session")
    st.markdown("Veuillez saisir votre Nom et Prénom pour cette session. Ces informations seront affichées à l'écran et associées aux fiches clients que vous enregistrerez.")
    
    l_col, _ = st.columns([1.2, 2])
    with l_col:
        with st.form("username_form"):
            nom_utilisateur = st.text_input("Nom & Prénom de l'utilisateur *")
            if st.form_submit_button("Valider et Accéder à l'application 🚀"):
                if not nom_utilisateur.strip():
                    st.error("Veuillez saisir votre nom.")
                else:
                    cookie_manager.set("auth_user_name", nom_utilisateur.strip(), expires_at=datetime.now() + timedelta(days=30))
                    st.session_state.user_name = nom_utilisateur.strip()
                    import time as time_mod
                    time_mod.sleep(0.5)
                    st.rerun()

else:
    # Affichage utilisateur connecté
    st.markdown(
        f"<div style='text-align: right; font-size: 14px; font-weight: bold; color: #7f8c8d; margin-bottom: -10px; margin-top: -10px;'>"
        f"👤 Utilisateur connecté : <span style='color: #2c3e50;'>{st.session_state.user_name}</span>"
        f"</div>", 
        unsafe_allow_html=True
    )
    
    bloques, occupes = obtenir_etats()
    
    st.sidebar.image("https://img.icons8.com/color/96/city-buildings.png", width=64)
    st.sidebar.markdown(f"**Rôle Actif:** `{st.session_state.role.upper()}`")
    st.sidebar.info(f"📍 Ouagadougou : {datetime.now(CONFIG['TZ_BF']).strftime('%H:%M')}")
    
    def sync_menu():
        st.session_state.page_active = st.session_state._menu_radio
        
    menu = st.sidebar.radio("Navigation", [
        "🏠 Tableau de bord", 
        "📝 Enregistrement Client", 
        "🗂️ Historique des Séjours",
        "🛠️ Dépenses & Maintenance", 
        "⚙️ ADMINISTRATION", 
        "📈 RAPPORT PDF",
        "💬 Messagerie Interne"
    ], index=["🏠 Tableau de bord", "📝 Enregistrement Client", "🗂️ Historique des Séjours", "🛠️ Dépenses & Maintenance", "⚙️ ADMINISTRATION", "📈 RAPPORT PDF", "💬 Messagerie Interne"].index(st.session_state.page_active), key="_menu_radio", on_change=sync_menu)
    
    if st.sidebar.button("Se Déconnecter 🚪"): 
        cookie_manager.delete("auth_role")
        cookie_manager.delete("auth_user_name")
        st.session_state.auth = False
        st.session_state.role = None
        st.session_state.user_name = ""
        st.session_state.page_active = "🏠 Tableau de bord"
        import time as time_mod
        time_mod.sleep(0.5)
        st.rerun()

    # --- 1. DASHBOARD OVERHAUL ---
    if st.session_state.page_active == "🏠 Tableau de bord":
        st.header("Cockpit de Gestion - Résidence PARADISO")
        st.markdown("Pilotez toutes les opérations en temps réel directement depuis cette page d'accueil.")
        
        # --- RECHERCHE GLOBALE RAPIDE ---
        search_query = st.text_input("🔍 Recherche rapide de client (Nom, Téléphone, Appartement) :", placeholder="Rechercher un séjour en cours ou passé...")
        if search_query:
            df_sejours = charger("sejours")
            if not df_sejours.empty:
                query_lower = search_query.lower()
                df_filtered = df_sejours[
                    df_sejours["Client_Nom"].astype(str).str.lower().str.contains(query_lower) |
                    df_sejours["Tel_Client"].astype(str).str.lower().str.contains(query_lower) |
                    df_sejours["Appartement"].astype(str).str.lower().str.contains(query_lower)
                ]
                
                if df_filtered.empty:
                    st.info("Aucun séjour trouvé pour cette recherche.")
                else:
                    st.markdown("##### Résultats de recherche :")
                    for _, row in df_filtered.head(5).iterrows():
                        col_r1, col_r2, col_r3, col_r4 = st.columns([2, 1.5, 1.5, 1])
                        client_nom = row.get("Client_Nom", "")
                        appart_nom = row.get("Appartement", "")
                        date_entree = row.get("Date_Entree", "")
                        date_sortie = row.get("Date_Sortie", "")
                        statut_sej = row.get("Statut", "")
                        id_sej = row.get("id", "")
                        
                        col_r1.markdown(f"**{client_nom}** ({row.get('Tel_Client', '')})")
                        col_r2.markdown(f"🏠 {appart_nom} | Du {date_entree} au {date_sortie}")
                        col_r3.markdown(f"Statut: `{statut_sej}` | Paiement: `{row.get('Paiement', '')}` ({row.get('Mode_Paiement', 'Espèces')})")
                        
                        if col_r4.button("✏️ Modifier", key=f"search_edit_{id_sej}", use_container_width=True):
                            st.session_state.editing_search_id = id_sej
                            st.session_state.selected_app = None
                            st.rerun()
                            
                    if "editing_search_id" in st.session_state and st.session_state.editing_search_id:
                        selected_id = st.session_state.editing_search_id
                        selected_rows = df_sejours[df_sejours["id"] == selected_id]
                        if not selected_rows.empty:
                            selected_row = selected_rows.iloc[0]
                            st.markdown(f"### ✏️ Modification du séjour de **{selected_row.get('Client_Nom')}** (ID: {selected_id})")
                            with st.form(f"search_edit_form_{selected_id}"):
                                try: d_entree_val = datetime.strptime(str(selected_row.get("Date_Entree")), "%Y-%m-%d").date()
                                except: d_entree_val = date.today()
                                try: d_nais_val = datetime.strptime(str(selected_row.get("Date_Naissance")), "%Y-%m-%d").date()
                                except: d_nais_val = date(1990,1,1)
                                try: d_sortie_val = datetime.strptime(str(selected_row.get("Date_Sortie")), "%Y-%m-%d").date()
                                except: d_sortie_val = date.today()
                                nuits_val = max(1, (d_sortie_val - d_entree_val).days)
                                
                                c1, c2, c3 = st.columns(3)
                                with c1:
                                    e_nom = st.text_input("Nom Client", value=str(selected_row.get("Client_Nom", "")))
                                    e_dnais = st.date_input("Date Naissance", value=d_nais_val, min_value=date(1920,1,1))
                                    e_tel = st.text_input("Téléphone Complet", value=str(selected_row.get("Tel_Client", "")))
                                    e_prov = st.text_input("Provenance", value=str(selected_row.get("Provenance", "")))
                                with c2:
                                    piece_type_actuel = selected_row.get("Piece_Type", "CNI")
                                    piece_options = ["CNI", "Passeport", "Permis", "Carte Séjour"]
                                    e_piece = st.selectbox("Type Pièce", piece_options, index=piece_options.index(piece_type_actuel) if piece_type_actuel in piece_options else 0)
                                    e_pnum = st.text_input("N° Pièce", value=str(selected_row.get("Piece_Num", "")))
                                    e_dent = st.date_input("Date d'Entrée", value=d_entree_val)
                                    e_nuits = st.number_input("Nombre de Nuits", min_value=1, step=1, value=nuits_val)
                                with c3:
                                    app_list = CONFIG["APPARTEMENTS"]
                                    cur_app = str(selected_row.get("Appartement", app_list[0]))
                                    e_app = st.selectbox("Appartement", app_list, index=app_list.index(cur_app) if cur_app in app_list else 0)
                                    m_tot_val = float(selected_row.get("Montant_Total", e_nuits * CONFIG["PRIX_NUITEE"]) or (e_nuits * CONFIG["PRIX_NUITEE"]))
                                    e_montant = st.number_input("Montant Total (F CFA)", value=int(m_tot_val), step=1000)
                                    val_paiement_s = str(selected_row.get("Paiement", "Non Payé")).lower()
                                    e_paiement = st.selectbox("Statut Paiement", ["Non Payé", "Payé"], index=1 if val_paiement_s in ["payé", "paye"] else 0)
                                    cur_mode_p = str(selected_row.get("Mode_Paiement", "Espèces"))
                                    e_mode_p = st.selectbox("Mode de Règlement", MODES_PAIEMENT, index=MODES_PAIEMENT.index(cur_mode_p) if cur_mode_p in MODES_PAIEMENT else 0)
                                    e_statut = st.selectbox("Statut Séjour", ["En cours", "Terminé"], index=1 if str(selected_row.get("Statut", "En cours")).lower() == "terminé" else 0)

                                st.write("---")
                                c_act1, c_act2 = st.columns(2)
                                with c_act1:
                                    e_enom = st.text_input("Employé de Garde", value=str(selected_row.get("Employe_Nom", "")))
                                    e_rais = st.text_area("Raison du séjour", value=str(selected_row.get("Raison", "")))
                                with c_act2:
                                    e_dnom = st.text_input("Nom Démarcheur", value=str(selected_row.get("Demarcheur_Nom", "")))
                                    e_comm = st.number_input("Commission (F CFA)", value=int(float(selected_row.get("Commission", 0) or 0)))

                                c_btn1, c_btn2 = st.columns(2)
                                with c_btn1:
                                    if st.form_submit_button("SAUVEGARDER LES MODIFICATIONS 💾", use_container_width=True):
                                        dsor_edit = e_dent + timedelta(days=e_nuits)
                                        updated_data = {
                                            "Client_Nom": e_nom, "Date_Naissance": str(e_dnais), "Provenance": e_prov,
                                            "Piece_Type": e_piece, "Piece_Num": e_pnum, "Tel_Client": e_tel, 
                                            "Date_Entree": str(e_dent), "Date_Sortie": str(dsor_edit), "Raison": e_rais, 
                                            "Appartement": e_app, "Employe_Nom": e_enom, 
                                            "Demarcheur_Nom": e_dnom, "Montant_Total": e_montant, 
                                            "Commission": e_comm, "Statut": e_statut, "Paiement": e_paiement,
                                            "Mode_Paiement": e_mode_p
                                        }
                                        patch_sejour(selected_id, updated_data)
                                        st.success("✅ Modifications enregistrées !")
                                        st.session_state.editing_search_id = None
                                        st.cache_data.clear()
                                        import time as time_mod
                                        time_mod.sleep(1.5)
                                        st.rerun()
                                with c_btn2:
                                    if st.form_submit_button("Annuler", use_container_width=True):
                                        st.session_state.editing_search_id = None
                                        st.rerun()
            st.divider()

        # --- CARTES D'ÉTAT DES APPARTEMENTS (AVEC ALERTES 11H00) ---
        cols = st.columns(4)
        for i, app in enumerate(CONFIG["APPARTEMENTS"]):
            with cols[i]:
                if app in bloques:
                    html_card = f"""<div class='card card-maintenance'>
                                    <h3>{app}</h3><p>❌ MAINTENANCE</p>
                                    <small>{bloques[app]}</small></div>"""
                    st.markdown(html_card, unsafe_allow_html=True)
                elif app in occupes:
                    info = occupes[app]
                    etat_paiement = str(info.get("paiement", "Non Payé")).strip()
                    est_paye = (etat_paiement.lower() in ["payé", "paye"])
                    affichage_paiement = f"Payé ({info.get('mode_paiement', 'Espèces')})" if est_paye else "Non Payé"
                    color_paiement = "#2ecc71" if est_paye else "#e74c3c"
                    
                    if info.get("retard"):
                        html_card = f"""<div class='card card-retard'>
                                        <h3>{app}</h3><p>⚠️ RETARD LIBÉRATION</p>
                                        <small>Devait libérer le :<br>{info['fin']}</small>
                                        <br><span style='background-color:{color_paiement}; color:white; padding: 2px 6px; border-radius:4px; font-size:12px; font-weight:bold;'>Paiement : {affichage_paiement}</span>
                                        </div>"""
                    elif info.get("depart_aujourdhui"):
                        html_card = f"""<div class='card card-depart-today'>
                                        <h3>{app}</h3><p>🟡 LIBÉRATION AUJOURD'HUI</p>
                                        <small>Départ avant 11h00 :<br>{info['fin']}</small>
                                        <br><span style='background-color:{color_paiement}; color:white; padding: 2px 6px; border-radius:4px; font-size:12px; font-weight:bold;'>Paiement : {affichage_paiement}</span>
                                        </div>"""
                    else:
                        html_card = f"""<div class='card card-occupe'>
                                        <h3>{app}</h3><p>🔴 OCCUPÉ</p>
                                        <small>Libre le :<br>{info['fin']}</small>
                                        <br><span style='background-color:{color_paiement}; color:white; padding: 2px 6px; border-radius:4px; font-size:12px; font-weight:bold;'>Paiement : {affichage_paiement}</span>
                                        </div>"""
                    st.markdown(html_card, unsafe_allow_html=True)
                else:
                    html_card = f"""<div class='card card-libre'>
                                    <h3>{app}</h3><p>🟢 LIBRE</p></div>"""
                    st.markdown(html_card, unsafe_allow_html=True)
                
                is_selected = ("selected_app" in st.session_state and st.session_state.selected_app == app)
                btn_label = f"⚙️ Gérer {app}" if not is_selected else f"⭐️ Activé ({app})"
                if st.button(btn_label, key=f"select_{app}", use_container_width=True, type="secondary" if not is_selected else "primary"):
                    st.session_state.selected_app = app
                    st.session_state.editing_search_id = None
                    st.rerun()
                    
        if "selected_app" not in st.session_state or st.session_state.selected_app is None:
            st.session_state.selected_app = CONFIG["APPARTEMENTS"][0]
            
        selected_app = st.session_state.selected_app
        st.write("")
        st.markdown(f"### ⚙️ Cockpit de Contrôle : **{selected_app}**")
        
        # --- PANNEAU CONTEXTUEL ---
        if selected_app in bloques:
            st.warning(f"Cet appartement est actuellement bloqué pour maintenance. Motif : **{bloques[selected_app]}**")
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                if st.button("🟢 Rendre disponible (Terminer la maintenance)", key=f"m_dispo_{selected_app}", use_container_width=True, type="primary"):
                    actualiser_maintenance(selected_app, "Disponible (Fin de maintenance)", "")
                    st.success(f"L'appartement {selected_app} est à nouveau disponible.")
                    st.cache_data.clear()
                    import time as time_mod
                    time_mod.sleep(1.5)
                    st.rerun()
            with c_m2:
                new_reason = st.text_input("Modifier le motif de maintenance :", value=bloques[selected_app], key=f"m_reason_{selected_app}")
                if st.button("Sauvegarder le nouveau motif", key=f"m_save_reason_{selected_app}", use_container_width=True):
                    actualiser_maintenance(selected_app, "Inaccessible", new_reason)
                    st.success("Motif de maintenance mis à jour.")
                    st.cache_data.clear()
                    import time as time_mod
                    time_mod.sleep(1.5)
                    st.rerun()
                    
        elif selected_app in occupes:
            info = occupes[selected_app]
            etat_paiement = str(info.get("paiement", "Non Payé")).strip()
            est_paye = (etat_paiement.lower() in ["payé", "paye"])
            
            if info.get("retard"):
                st.error("🚨 **ATTENTION : RETARD DE LIBÉRATION (PASSÉ 11H00 GMT)**. Veuillez procéder au Check-out ou ajouter une nuitée supplémentaire.")
            elif info.get("depart_aujourdhui"):
                st.warning("⏰ **RAPPEL : Déchéance aujourd'hui à 11h00 GMT**. Vérifier le départ ou la prolongation.")

            c_info, c_actions = st.columns([1.5, 1])
            with c_info:
                st.markdown(f"""
                📍 **Résumé du séjour en cours :**
                - **Client :** `{info['client']}`
                - **Téléphone :** `{info['tel']}`
                - **Date d'Entrée :** `{info['debut']}`
                - **Libération prévue :** `{info['fin']}`
                - **Montant Total :** `{int(info['montant']):,} F CFA`
                - **Statut du Paiement :** {'🟢 Payé' if est_paye else '🔴 Non Payé'} ({info.get('mode_paiement', 'Espèces')})
                """)
                
                if st.checkbox("✏️ Modifier / Prolonger ce séjour", key=f"chk_edit_{selected_app}"):
                    df_sejours = charger("sejours")
                    if not df_sejours.empty:
                        selected_rows = df_sejours[df_sejours["id"] == info["id_sej"]]
                        if not selected_rows.empty:
                            selected_row = selected_rows.iloc[0]
                            with st.form(f"inline_edit_form_{selected_app}"):
                                try: d_entree_val = datetime.strptime(str(selected_row.get("Date_Entree")), "%Y-%m-%d").date()
                                except: d_entree_val = date.today()
                                try: d_nais_val = datetime.strptime(str(selected_row.get("Date_Naissance")), "%Y-%m-%d").date()
                                except: d_nais_val = date(1990,1,1)
                                try: d_sortie_val = datetime.strptime(str(selected_row.get("Date_Sortie")), "%Y-%m-%d").date()
                                except: d_sortie_val = date.today()
                                nuits_val = max(1, (d_sortie_val - d_entree_val).days)
                                
                                ec1, ec2 = st.columns(2)
                                with ec1:
                                    e_nom = st.text_input("Nom Client", value=str(selected_row.get("Client_Nom", "")))
                                    e_dnais = st.date_input("Date Naissance", value=d_nais_val)
                                    e_tel = st.text_input("Téléphone Complet", value=str(selected_row.get("Tel_Client", "")))
                                    e_prov = st.text_input("Provenance", value=str(selected_row.get("Provenance", "")))
                                    piece_type_actuel = selected_row.get("Piece_Type", "CNI")
                                    piece_options = ["CNI", "Passeport", "Permis", "Carte Séjour"]
                                    e_piece = st.selectbox("Type Pièce", piece_options, index=piece_options.index(piece_type_actuel) if piece_type_actuel in piece_options else 0)
                                with ec2:
                                    e_pnum = st.text_input("N° Pièce", value=str(selected_row.get("Piece_Num", "")))
                                    e_dent = st.date_input("Date d'Entrée", value=d_entree_val)
                                    e_nuits = st.number_input("Nombre de Nuits", min_value=1, step=1, value=nuits_val)
                                    m_tot_val = float(selected_row.get("Montant_Total", e_nuits * CONFIG["PRIX_NUITEE"]) or (e_nuits * CONFIG["PRIX_NUITEE"]))
                                    e_montant = st.number_input("Montant Total", value=int(m_tot_val), step=1000)
                                    val_paiement_i = str(selected_row.get("Paiement", "Non Payé")).lower()
                                    e_paiement = st.selectbox("Statut Paiement", ["Non Payé", "Payé"], index=1 if val_paiement_i in ["payé", "paye"] else 0)
                                    cur_mode = str(selected_row.get("Mode_Paiement", "Espèces"))
                                    e_mode_p = st.selectbox("Mode de Règlement", MODES_PAIEMENT, index=MODES_PAIEMENT.index(cur_mode) if cur_mode in MODES_PAIEMENT else 0)
                                
                                st.write("---")
                                ec_act1, ec_act2 = st.columns(2)
                                with ec_act1:
                                    e_enom = st.text_input("Employé de Garde", value=str(selected_row.get("Employe_Nom", "")))
                                    e_rais = st.text_area("Raison", value=str(selected_row.get("Raison", "")))
                                with ec_act2:
                                    e_dnom = st.text_input("Nom Démarcheur", value=str(selected_row.get("Demarcheur_Nom", "")))
                                    e_comm = st.number_input("Commission (F CFA)", value=int(float(selected_row.get("Commission", 0) or 0)))

                                if st.form_submit_button("SAUVEGARDER LES MODIFICATIONS 💾", use_container_width=True):
                                    dsor_edit = e_dent + timedelta(days=e_nuits)
                                    updated_data = {
                                        "Client_Nom": e_nom, "Date_Naissance": str(e_dnais), "Provenance": e_prov,
                                        "Piece_Type": e_piece, "Piece_Num": e_pnum, "Tel_Client": e_tel, 
                                        "Date_Entree": str(e_dent), "Date_Sortie": str(dsor_edit), "Raison": e_rais, 
                                        "Appartement": selected_app, "Employe_Nom": e_enom, 
                                        "Demarcheur_Nom": e_dnom, "Montant_Total": e_montant, 
                                        "Commission": e_comm, "Paiement": e_paiement, "Mode_Paiement": e_mode_p
                                    }
                                    patch_sejour(info['id_sej'], updated_data)
                                    st.success("✅ Modifications enregistrées !")
                                    st.cache_data.clear()
                                    import time as time_mod
                                    time_mod.sleep(1.5)
                                    st.rerun()
            
            with c_actions:
                st.markdown("**Actions :**")
                if not est_paye:
                    if st.button("Valider Paiement 💸", key=f"pay_dash_{selected_app}", use_container_width=True, type="primary"):
                        patch_sejour(info['id_sej'], {"Paiement": "Payé"})
                        st.success("✅ Paiement validé !")
                        st.cache_data.clear()
                        import time as time_mod
                        time_mod.sleep(1.5)
                        st.rerun()
                
                pdf_bytes = generer_recu_pdf(info, selected_app)
                st.download_button("🖨️ Télécharger Reçu PDF", data=pdf_bytes, file_name=f"Recu_{selected_app}.pdf", mime="application/pdf", key=f"dl_dash_{selected_app}", use_container_width=True)
                
                msg = f"Bonjour {info['client']}, voici le récapitulatif de votre séjour à {selected_app}. Montant total: {int(info['montant']):,} F CFA. Statut du paiement: {etat_paiement} ({info.get('mode_paiement', 'Espèces')})."
                url_msg = urllib.parse.quote(msg)
                st.markdown(f"<a href='https://wa.me/{info['tel'].replace('+', '')}?text={url_msg}' target='_blank' style='display:block; text-align:center; background-color:#25D366; color:white; padding:8px; border-radius:4px; text-decoration:none; margin-bottom:10px; font-size:14px; font-weight:bold;'>📱 Envoyer Reçu (WhatsApp)</a>", unsafe_allow_html=True)
                
                with st.popover("💸 Déclarer une Dépense", use_container_width=True):
                    with st.form(f"dep_form_{selected_app}", clear_on_submit=True):
                        motif_dep = st.text_input("Motif *", placeholder="Ex: Climatisation / Plomberie")
                        montant_dep = st.number_input("Montant (F CFA) *", min_value=100, step=100)
                        if st.form_submit_button("Valider la dépense"):
                            if motif_dep and montant_dep:
                                nouvel_id = f"DEP-{uuid.uuid4().hex[:5].upper()}"
                                d_obj = {
                                    "id": nouvel_id, 
                                    "Date": str(date.today()), 
                                    "Motif": motif_dep, 
                                    "Montant": montant_dep, 
                                    "Appartement": selected_app, 
                                    "Mois": datetime.now(CONFIG["TZ_BF"]).strftime("%m-%Y")
                                }
                                if sauver(d_obj, "depenses"):
                                    st.success("Dépense enregistrée !")
                                    st.cache_data.clear()
                                    import time as time_mod
                                    time_mod.sleep(1)
                                    st.rerun()
                            else:
                                st.warning("Veuillez remplir tous les champs.")

                if st.button("🏁 Mettre fin au séjour (Check-out)", key=f"fin_dash_{selected_app}", use_container_width=True, type="secondary"):
                    patch_sejour(info['id_sej'], {
                        "Statut": "Terminé",
                        "Paiement": "Payé",
                        "Date_Sortie": str(datetime.now(CONFIG["TZ_BF"]).date())
                    })
                    st.success(f"Séjour terminé pour {selected_app}.")
                    st.cache_data.clear()
                    import time as time_mod
                    time_mod.sleep(1.5)
                    st.rerun()
                    
        else:
            st.success(f"L'appartement **{selected_app}** est libre.")
            c_reg, c_maint = st.columns([2, 1])
            with c_reg:
                st.markdown("##### 📝 Enregistrer un Client :")
                with st.form(f"register_form_{selected_app}", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        nom = st.text_input("Nom Client *", placeholder="Jean Dupont")
                        dnais = st.date_input("Date de Naissance", value=date(1990,1,1), min_value=date(1920,1,1))
                        prov = st.text_input("Provenance (Pays/Ville)")
                        col_ind, col_tel = st.columns([1, 2])
                        with col_ind:
                            indicatif = st.text_input("Indicatif", value="+226")
                        with col_tel:
                            tel = st.text_input("Téléphone *", placeholder="70 00 00 00")
                        piece = st.selectbox("Type Pièce", ["CNI", "Passeport", "Permis", "Carte Séjour"])
                        pnum = st.text_input("N° Pièce *")
                    with c2:
                        dent = st.date_input("Date d'Entrée", value=date.today())
                        nuits = st.number_input("Nombre de Nuits *", min_value=1, step=1)
                        statut_paiement = st.selectbox("Statut Paiement", ["Non Payé", "Payé"])
                        mode_paiement = st.selectbox("Mode de Règlement", MODES_PAIEMENT)
                        rais_s = st.text_area("Raison du séjour", height=60)
                        enom = st.text_input("Employé Responsable", value=st.session_state.get("user_name", ""))
                        etel = st.text_input("Téléphone de l'Employé")
                    
                    st.markdown("---")
                    c_com1, c_com2 = st.columns(2)
                    with c_com1:
                        dnom = st.text_input("Nom du Démarcheur (Optionnel)")
                    with c_com2:
                        dtel = st.text_input("Téléphone du Démarcheur")
                        
                    if st.form_submit_button("VALIDER L'ENREGISTREMENT ✅", use_container_width=True):
                        if not nom or not tel or not pnum:
                            st.warning("Veuillez remplir les champs obligatoires (*)")
                        else:
                            dsor = dent + timedelta(days=nuits)
                            total = nuits * CONFIG["PRIX_NUITEE"]
                            comm = (total * 0.1) if dnom else 0
                            nouvel_id = f"VIP-{uuid.uuid4().hex[:6].upper()}"
                            tel_complet = f"{indicatif}{tel}".replace(" ", "")
                            data = {
                                "id": nouvel_id, "Client_Nom": nom, "Date_Naissance": str(dnais), "Provenance": prov,
                                "Piece_Type": piece, "Piece_Num": pnum, "Tel_Client": tel_complet, "Date_Entree": str(dent), 
                                "Date_Sortie": str(dsor), "Raison": rais_s, "Appartement": selected_app, "Employe_Nom": enom, 
                                "Employe_Tel": etel, "Demarcheur_Nom": "Aucun" if not dnom else dnom, 
                                "Demarcheur_Tel": "Aucun" if not dtel else dtel, "Montant_Total": total, 
                                "Commission": comm, "Mois": dent.strftime("%m-%Y"), "Statut": "En cours",
                                "Paiement": statut_paiement, "Mode_Paiement": mode_paiement
                            }
                            if sauver(data, "sejours"): 
                                st.success("Enregistrement réussi !")
                                st.cache_data.clear()
                                import time as time_mod
                                time_mod.sleep(1.5)
                                st.rerun()
                                
            with c_maint:
                st.markdown("##### 🔧 Mettre en Maintenance :")
                with st.form(f"maint_form_{selected_app}"):
                    rais_m = st.text_area("Observations / Motifs de blocage", height=120, placeholder="Ex: Panne climatisation...")
                    if st.form_submit_button("Bloquer pour Maintenance 🛠️", use_container_width=True):
                        actualiser_maintenance(selected_app, "Inaccessible", rais_m)
                        st.success(f"{selected_app} bloqué pour maintenance.")
                        st.cache_data.clear()
                        import time as time_mod
                        time_mod.sleep(1.5)
                        st.rerun()

    # --- 2. ENREGISTREMENT CLIENT ---
    elif st.session_state.page_active == "📝 Enregistrement Client":
        st.header("Nouvelle Fiche Client")
        libres = [a for a in CONFIG["APPARTEMENTS"] if a not in bloques and a not in occupes]
        
        idx_appart = 0
        if st.session_state.appart_cible and st.session_state.appart_cible in libres:
            idx_appart = libres.index(st.session_state.appart_cible)
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
                    col_ind, col_tel = st.columns([1, 2])
                    with col_ind:
                        indicatif = st.text_input("Indicatif", value="+226")
                    with col_tel:
                        tel = st.text_input("Téléphone *", placeholder="70 00 00 00")
                    piece = st.selectbox("Type Pièce", ["CNI", "Passeport", "Permis", "Carte Séjour"])
                    pnum = st.text_input("N° Pièce *")
                with c3:
                    dent = st.date_input("Date d'Entrée", value=date.today())
                    nuits = st.number_input("Nombre de Nuits *", min_value=1, step=1)
                    app = st.selectbox("Appartement Attribué", libres, index=idx_appart)
                    statut_paiement = st.selectbox("Statut Paiement", ["Non Payé", "Payé"])
                    mode_paiement = st.selectbox("Mode de Règlement", MODES_PAIEMENT)

                st.subheader("Acteurs du Dossier")
                c_act1, c_act2 = st.columns(2)
                with c_act1:
                    rais_s = st.text_area("Raison du séjour", height=100)
                    enom = st.text_input("Employé de Garde Responsable", value=st.session_state.get("user_name", ""))
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
                        nouvel_id = f"VIP-{uuid.uuid4().hex[:6].upper()}"
                        
                        tel_complet = f"{indicatif}{tel}".replace(" ", "")
                        data = {
                            "id": nouvel_id, "Client_Nom": nom, "Date_Naissance": str(dnais), "Provenance": prov,
                            "Piece_Type": piece, "Piece_Num": pnum, "Tel_Client": tel_complet, "Date_Entree": str(dent), 
                            "Date_Sortie": str(dsor), "Raison": rais_s, "Appartement": app, "Employe_Nom": enom, 
                            "Employe_Tel": etel, "Demarcheur_Nom": "Aucun" if not dnom else dnom, 
                            "Demarcheur_Tel": "Aucun" if not dtel else dtel, "Montant_Total": total, 
                            "Commission": comm, "Mois": dent.strftime("%m-%Y"), "Statut": "En cours",
                            "Paiement": statut_paiement, "Mode_Paiement": mode_paiement
                        }
                        
                        if sauver(data, "sejours"): 
                            st.toast("Enregistrement réussi !", icon="✅")
                            st.session_state.appart_cible = None 
                            st.cache_data.clear()
                            st.rerun()

    # --- 3. HISTORIQUE ET EDITION CLIENTS ---
    elif st.session_state.page_active == "🗂️ Historique des Séjours":
        st.header("🗂️ Historique des Séjours & Édition")
        st.markdown("Recherchez un client, modifiez ses informations ou générez son reçu (même après son départ).")
        
        df_sejours = charger("sejours")
        if df_sejours.empty:
            st.info("Aucun séjour enregistré pour le moment.")
        else:
            if "Date_Entree" in df_sejours.columns:
                df_sejours = df_sejours.sort_values(by="Date_Entree", ascending=False)
            
            search_query = st.text_input("🔍 Rechercher par Nom de client, Téléphone ou Appartement :", "")
            
            df_filtered = df_sejours.copy()
            if search_query:
                query_lower = search_query.lower()
                df_filtered = df_filtered[
                    df_filtered["Client_Nom"].astype(str).str.lower().str.contains(query_lower) |
                    df_filtered["Tel_Client"].astype(str).str.lower().str.contains(query_lower) |
                    df_filtered["Appartement"].astype(str).str.lower().str.contains(query_lower)
                ]
            
            st.write("---")
            if df_filtered.empty:
                st.warning("Aucun résultat pour cette recherche.")
            else:
                options = []
                for _, row in df_filtered.iterrows():
                    nom = row.get("Client_Nom", "Inconnu")
                    app = row.get("Appartement", "?")
                    debut = row.get("Date_Entree", "")
                    statut = row.get("Statut", "")
                    id_sej = row.get("id", "")
                    options.append(f"{nom} | {app} | Du {debut} | [{statut}] (ID: {id_sej})")
                
                selected_option = st.selectbox("Sélectionnez un séjour pour voir/modifier les détails :", options)
                
                if selected_option:
                    selected_id = selected_option.split("(ID: ")[-1].replace(")", "").strip()
                    selected_row = df_sejours[df_sejours["id"] == selected_id].iloc[0]
                    
                    st.write("---")
                    st.subheader(f"Détails de : {selected_row.get('Client_Nom', '')}")
                    
                    info_recu = {
                        "client": str(selected_row.get("Client_Nom", "")),
                        "tel": str(selected_row.get("Tel_Client", "")),
                        "debut": str(selected_row.get("Date_Entree", "")),
                        "fin": str(selected_row.get("Date_Sortie", "")),
                        "montant": float(selected_row.get("Montant_Total", 0) or 0),
                        "paiement": str(selected_row.get("Paiement", "Non Payé")),
                        "mode_paiement": str(selected_row.get("Mode_Paiement", "Espèces"))
                    }
                    pdf_bytes = generer_recu_pdf(info_recu, str(selected_row.get("Appartement", "")))
                    st.download_button(
                        "🖨️ Télécharger le Reçu PDF de ce séjour", 
                        data=pdf_bytes, 
                        file_name=f"Recu_{selected_row.get('Appartement', '')}_{selected_row.get('Client_Nom', '')}.pdf", 
                        mime="application/pdf", 
                        type="primary"
                    )
                    
                    with st.expander("✏️ Modifier les informations de ce séjour", expanded=False):
                        with st.form(f"edit_form_{selected_id}"):
                            try: d_entree_val = datetime.strptime(str(selected_row.get("Date_Entree")), "%Y-%m-%d").date()
                            except: d_entree_val = date.today()
                            
                            try: d_nais_val = datetime.strptime(str(selected_row.get("Date_Naissance")), "%Y-%m-%d").date()
                            except: d_nais_val = date(1990,1,1)
                            
                            try: d_sortie_val = datetime.strptime(str(selected_row.get("Date_Sortie")), "%Y-%m-%d").date()
                            except: d_sortie_val = date.today()
                            
                            delta = (d_sortie_val - d_entree_val).days
                            nuits_val = max(1, delta)
                            
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                e_nom = st.text_input("Nom Client", value=str(selected_row.get("Client_Nom", "")))
                                e_dnais = st.date_input("Date Naissance", value=d_nais_val, min_value=date(1920,1,1))
                                e_tel = st.text_input("Téléphone Complet", value=str(selected_row.get("Tel_Client", "")))
                                e_prov = st.text_input("Provenance", value=str(selected_row.get("Provenance", "")))
                            with c2:
                                piece_type_actuel = selected_row.get("Piece_Type", "CNI")
                                piece_options = ["CNI", "Passeport", "Permis", "Carte Séjour"]
                                e_piece = st.selectbox("Type Pièce", piece_options, index=piece_options.index(piece_type_actuel) if piece_type_actuel in piece_options else 0)
                                e_pnum = st.text_input("N° Pièce", value=str(selected_row.get("Piece_Num", "")))
                                e_dent = st.date_input("Date d'Entrée", value=d_entree_val)
                                e_nuits = st.number_input("Nombre de Nuits", min_value=1, step=1, value=nuits_val)
                            with c3:
                                app_list = CONFIG["APPARTEMENTS"]
                                cur_app = str(selected_row.get("Appartement", app_list[0]))
                                e_app = st.selectbox("Appartement", app_list, index=app_list.index(cur_app) if cur_app in app_list else 0)
                                m_tot_val = float(selected_row.get("Montant_Total", e_nuits * CONFIG["PRIX_NUITEE"]) or (e_nuits * CONFIG["PRIX_NUITEE"]))
                                e_montant = st.number_input("Montant Total (F CFA)", value=int(m_tot_val), step=1000)
                                val_paiement = str(selected_row.get("Paiement", "Non Payé")).lower()
                                e_paiement = st.selectbox("Statut Paiement", ["Non Payé", "Payé"], index=1 if val_paiement in ["payé", "paye"] else 0)
                                cur_mode_h = str(selected_row.get("Mode_Paiement", "Espèces"))
                                e_mode_p = st.selectbox("Mode de Règlement", MODES_PAIEMENT, index=MODES_PAIEMENT.index(cur_mode_h) if cur_mode_h in MODES_PAIEMENT else 0)
                                e_statut = st.selectbox("Statut Séjour", ["En cours", "Terminé"], index=1 if str(selected_row.get("Statut", "En cours")).lower() == "terminé" else 0)

                            st.write("---")
                            c_act1, c_act2 = st.columns(2)
                            with c_act1:
                                e_enom = st.text_input("Employé de Garde", value=str(selected_row.get("Employe_Nom", "")))
                                e_rais = st.text_area("Raison du séjour", value=str(selected_row.get("Raison", "")))
                            with c_act2:
                                e_dnom = st.text_input("Nom Démarcheur", value=str(selected_row.get("Demarcheur_Nom", "")))
                                e_comm = st.number_input("Commission (F CFA)", value=int(float(selected_row.get("Commission", 0) or 0)))

                            submit_edit = st.form_submit_button("SAUVEGARDER LES MODIFICATIONS 💾")
                            
                            if submit_edit:
                                dsor_edit = e_dent + timedelta(days=e_nuits)
                                updated_data = {
                                    "Client_Nom": e_nom, "Date_Naissance": str(e_dnais), "Provenance": e_prov,
                                    "Piece_Type": e_piece, "Piece_Num": e_pnum, "Tel_Client": e_tel, 
                                    "Date_Entree": str(e_dent), "Date_Sortie": str(dsor_edit), "Raison": e_rais, 
                                    "Appartement": e_app, "Employe_Nom": e_enom, 
                                    "Demarcheur_Nom": e_dnom, "Montant_Total": e_montant, 
                                    "Commission": e_comm, "Statut": e_statut, "Paiement": e_paiement,
                                    "Mode_Paiement": e_mode_p
                                }
                                patch_sejour(selected_id, updated_data)
                                st.success("✅ Modifications enregistrées avec succès !")
                                st.cache_data.clear()
                                import time as time_mod
                                time_mod.sleep(1.5)
                                st.rerun()

    # --- 4. DEPENSES & MAINTENANCE ---
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
                actualiser_maintenance(app_m, stat_m, rais_m)
                st.toast(f"Statut technique de {app_m} mis à jour.", icon="🔧")
                st.cache_data.clear()
                st.rerun()

    # --- 5. ADMINISTRATION ---
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
                            st.toast("Ligne définitivement supprimée.", icon="✅")
                            st.cache_data.clear()
                            st.rerun()
            else:
                st.info(f"La table '{onglet}' est actuellement vide.")

    # --- 6. RAPPORT PDF ---
    elif st.session_state.page_active == "📈 RAPPORT PDF":
        if st.session_state.role != "admin": 
            st.error("⛔ Zone de comptabilité confidentielle (Direction Uniquement).")
        else:
            st.header("Bilan Comptable Mensuel")
            
            df_s = charger("sejours")
            df_d = charger("depenses")
            
            mois_set = set()
            if not df_d.empty and "Mois" in df_d.columns:
                mois_set.update(df_d["Mois"].dropna().unique())
            
            if not df_s.empty:
                for _, row in df_s.iterrows():
                    try:
                        d_ent = datetime.strptime(str(row["Date_Entree"]), "%Y-%m-%d").date()
                        d_sor = datetime.strptime(str(row["Date_Sortie"]), "%Y-%m-%d").date()
                        
                        curr = d_ent + timedelta(days=1)
                        if curr > d_sor: curr = d_sor
                        
                        while curr <= d_sor:
                            mois_set.add(curr.strftime("%m-%Y"))
                            curr += timedelta(days=1)
                    except:
                        if pd.notna(row.get("Mois")):
                            mois_set.add(str(row.get("Mois")))
            
            mois_list = sorted(list(mois_set), key=lambda x: datetime.strptime(x, "%m-%Y") if x and len(x.split('-'))==2 else datetime.min, reverse=True)
            
            if mois_list:
                sel_m = st.selectbox("Sélectionner la période", mois_list)
                
                if sel_m:
                    try:
                        m_num, year = map(int, sel_m.split("-"))
                    except:
                        m_num, year = 1, 2000
                    
                    d_m = df_d[df_d["Mois"] == sel_m].copy() if not df_d.empty else pd.DataFrame()
                    dep = pd.to_numeric(d_m["Montant"], errors='coerce').fillna(0).sum() if not d_m.empty else 0
                    
                    ca = 0
                    ca_paye = 0
                    ca_attente = 0
                    comm = 0
                    lignes_sejours_mois = []
                    
                    if not df_s.empty:
                        for _, row in df_s.iterrows():
                            try:
                                d_ent = datetime.strptime(str(row["Date_Entree"]), "%Y-%m-%d").date()
                                d_sor = datetime.strptime(str(row["Date_Sortie"]), "%Y-%m-%d").date()
                                
                                nuits_ce_mois = 0
                                curr = d_ent + timedelta(days=1)
                                if curr > d_sor: curr = d_sor
                                while curr <= d_sor:
                                    if curr.month == m_num and curr.year == year:
                                        nuits_ce_mois += 1
                                    curr += timedelta(days=1)
                                
                                if nuits_ce_mois > 0:
                                    total_nuits_sejour = max(1, (d_sor - d_ent).days)
                                    montant_total = float(row.get("Montant_Total", 0) or 0)
                                    commission_totale = float(row.get("Commission", 0) or 0)
                                    
                                    prix_par_nuit = montant_total / total_nuits_sejour
                                    comm_par_nuit = commission_totale / total_nuits_sejour
                                    
                                    montant_ce_mois = prix_par_nuit * nuits_ce_mois
                                    comm_ce_mois = comm_par_nuit * nuits_ce_mois
                                    
                                    ca += montant_ce_mois
                                    comm += comm_ce_mois
                                    
                                    val_paiement = str(row.get("Paiement", "")).lower()
                                    est_paye = (val_paiement in ["payé", "paye"])
                                    
                                    if est_paye:
                                        ca_paye += montant_ce_mois
                                    else:
                                        ca_attente += montant_ce_mois
                                        
                                    lignes_sejours_mois.append({
                                        "Client": str(row.get("Client_Nom", "Inconnu")),
                                        "Appart": str(row.get("Appartement", "?")),
                                        "Dates": f"Du {d_ent.strftime('%d/%m')} au {d_sor.strftime('%d/%m')}",
                                        "Nuits": f"{nuits_ce_mois}/{total_nuits_sejour}",
                                        "Montant": montant_ce_mois
                                    })
                            except:
                                if str(row.get("Mois")) == sel_m:
                                    m_val = float(row.get("Montant_Total", 0) or 0)
                                    c_val = float(row.get("Commission", 0) or 0)
                                    ca += m_val
                                    comm += c_val
                                    val_paiement = str(row.get("Paiement", "")).lower()
                                    est_paye = (val_paiement in ["payé", "paye"])
                                    if est_paye: ca_paye += m_val
                                    else: ca_attente += m_val
                                    
                                    lignes_sejours_mois.append({
                                        "Client": str(row.get("Client_Nom", "Inconnu")),
                                        "Appart": str(row.get("Appartement", "?")),
                                        "Dates": "Ancien format",
                                        "Nuits": "?",
                                        "Montant": m_val
                                    })
                                    
                    df_s_mois = pd.DataFrame(lignes_sejours_mois)
                    net = ca - comm - dep
                    
                    st.write("")
                    st.markdown(f"### Résultat du mois ({sel_m})")
                    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                    f_col1.metric("CA GLOBAL (PRORATA)", f"{ca:,.0f} F")
                    f_col2.metric("DONT CA ENCAISSÉ (PAYÉ)", f"{ca_paye:,.0f} F", help="Argent déjà reçu")
                    f_col3.metric("DEPENSES", f"{dep:,.0f} F", delta_color="inverse")
                    f_col4.metric("BENEFICE NET", f"{net:,.0f} F", delta="Calculé")

                    st.markdown("---")
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        st.subheader("📋 Séjours impactant ce mois")
                        if not df_s_mois.empty:
                            st.dataframe(df_s_mois, use_container_width=True, hide_index=True)
                        else:
                            st.info("Aucun séjour sur cette période.")
                    
                    with col_t2:
                        st.subheader("📉 Dépenses du mois")
                        if not d_m.empty: 
                            st.dataframe(d_m[["Date", "Motif", "Appartement", "Montant"]], use_container_width=True, hide_index=True)
                        else:
                            st.info("Aucune dépense enregistrée sur cette période.")
                        
                    st.markdown("---")
                    pdf_bytes = imprimer_bilan(sel_m, ca, ca_paye, ca_attente, comm, dep, net, d_m, df_s_mois)
                    st.download_button(
                        label=f"📥 ÉDITER LE BILAN PDF GLOBAL - {sel_m}",
                        data=pdf_bytes,
                        file_name=f"Bilan_Residence_{sel_m}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )
            else:
                st.info("Aucune donnée disponible pour le moment.")

    # --- 7. MESSAGERIE INTERNE (CHAT) ---
    elif st.session_state.page_active == "💬 Messagerie Interne":
        st.header("💬 Messagerie Équipe")
        st.markdown("Communiquez en temps réel avec la Direction et les Employés. Vous pouvez supprimer vos messages si besoin.")
        
        messages = get_chat_messages()
        chat_container = st.container(height=500)
        
        with chat_container:
            if not messages:
                st.info("La discussion est vide. Envoyez le premier message !")
            
            for msg in messages:
                is_admin = (msg["sender"] == "admin")
                avatar_icon = "👨‍💼" if is_admin else "👤"
                sender_label = "Direction (Admin)" if is_admin else "Employé(e)"
                
                with st.chat_message(sender_label, avatar=avatar_icon):
                    col_msg, col_del = st.columns([0.9, 0.1])
                    with col_msg:
                        st.caption(f"_{msg['timestamp']}_")
                        if msg["type"] == "text":
                            st.write(msg["content"])
                        elif msg["type"] == "image":
                            st.image(msg["content"], width=300)
                        elif msg["type"] == "audio":
                            st.audio(msg["content"])
                    
                    with col_del:
                        if st.button("🗑️", key=f"del_{msg['id']}", help="Supprimer ce message"):
                            delete_chat_message(msg['id'])
                            st.rerun()

        st.divider()
        
        prompt = st.chat_input("Écrire un message texte...")
        if prompt:
            new_msg = {
                "id": uuid.uuid4().hex,
                "timestamp": datetime.now(CONFIG["TZ_BF"]).strftime("%d/%m/%Y à %H:%M"),
                "sender": st.session_state.role,
                "type": "text",
                "content": prompt
            }
            save_chat_message(new_msg)
            st.rerun()
            
        with st.expander("📎 Envoyer une Photo ou Note Vocale (Média)"):
            c_img, c_aud = st.columns(2)
            with c_img:
                img_file = st.file_uploader("📤 Joindre une Image", type=["png", "jpg", "jpeg"], accept_multiple_files=False)
                if img_file:
                    if st.button("Confirmer l'envoi de l'image 🖼️", use_container_width=True):
                        filename = f"{uuid.uuid4().hex}.jpg"
                        filepath = os.path.join(CHAT_MEDIA_DIR, filename)
                        with open(filepath, "wb") as f:
                            f.write(img_file.getbuffer())
                        
                        new_msg = {
                            "id": uuid.uuid4().hex,
                            "timestamp": datetime.now(CONFIG["TZ_BF"]).strftime("%d/%m/%Y à %H:%M"),
                            "sender": st.session_state.role,
                            "type": "image",
                            "content": filepath
                        }
                        save_chat_message(new_msg)
                        st.rerun()
                        
            with c_aud:
                aud_file = st.audio_input("🎙️ Enregistrer une note vocale")
                if aud_file:
                    if st.button("Confirmer l'envoi du vocal 🎵", use_container_width=True):
                        filename = f"{uuid.uuid4().hex}.wav"
                        filepath = os.path.join(CHAT_MEDIA_DIR, filename)
                        with open(filepath, "wb") as f:
                            f.write(aud_file.getbuffer())
                            
                        new_msg = {
                            "id": uuid.uuid4().hex,
                            "timestamp": datetime.now(CONFIG["TZ_BF"]).strftime("%d/%m/%Y à %H:%M"),
                            "sender": st.session_state.role,
                            "type": "audio",
                            "content": filepath
                        }
                        save_chat_message(new_msg)
                        st.rerun()
