import streamlit as st
import hashlib
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import io
import base64
import requests
from requests.exceptions import RequestException

# Configuration de la page
st.set_page_config(
    page_title="Gestion des Achats",
    layout="wide"
)

# --- Constantes ---
NUMERO_PAIEMENT = "+221773867580"
DEFAULT_COUNTRY_CODE = "+221" # Indicatif par défaut (Sénégal)

# *** MODIFICATION CRITIQUE ICI : URL DE L'API RENDER ***
FASTAPI_BASE_URL = "https://gestion-achatss-io.onrender.com" 
# ********************************************************


# ----------------------------------------------------------------------
# --- FONCTIONS CRITIQUES D'INTERACTION AVEC L'API FASTAPI/RENDER ---
# ----------------------------------------------------------------------

@st.cache_data(ttl=60) # Mettre en cache pour 60 secondes pour éviter les appels API excessifs
def get_data_from_api(endpoint):
    """Récupère les données d'un point de terminaison de l'API (GET)."""
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}{endpoint}")
        response.raise_for_status() # Lève une exception pour les codes d'erreur 4xx/5xx
        return response.json()
    except RequestException as e:
        # En cas d'échec de la connexion (API inactive ou erreur 5xx), retourne None
        # st.error(f"Erreur de connexion à l'API pour {endpoint}: {e}") # Désactiver cette erreur pour ne pas spammer l'utilisateur
        return None

def handle_api_request(method, endpoint, data=None):
    """
    Gère les requêtes API POST, PUT, DELETE et retourne la réponse JSON.
    Retourne un tuple (success, data_or_error_message).
    """
    url = f"{FASTAPI_BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json', 'accept': 'application/json'}
    
    try:
        if method == 'POST':
            response = requests.post(url, json=data, headers=headers)
        elif method == 'PUT':
            response = requests.put(url, json=data, headers=headers)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            return False, f"Méthode {method} non supportée."

        # Gérer les codes d'erreur HTTP 4xx et 5xx
        response.raise_for_status()
        
        if response.status_code == 204 or not response.content:
            return True, {"message": "Opération réussie"}
        
        # Invalider le cache après une modification (pour forcer le rafraîchissement des données)
        st.cache_data.clear() 
        return True, response.json()

    except RequestException as e:
        error_message = f"Erreur de connexion à l'API : {e}"
        if 'response' in locals() and response.text:
            try:
                # Tenter de récupérer le message d'erreur détaillé de FastAPI (422, etc.)
                error_detail = response.json().get('detail', response.text)
                if isinstance(error_detail, list):
                    # Formater le message d'erreur 422 pour les champs manquants
                    error_message = "Erreur de validation (422) : " + "; ".join([f"{d.get('loc', ['N/A'])[-1]} -> {d.get('msg')}" for d in error_detail])
                else:
                    error_message = f"Erreur API ({response.status_code}): {error_detail}"
            except Exception:
                error_message = f"Erreur API ({response.status_code}): {response.text}"
        
        return False, error_message

# ----------------------------------------------------------------------
# --- FONCTIONS DE CHARGEMENT DE DONNÉES (API) AVEC ROBUSTESSE ---
# ----------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_products_data():
    """Charge les produits depuis l'API et retourne un DataFrame vide ou rempli."""
    data = get_data_from_api("/produits/")
    if data is None or not isinstance(data, list):
        if st.session_state.logged_in:
            # st.error("⚠️ Impossible de charger les données de produits.")
             pass # L'erreur API est gérée silencieusement pour éviter de surcharger
        return pd.DataFrame()

    df = pd.DataFrame(data)
    
    if not df.empty:
        # 1. Définir le mappage complet des colonnes
        rename_map = {
            'id': 'ID Produit',
            'nom': 'Produit',
            'stock': 'Stock Actuel',
            'prix_achat': 'Prix Achat Unitaire (FCFA)',
            'prix_vente': 'Prix Vente Unitaire (FCFA)',
            'fournisseur_id': 'ID Fournisseur'
        }
        
        # 2. Renommer uniquement les colonnes existantes dans le DataFrame
        valid_rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=valid_rename_map)

        # 3. S'assurer que les colonnes nécessaires existent
        required_cols = [
            'ID Produit', 'Produit', 'Stock Actuel', 
            'Prix Achat Unitaire (FCFA)', 'Prix Vente Unitaire (FCFA)', 
            'ID Fournisseur'
        ]
        
        for col in required_cols:
            if col not in df.columns:
                if 'Prix' in col or 'Stock' in col:
                     df[col] = 0.0 # Valeur par défaut numérique
                elif 'ID' in col:
                     df[col] = '' # Valeur par défaut chaîne vide
                else:
                    df[col] = 'Inconnu'


        # 4. Conversion des types
        if 'ID Produit' in df.columns:
             # Assurer que l'ID est une chaîne pour la jointure
             df['ID Produit'] = df['ID Produit'].astype(str) 
        if 'ID Fournisseur' in df.columns:
             # Assurer que l'ID est une chaîne pour la jointure
             df['ID Fournisseur'] = df['ID Fournisseur'].astype(str) 
            
        # S'assurer que les colonnes numériques sont au bon format
        for col_name in ['Prix Achat Unitaire (FCFA)', 'Prix Vente Unitaire (FCFA)', 'Stock Actuel']:
             if col_name in df.columns:
                 df[col_name] = pd.to_numeric(df[col_name], errors='coerce').fillna(0)
                 if 'Stock' in col_name:
                     df[col_name] = df[col_name].astype(int) # Le stock est un entier
            
    # Retourner le DataFrame sans définir l'index 
    return df if not df.empty else pd.DataFrame() 

@st.cache_data(ttl=60)
def load_fournisseurs_data():
    """Charge les fournisseurs depuis l'API et retourne un DataFrame vide ou rempli."""
    data = get_data_from_api("/fournisseurs/")
    if data is None or not isinstance(data, list):
        if st.session_state.logged_in:
             # st.error("⚠️ Impossible de charger les données de fournisseurs.")
             pass
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if not df.empty:
         df = df.rename(columns={
            'nom': 'Nom Fournisseur',
            'contact': 'Contact',
            'adresse': 'Adresse',
            'id': 'ID Fournisseur'
        })
         if 'ID Fournisseur' in df.columns:
             # Assurer que l'ID est une chaîne pour la jointure
             df['ID Fournisseur'] = df['ID Fournisseur'].astype(str) 
             
    # Retourner le DataFrame sans définir l'index
    return df if not df.empty else pd.DataFrame()

@st.cache_data(ttl=60)
def load_commandes_data():
    """Charge les commandes depuis l'API et retourne une liste vide ou remplie."""
    data = get_data_from_api("/commandes/")
    if data is None or not isinstance(data, list):
        if st.session_state.logged_in:
             # st.error("⚠️ Impossible de charger les données de commandes.")
             pass
        return []
    
    return data

# ----------------------------------------------------------------------
# --- FIN DES FONCTIONS D'INTERACTION API ---
# ----------------------------------------------------------------------

# --- Fonctions de hachage du mot de passe ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- Fonctions utilitaires pour le téléchargement ---
@st.cache_data
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Rapport')
    processed_data = output.getvalue()
    return processed_data

@st.cache_data
def to_plain_text_report(df, title="Rapport"):
    report = f"\n\n*** {title.upper()} ***\n\n"
    report += df.to_string(index=False, justify='left', line_width=120)
    
    # Correction : Utiliser les colonnes de l'API (cout_total) si possible
    amount_col = 'Montant' if 'Montant' in df.columns else 'Montant Total'
    
    if amount_col in df.columns or 'Montant Total' in df.columns:
        amount_col_final = amount_col if amount_col in df.columns else 'Montant Total'
        try:
            # S'assurer que les valeurs sont numériques avant la somme
            def clean_amount(x):
                if isinstance(x, str):
                    return x.replace(' FCFA', '').replace(',', '').strip()
                return x
            
            df[amount_col_final] = df[amount_col_final].apply(clean_amount)
            total_amount = pd.to_numeric(df[amount_col_final], errors='coerce').fillna(0).sum()
            
            report += f"\n\n---"
            report += f"\nTOTAL GÉNÉRAL DES MONTANTS: {total_amount:,.0f} FCFA\n"
            report += f"---"
        except Exception:
             pass
        
    return report.encode('utf-8')

def generate_download_buttons(df, filename_base):
    if df.empty:
        st.warning("Aucune donnée disponible pour le téléchargement.")
        return

    col_txt, col_xlsx, _ = st.columns([1, 1, 4]) 

    txt_title = filename_base.replace('_', ' ').replace('Rapport', 'Rapport').capitalize()
    
    # Pour s'assurer que to_plain_text_report reçoit un DataFrame propre pour le téléchargement
    df_for_txt = df.copy() 
    if 'Total (FCFA)' in df_for_txt.columns:
        df_for_txt.rename(columns={'Total (FCFA)': 'Montant Total'}, inplace=True)
    elif 'Montant (FCFA)' in df_for_txt.columns:
        df_for_txt.rename(columns={'Montant (FCFA)': 'Montant Total'}, inplace=True)
        
    txt_data = to_plain_text_report(df_for_txt, title=txt_title) 

    with col_txt:
        st.download_button(
            label="📄 Télécharger en TXT", 
            data=txt_data,
            file_name=f'{filename_base}.txt', 
            mime='text/plain', 
            key=f'txt_download_{filename_base}',
            type="primary"
        )
        
    with col_xlsx:
        st.download_button(
            label="💾 Télécharger en XLSX",
            data=to_excel(df),
            file_name=f'{filename_base}.xlsx',
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f'xlsx_download_{filename_base}'
        )

# --- Base de données : Fonctions d'aide (Utilisateurs locaux) ---

def get_phone_number_from_db(username):
    user_info = st.session_state.USER_DB.get(username)
    if user_info and user_info.get("country_code") and user_info.get("phone_number"):
        return f"{user_info['country_code']}{user_info['phone_number']}"
    return "N/A"

def is_phone_unique(country_code, phone_number, exclude_user=None):
    full_number = f"{country_code}{phone_number}"
    for user, user_info in st.session_state.USER_DB.items():
        if user == exclude_user:
            continue
        if f"{user_info.get('country_code', '')}{user_info.get('phone_number', '')}" == full_number:
            return False
    return True

# --- Initialisation des données locales (Uniquement Users et Charges) ---

if "USER_DB" not in st.session_state:
    st.session_state.USER_DB = {
        "admin": {
            "password_hash": make_hashes("admin123"),
            "is_admin": True,
            "is_active": True,
            "subscription_end_date": None,
            "country_code": DEFAULT_COUNTRY_CODE,
            "phone_number": "770000000"
        },
        "client1": {
            "password_hash": make_hashes("client123"),
            "is_admin": False,
            "is_active": True,
            "subscription_end_date": "2025-11-25",
            "country_code": DEFAULT_COUNTRY_CODE,
            "phone_number": "771111111"
        },
        "YACHE12": {
            "password_hash": make_hashes("babacar12"),
            "is_admin": True,
            "is_active": True,
            "subscription_end_date": None,
            "country_code": DEFAULT_COUNTRY_CODE,
            "phone_number": "773333333"
        }
    }
    # Initialisation pour les anciens utilisateurs si le script a été redémarré
    for user, info in st.session_state.USER_DB.items():
         if "country_code" not in info:
             info["country_code"] = DEFAULT_COUNTRY_CODE
         if "phone_number" not in info:
             info["phone_number"] = "000000000"

if "charges_db" not in st.session_state:
    st.session_state.charges_db = [
        {"id": 1, "nature": "Salaire", "montant": 200000.0, "date": "2025-09-19"},
        {"id": 2, "nature": "Loyer", "montant": 150000.0, "date": "2025-09-20"},
        {"id": 3, "nature": "Marketing", "montant": 50000.0, "date": "2025-09-21"},
    ]
if "next_charge_id" not in st.session_state:
    st.session_state.next_charge_id = 4 

if "user_settings" not in st.session_state:
    st.session_state.user_settings = {}
    for user in st.session_state.USER_DB.keys():
        st.session_state.user_settings[user] = {
            "display_name_format": "full", 
            "company_logo_base64": None
        }

# --- NOUVELLE INITIALISATION : Panier d'achat temporaire (client-side) ---
if "cart" not in st.session_state: 
    st.session_state.cart = {} # {product_id: {'quantity': qty, 'price': price}}

# --- Initialisation de l'état de la session ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "current_view" not in st.session_state:
    st.session_state.current_view = "client"
if "auth_mode" not in st.session_state: 
    st.session_state.auth_mode = "login"

# --- Fonctions de basculement, déconnexion et abonnement ---

def set_view_admin():
    st.session_state.current_view = "admin"

def set_view_client():
    st.session_state.current_view = "client"

def set_auth_mode(mode):
    st.session_state.auth_mode = mode

def logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.is_admin = False
    st.session_state.current_view = "admin"
    st.session_state.auth_mode = "login"
    
    # Vider le panier client.
    st.session_state.cart = {}
    st.cache_data.clear() # Vider le cache des données API
    st.rerun()

def activate_subscription(username):
    today = datetime.now().date()
    new_end_date = today + timedelta(days=30) 
    st.session_state.USER_DB[username]["is_active"] = True
    st.session_state.USER_DB[username]["subscription_end_date"] = new_end_date.strftime("%Y-%m-%d")
    st.success(f"Abonnement de **{username}** activé/prolongé jusqu'au **{new_end_date.strftime('%d-%m-%Y')}**.")

def suspend_subscription(username):
    st.session_state.USER_DB[username]["is_active"] = False
    st.warning(f"Abonnement de **{username}** suspendu (compte rendu inactif).")

def register_user(username, password, country_code, phone_number):
    if username in st.session_state.USER_DB:
        return False, "Ce nom d'utilisateur existe déjà. Il doit être unique."
    
    if not username or not password or not country_code or not phone_number:
        return False, "Veuillez remplir tous les champs obligatoires."

    if not is_phone_unique(country_code, phone_number, exclude_user=None):
         return False, "Ce numéro de téléphone est déjà associé à un autre compte. Veuillez utiliser un numéro unique."


    st.session_state.USER_DB[username] = {
        "password_hash": make_hashes(password),
        "is_admin": False,
        "is_active": False,
        "subscription_end_date": None,
        "country_code": country_code,
        "phone_number": phone_number
    }
    st.session_state.user_settings[username] = {
        "display_name_format": "full", 
            "company_logo_base64": None
    }
    return True, f"Compte **{username}** créé avec succès ! Veuillez payer 5000 FCFA sur le numéro {NUMERO_PAIEMENT} pour l'activation."

def check_subscription_status():
    if st.session_state.is_admin:
        return True
    
    user_info = st.session_state.USER_DB.get(st.session_state.username)
    if not user_info:
        return False

    if user_info["is_active"]:
        sub_end_date_str = user_info["subscription_end_date"]
        
        if sub_end_date_str:
            try:
                sub_end_date = datetime.strptime(sub_end_date_str, "%Y-%m-%d")
                if sub_end_date.date() < datetime.now().date():
                    # Expiration automatique
                    st.session_state.USER_DB[st.session_state.username]["is_active"] = False
                    st.session_state.logged_in = False
                    st.session_state.auth_mode = "login" 
                    st.error("Votre abonnement a expiré. Veuillez vous reconnecter.")
                    return False
            except ValueError:
                # Gérer une date mal formatée
                 st.warning("Date d'abonnement invalide. Contactez l'administrateur.")
                 return False
        return True
    
    return False

def get_display_name(username, format_type):
    """Retourne le nom d'affichage selon le format choisi."""
    name_parts = username.split()
    if format_type == 'initials':
        if len(name_parts) > 1:
            return "".join([p[0].upper() for p in name_parts])
        return username[0].upper()
    
    return " ".join([p.capitalize() for p in name_parts]) if name_parts else username.capitalize()

# --- Fonctions d'affichage (Pages d'authentification) ---

def show_password_reset():
    st.subheader("Réinitialiser le Mot de Passe")
    st.info("Pour des raisons de sécurité, veuillez fournir votre nom d'utilisateur et le numéro de téléphone associé à votre compte.")
    
    with st.form("reset_password_form"):
        username_to_reset = st.text_input("Nom d'utilisateur", key="reset_user")
        
        col_code, col_phone = st.columns([1, 2])
        with col_code:
            reset_country_code = st.text_input("Indicatif Pays", value=DEFAULT_COUNTRY_CODE, key="reset_country_code")
        with col_phone:
            reset_phone_number = st.text_input("Numéro de Téléphone (sans l'indicatif)", key="reset_phone_number")

        new_password = st.text_input("Nouveau mot de passe", type="password", key="reset_new_pass")
        confirm_password = st.text_input("Confirmer le nouveau mot de passe", type="password", key="reset_confirm_pass")
        reset_button = st.form_submit_button("Réinitialiser le mot de passe", type="primary")

        if reset_button:
            user_info = st.session_state.USER_DB.get(username_to_reset)
            
            if not user_info:
                st.error("Nom d'utilisateur non trouvé.")
            elif new_password != confirm_password:
                st.error("Les mots de passe ne correspondent pas.")
            elif len(new_password) < 6:
                st.error("Le mot de passe doit contenir au moins 6 caractères.")
            elif (user_info.get("country_code") != reset_country_code or 
                  user_info.get("phone_number") != reset_phone_number):
                st.error("Le numéro de téléphone ou l'indicatif fourni ne correspond pas à ce nom d'utilisateur.")
            else:
                st.session_state.USER_DB[username_to_reset]["password_hash"] = make_hashes(new_password)
                st.success(f"Le mot de passe pour **{username_to_reset}** a été réinitialisé avec succès ! Vous pouvez maintenant vous connecter.")
                set_auth_mode("login")
                st.rerun()

    st.markdown("---")
    if st.button("Retour à la connexion", key="back_to_login_btn"):
        set_auth_mode("login")

def show_login_page():
    st.title("Connexion - Gestion des Achats")
    st.markdown("---")

    if st.session_state.auth_mode == "reset":
        show_password_reset()
        return

    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.auth_mode == "login":
            st.subheader("Se connecter")
            with st.form("login_form"):
                username = st.text_input("Nom d'utilisateur")
                password = st.text_input("Mot de passe", type="password")
                login_button = st.form_submit_button("Se connecter", type="primary")
            
            if login_button:
                hashed_password = make_hashes(password)
                if username in st.session_state.USER_DB and st.session_state.USER_DB[username]["password_hash"] == hashed_password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.is_admin = st.session_state.USER_DB[username]["is_admin"]
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Nom d'utilisateur ou mot de passe incorrect.")
            
            st.markdown("---")
            col_links = st.columns(2)
            with col_links[0]:
                st.button("Créer un compte", on_click=lambda: set_auth_mode("register"))
            with col_links[1]:
                st.button("Mot de passe oublié ?", on_click=lambda: set_auth_mode("reset")) 

        elif st.session_state.auth_mode == "register":
            st.subheader("Créer un compte client")
            with st.form("register_form"):
                new_username = st.text_input("Nom d'utilisateur souhaité")
                new_password = st.text_input("Mot de passe", type="password")
                
                st.markdown("---")
                st.markdown("**Contact (pour vérification d'abonnement et de sécurité) :**")
                col_code, col_phone = st.columns([1, 2])
                with col_code:
                    new_country_code = st.text_input("Indicatif Pays", value=DEFAULT_COUNTRY_CODE)
                with col_phone:
                    new_phone_number = st.text_input("Numéro de Téléphone (sans l'indicatif)")
                st.markdown("---")
                
                register_button = st.form_submit_button("S'inscrire", type="primary")

            if register_button:
                success, message = register_user(new_username, new_password, new_country_code, new_phone_number)
                if success:
                    st.success(message)
                    st.info(f"Veuillez vous connecter et effectuer le paiement des **5000 FCFA** pour activer votre abonnement auprès de l'administrateur.")
                    set_auth_mode("login")
                else:
                    st.error(message)

            st.markdown("---")
            st.button("Se connecter", on_click=lambda: set_auth_mode("login"))

    with col2:
        st.header("Note Importante pour l'Abonnement")
        st.markdown(f"""
        Tous les nouveaux comptes clients nécessitent une activation. 
        
        💸 **Coût :** 5000 FCFA / mois
        
        **Pour activer votre compte, veuillez payer sur le numéro :**
        
        # {NUMERO_PAIEMENT}
        
        **(Orange Money / Wave / Mixx)**
        
        L'administrateur validera votre abonnement après confirmation du paiement.
        """)

def show_payment_page():
    st.title("Abonnement Expiré ou Inactif")
    st.warning("Votre compte est inactif ou votre abonnement est expiré. Veuillez le renouveler pour accéder à l'application.")
    
    st.subheader("Instructions de paiement (5000 FCFA/mois)")
    st.markdown(f"""
    Pour renouveler votre abonnement, veuillez effectuer un paiement de **5000 FCFA** via Orange Money ou Wave sur le numéro indiqué.
    
    1.  **Montant :** **5000 FCFA**
    2.  **Numéro Orange Money/Wave :** `{NUMERO_PAIEMENT}`
    
    ---
    ### 📲 Étape Cruciale : Confirmation de Paiement
    
    Après avoir effectué le transfert manuellement, **vous devez** confirmer le paiement auprès de l'administrateur en cliquant sur le bouton ci-dessous. Cela ouvrira WhatsApp avec un message pré-rempli contenant votre nom d'utilisateur :
    """)

    whatsapp_link = f"https://wa.me/{NUMERO_PAIEMENT}?text=Bonjour,%20je%20souhaite%20activer%20mon%20abonnement%20de%205000%20FCFA.%20Mon%20nom%20d'utilisateur%20est%20*{st.session_state.username}*.%20J'ai%20effectué%20le%20paiement."
    
    st.link_button(
        f"📲 Payer sur le {NUMERO_PAIEMENT} (Orange Money/Wave)",
        url=whatsapp_link,
        type="primary",
        use_container_width=True
    )
    
    st.markdown(f"""
    
    L'administrateur activera manuellement votre compte pour **1 mois** après réception de la preuve de paiement.
    """)
    st.markdown("---")
    if st.button("Retour à la page de connexion"):
        logout() 

# --- Fonctions de Gestion (Admin/Client) ---

def show_admin_dashboard():
    st.title("Tableau de Bord Administrateur")
    st.button("Voir l'espace client", on_click=set_view_client)
    
    st.header("Gestion des Utilisateurs")
    user_data = []
    for user, info in st.session_state.USER_DB.items():
        full_phone = get_phone_number_from_db(user)
        user_data.append({
            "Nom d'utilisateur": user,
            "Téléphone": full_phone, 
            "Admin": "Oui" if info["is_admin"] else "Non",
            "Statut d'abonnement": "🟢 Actif" if info["is_active"] else "🔴 Inactif",
            "Date d'expiration": info["subscription_end_date"] if info["subscription_end_date"] else "N/A"
        })
    df_users = pd.DataFrame(user_data)
    st.dataframe(df_users, hide_index=True, use_container_width=True)
    
    st.subheader("Modifier l'abonnement d'un utilisateur")
    
    admin_users = [u for u in st.session_state.USER_DB.keys() if u != st.session_state.username and not st.session_state.USER_DB[u]["is_admin"]]
    if not admin_users:
         st.warning("Aucun autre utilisateur client à gérer.")
         # Continuer pour montrer la gestion des charges
    else:
        user_to_update = st.selectbox("Sélectionner un utilisateur", options=admin_users, key="admin_user_select")
        
        if user_to_update:
            current_info = st.session_state.USER_DB[user_to_update]
            
            st.write(f"**Utilisateur sélectionné :** `{user_to_update}`")
            st.write(f"**Numéro de Téléphone :** `{get_phone_number_from_db(user_to_update)}`")
            st.markdown(f"**Statut actuel :** {current_info['is_active'] and '🟢 Actif' or '🔴 Inactif'}")
            st.write(f"**Expire le :** {current_info['subscription_end_date'] if current_info['subscription_end_date'] else 'N/A'}")

            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Activer / Prolonger l'abonnement (1 Mois)", key="btn_activate"):
                    activate_subscription(user_to_update)
                    st.rerun()

            with col2:
                if current_info['is_active']:
                    if st.button("🔴 Suspendre l'abonnement", key="btn_suspend"):
                        suspend_subscription(user_to_update)
                        st.rerun()
                else:
                    st.info("L'abonnement est déjà suspendu ou expiré.")

    st.markdown("---")
    # Appel de la fonction de gestion des charges dans le dashboard Admin
    show_charge_management()

def show_charge_management():
    st.header("Gestion des Charges du Magasin")
    
    if not st.session_state.charges_db:
        st.info("Aucune charge enregistrée.")
        df_charges = pd.DataFrame()
    else:
        df_charges = pd.DataFrame(st.session_state.charges_db)
        df_charges['montant'] = pd.to_numeric(df_charges['montant'], errors='coerce').fillna(0)
        df_charges['date'] = pd.to_datetime(df_charges['date'], errors='coerce')
        df_charges = df_charges.sort_values(by="date", ascending=False).reset_index(drop=True)
        df_charges = df_charges.rename(columns={"nature": "Nature de la Charge", "montant": "Montant (FCFA)", "date": "Date"})
        # Nettoyage des lignes avec dates invalides si nécessaire
        df_charges = df_charges.dropna(subset=['Date']) 


    st.subheader("Historique des Charges")
    st.dataframe(df_charges.drop(columns=['id'], errors='ignore'), hide_index=True, use_container_width=True)
    
    st.subheader("Derniers Ajouts de Charges (5 plus récents)")
    st.dataframe(df_charges.drop(columns=['id'], errors='ignore').head(5), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("Ajouter une nouvelle charge")
    with st.form("add_charge_form", clear_on_submit=True):
        new_nature = st.text_input("Nature de la charge", key="add_charge_nature")
        new_amount = st.number_input("Montant (FCFA)", min_value=1.0, key="add_charge_amount")
        new_date = st.date_input("Date de la charge", value=datetime.now().date())
        add_charge_button = st.form_submit_button("Ajouter la charge")

        if add_charge_button:
            if new_nature and new_amount:
                new_charge = {
                    "id": st.session_state.next_charge_id,
                    "nature": new_nature,
                    "montant": new_amount,
                    "date": new_date.strftime("%Y-%m-%d")
                }
                st.session_state.charges_db.append(new_charge)
                st.session_state.next_charge_id += 1
                st.success("Charge ajoutée avec succès !")
                st.rerun()
            else:
                st.warning("Veuillez remplir la nature et le montant.")

    st.markdown("---")
    st.subheader("Modifier ou supprimer une charge")
    if not df_charges.empty:
        charge_options = {row['id']: f"{row['Nature de la Charge']} - {row['Montant (FCFA)'] + 0:,.0f} CFA ({row['Date'].strftime('%Y-%m-%d')})" for _, row in df_charges.iterrows()}
        charge_to_modify = st.selectbox("Sélectionner une charge", options=list(charge_options.keys()), format_func=lambda x: charge_options[x], key="modify_charge_select")

        if charge_to_modify:
            current_charge_index = next((i for i, c in enumerate(st.session_state.charges_db) if c['id'] == charge_to_modify), None)
            
            if current_charge_index is not None:
                current_charge = st.session_state.charges_db[current_charge_index]
                with st.form("modify_charge_form"):
                    updated_nature = st.text_input("Nouvelle nature de la charge", value=current_charge['nature'])
                    updated_amount = st.number_input("Nouveau montant (FCFA)", value=float(current_charge['montant']), min_value=1.0)
                    updated_date = st.date_input("Nouvelle date de la charge", value=datetime.strptime(current_charge['date'], "%Y-%m-%d").date())
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        modify_button = st.form_submit_button("Modifier la charge")
                    with col2:
                        delete_button = st.form_submit_button("Supprimer la charge")

                    if modify_button:
                        st.session_state.charges_db[current_charge_index]['nature'] = updated_nature
                        st.session_state.charges_db[current_charge_index]['montant'] = updated_amount
                        st.session_state.charges_db[current_charge_index]['date'] = updated_date.strftime("%Y-%m-%d")
                        st.success("Charge mise à jour avec succès !")
                        st.rerun()
                    
                    if delete_button:
                        del st.session_state.charges_db[current_charge_index]
                        st.success("Charge supprimée avec succès !")
                        st.rerun()

def show_user_settings_page():
    st.header("⚙️ Paramètres Utilisateur & Société")
    current_username = st.session_state.username
    current_settings = st.session_state.user_settings.get(current_username, {"display_name_format": "full", "company_logo_base64": None})
    current_user_db = st.session_state.USER_DB[current_username] 
    
    # --- 1. Modification du Numéro de Téléphone --- 
    st.subheader("Modifier votre Numéro de Téléphone") 
    with st.form("update_phone_form"): 
        col_code, col_phone = st.columns([1, 2]) 
        with col_code: 
            current_code = current_user_db.get("country_code", DEFAULT_COUNTRY_CODE) 
            new_country_code = st.text_input("Nouvel Indicatif Pays", value=current_code, key="settings_country_code") 
        with col_phone: 
            current_phone = current_user_db.get("phone_number", "") 
            new_phone_number = st.text_input("Nouveau Numéro de Téléphone (sans l'indicatif)", value=current_phone, key="settings_phone_number") 
        update_phone_button = st.form_submit_button("Mettre à jour le numéro", type="primary") 

        if update_phone_button: 
            if not new_country_code or not new_phone_number: 
                st.error("L'indicatif et le numéro de téléphone ne doivent pas être vides.") 
            elif not is_phone_unique(new_country_code, new_phone_number, exclude_user=current_username): 
                st.error("Ce numéro de téléphone est déjà utilisé par un autre compte.") 
            else: 
                current_user_db["country_code"] = new_country_code 
                current_user_db["phone_number"] = new_phone_number 
                st.success(f"Votre nouveau numéro, **{new_country_code}{new_phone_number}**, a été enregistré.") 
                st.rerun() 
    st.markdown("---") 
    
    # --- 2. Préférences d'affichage du Nom --- 
    st.subheader("Préférences d'affichage du Nom") 
    new_format = st.radio( 
        "Comment souhaitez-vous être accueilli(e) ?", 
        ('full', 'initials'), 
        format_func={'full': 'Nom complet (ex: Client1)', 'initials': 'Initiales (ex: C1)'}.get, 
        index=0 if current_settings["display_name_format"] == 'full' else 1, 
        horizontal=True 
    ) 
    if new_format != current_settings["display_name_format"]: 
        current_settings["display_name_format"] = new_format 
        st.success(f"Format d'affichage mis à jour : **{get_display_name(current_username, new_format)}**.") 
        st.rerun() 
    st.markdown("---") 
    
    # --- 3. Logo de la Société --- 
    st.subheader("Logo de la Société (Modifier ou Supprimer)") 
    col_upload, col_display = st.columns([1, 1]) 
    with col_upload: 
        uploaded_file = st.file_uploader("Charger un nouveau logo (PNG, JPG)", type=["png", "jpg", "jpeg"], accept_multiple_files=False) 
        if uploaded_file is not None: 
            bytes_data = uploaded_file.getvalue() 
            base64_encoded = base64.b64encode(bytes_data).decode('utf-8') 
            current_settings["company_logo_base64"] = base64_encoded 
            st.success("Logo chargé et enregistré ! (Actualisation)") 
            st.rerun() 
        if current_settings["company_logo_base64"] and st.button("🗑️ Supprimer le Logo", key="delete_logo_btn"): 
            current_settings["company_logo_base64"] = None 
            st.warning("Logo supprimé.") 
            st.rerun() 
        elif not current_settings["company_logo_base64"]: 
            st.info("Aucun logo enregistré. Utilisez le champ ci-dessus pour charger un nouveau logo.") 
            
    with col_display: 
        if current_settings["company_logo_base64"]: 
            logo_base64 = current_settings["company_logo_base64"] 
            logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 150px; max-width: 100%; border-radius: 5px; border: 1px solid #ccc; padding: 5px;">' 
            st.markdown("Votre Logo Actuel :") 
            st.markdown(logo_html, unsafe_allow_html=True) 
        else: 
            st.info("Aucun logo enregistré.") 
    st.markdown("---") 
    
    # --- 4. Partage de l'Application --- 
    st.subheader("Partage de l'Application") 
    st.info("Pour partager cette application, copiez et collez le lien ci-dessous.") 
    # NOTE: L'URL est simulée ici, remplacez-la par votre URL Streamlit Cloud 
    app_link = "https://votre-application-gestion-achats.streamlit.app" 
    st.text_input("Lien de partage de l'application", value=app_link, disabled=True) 
    st.link_button("Partager sur WhatsApp", url=f"https://wa.me/?text=Découvrez%20mon%20outil%20de%20gestion%20des%20achats%20:%20{app_link}", type="primary")

# --- Fonctions de Panier (ADAPTÉES POUR L'API) --- 
def add_to_cart(product_id, quantity, price): 
    """Ajoute un produit au panier temporaire (Client-side).""" 
    # Correction : toujours stocker nom, quantité, prix dans le panier
    df_products = load_products_data()
    product_row = df_products[df_products['ID Produit'] == product_id]
    if not product_row.empty:
        product_name = product_row.iloc[0]['Produit']
    else:
        product_name = str(product_id)
    if product_id in st.session_state.cart:
        st.session_state.cart[product_id]['quantity'] += quantity
        st.session_state.cart[product_id]['price'] = price
        st.session_state.cart[product_id]['name'] = product_name
    else:
        st.session_state.cart[product_id] = {'quantity': quantity, 'price': price, 'name': product_name}

def finalize_purchase(fournisseur_id, societe): 
    """Finalise le panier actuel en une commande via l'API.""" 
    if not st.session_state.cart: 
        st.error("Le panier est vide. Veuillez ajouter des produits avant de finaliser l'achat.") 
        return False 
        
    articles_list = [] 
    for product_id, item_data in st.session_state.cart.items(): 
        # Utiliser les clés que l'API attend (quantite, prix_achat) 
        # Assurez-vous que l'ID est un entier
        try:
             prod_id_int = int(product_id)
        except ValueError:
             st.error(f"Erreur de conversion de l'ID produit: {product_id}. Annulation.")
             return False

        articles_list.append({ 
            "produit_id": prod_id_int, 
            "quantite": item_data["quantity"], 
            "prix_achat": item_data["price"] 
        }) 
        
    # Structure de données attendue par POST /commandes/ 
    # Assurez-vous que l'ID fournisseur est un entier
    try:
        fournisseur_id_int = int(fournisseur_id)
    except ValueError:
        st.error(f"Erreur de conversion de l'ID fournisseur: {fournisseur_id}. Annulation.")
        return False
        
    purchase_data = { 
        "fournisseur_id": fournisseur_id_int, 
        "societe": societe, 
        "date_commande": datetime.now().strftime("%Y-%m-%d"), 
        "statut": "En attente", # Statut initial 
        "details": articles_list 
    } 
    st.info("Envoi de la commande à l'API...") 
    success, result = handle_api_request('POST', "/commandes/", data=purchase_data) 
    
    if success: 
        st.session_state.cart = {} # Vider le panier après succès 
        st.cache_data.clear() # Invalider le cache pour forcer la mise à jour des stocks et statistiques 
        st.success(f"Commande ID **{result['id']}** finalisée avec succès pour un total de **{result.get('cout_total', 0) + 0:,.0f} FCFA**!") 
        st.balloons() 
        return True 
    else: 
        st.error(f"Échec de la finalisation de la commande : {result}") 
        return False 

def purchase_formatter(cmd_id, details): 
    """ Formate l'affichage de la commande pour les sélecteurs. """ 
    date_achat_val = details.get("date_commande", "N/A")
    cout_total = details.get("cout_total", 0) # Utiliser 0 par défaut pour les commandes sans cout_total
    # Assurer le formatage de l'ID fournisseur pour les anciennes commandes
    # fournisseur_id = details.get("fournisseur_id", "N/A") # Non utilisé dans le format actuel
    return f"ID {cmd_id} - {date_achat_val} - Total: {cout_total:,.0f} FCFA"
    
# ----------------------------------------------------------------------
# --- FONCTION D'AFFICHAGE DES STATISTIQUES (INTEGRALE) ---
# ----------------------------------------------------------------------

def show_statistics_page():
    # Suppression du st.header("📈 Statistiques et Rapports") car il est placé avant l'appel
    
    commandes_list = load_commandes_data()
    df_fournisseurs = load_fournisseurs_data()
    charges_db = st.session_state.charges_db
    df_products = load_products_data() # Chargement des produits pour la jointure
    
    # Sélecteur de période pour l'évolution
    st.markdown('**Granularité des statistiques :**')
    period = st.radio('Afficher les statistiques par :', ['Jour', 'Semaine', 'Mois', 'Année'], horizontal=True, key='stat_period')
    period_map = {'Jour': 'D', 'Semaine': 'W', 'Mois': 'M', 'Année': 'Y'}
    resample_freq = period_map[period]

    # 1. Traitement des Commandes (Achats)
    if commandes_list:
        df_commandes = pd.DataFrame(commandes_list)
        # Calcul du coût total par commande si manquant
        if 'cout_total' not in df_commandes.columns:
            df_commandes['cout_total'] = df_commandes['details'].apply(
                lambda details: sum(item.get('quantite', 0) * item.get('prix_achat', 0) for item in details)
            )
        total_achats_cost = df_commandes['cout_total'].sum()
        df_commandes['date_commande'] = pd.to_datetime(df_commandes['date_commande'], errors='coerce')
        df_commandes = df_commandes.dropna(subset=['date_commande'])
    else:
        df_commandes = pd.DataFrame()
        total_achats_cost = 0

    # 2. Traitement des Charges (Dépenses Locales)
    if charges_db:
        df_charges = pd.DataFrame(charges_db)
        df_charges = df_charges.rename(columns={"nature": "Nature de la Charge", "montant": "Montant (FCFA)", "date": "Date"})
        df_charges['Montant (FCFA)'] = pd.to_numeric(df_charges['Montant (FCFA)'], errors='coerce').fillna(0)
        df_charges['Date'] = pd.to_datetime(df_charges['Date'], errors='coerce')
        df_charges = df_charges.dropna(subset=['Date'])
        total_charges = df_charges['Montant (FCFA)'].sum()
    else:
        df_charges = pd.DataFrame()
        total_charges = 0
        
    total_debourse = total_achats_cost + total_charges

    # --- Metrics ---
    st.subheader("Synthèse Financière Globale")
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Coût Total des Achats (Biens)", f"{total_achats_cost:,.0f} FCFA")
    col2.metric("Total des Charges Opérationnelles", f"{total_charges:,.0f} FCFA")
    col3.metric("Déboursé Total Cumulé", f"{total_debourse:,.0f} FCFA", delta=f"Base: {total_achats_cost:,.0f} (Achats)", delta_color="off")
    
    st.markdown("---")
    
    # --- Conteneur pour les graphiques d'achats ---
    with st.container(border=True):
        st.markdown("#### Analyse des Achats (Coût des Biens)")
        if not df_commandes.empty:
            
            col_chart_1, col_chart_2 = st.columns(2)
            
            # Chart 1: Achats par Fournisseur (Répartition en Tarte)
            df_achats_four = df_commandes.groupby('fournisseur_id')['cout_total'].sum().reset_index()
            if not df_fournisseurs.empty:
                 f_map = df_fournisseurs.set_index('ID Fournisseur')['Nom Fournisseur'].to_dict()
                 df_achats_four['Nom Fournisseur'] = df_achats_four['fournisseur_id'].astype(str).map(f_map).fillna("Inconnu")
            else:
                 df_achats_four['Nom Fournisseur'] = df_achats_four['fournisseur_id']

            fig_fournisseur = px.pie(
                df_achats_four, 
                values='cout_total', 
                names='Nom Fournisseur', 
                title='Répartition du Coût des Achats par Fournisseur',
                hole=0.3
            )
            with col_chart_1:
                st.plotly_chart(fig_fournisseur, use_container_width=True)
            
            # Chart 2: Évolution des Achats (Ligne)
            df_period = df_commandes.set_index('date_commande').resample(resample_freq)['cout_total'].sum().reset_index()
            df_period.columns = ['Période', 'Coût Total des Achats']
            fig_period_achats = px.line(
                df_period,
                x='Période',
                y='Coût Total des Achats',
                title=f"Évolution du Coût des Achats par {period}",
                markers=True
            )
            with col_chart_2:
                st.plotly_chart(fig_period_achats, use_container_width=True)
            
            # --- Analyse des Achats par Produit (Produits Commandés) ---
            st.markdown("---")
            st.markdown("#### Répartition Prix d'Achat vs Prix de Vente par Produit")
            if not df_products.empty:
                df_prix = df_products[['Produit', 'Prix Achat Unitaire (FCFA)', 'Prix Vente Unitaire (FCFA)']].copy()
                df_prix = df_prix.melt(id_vars=['Produit'], var_name='Type de Prix', value_name='Montant (FCFA)')
                fig_prix = px.bar(
                    df_prix,
                    x='Produit',
                    y='Montant (FCFA)',
                    color='Type de Prix',
                    barmode='group',
                    title="Comparatif Prix d'Achat vs Prix de Vente par Produit",
                    text_auto='.2s'
                )
                st.plotly_chart(fig_prix, use_container_width=True)
            else:
                st.info("Aucun produit disponible pour l'analyse des prix.")

            st.markdown("---")
            st.markdown("#### Top 10 des Produits les plus Coûteux en Achat")
            # Sélecteur de période pour le top 10 (même que global)
            command_details_list = []
            for index, row in df_commandes.iterrows():
                if isinstance(row.get('details'), list):
                     for detail in row['details']:
                         # Calcul du coût unitaire si nécessaire
                         detail['cout_article'] = detail.get('quantite', 0) * detail.get('prix_achat', 0)
                         # S'assurer que l'ID est une chaîne pour la jointure future
                         detail['produit_id'] = str(detail.get('produit_id', 'N/A')) 
                         detail['date_commande'] = row['date_commande']
                         command_details_list.append(detail)
            if command_details_list:
                df_details = pd.DataFrame(command_details_list)
                df_details['date_commande'] = pd.to_datetime(df_details['date_commande'], errors='coerce')
                # Grouper par période et produit
                df_details = df_details.dropna(subset=['date_commande'])
                df_details['periode'] = df_details['date_commande'].dt.to_period(resample_freq).dt.to_timestamp()
                df_cost_by_product = df_details.groupby(['periode', 'produit_id'])['cout_article'].sum().reset_index()
                df_cost_by_product.columns = ['Période', 'ID Produit', 'Coût Total Achat']
                # Joindre les noms de produits
                if not df_products.empty:
                    df_product_names = df_products[['ID Produit', 'Produit']]
                    df_final = pd.merge(df_cost_by_product, df_product_names, on='ID Produit', how='left')
                    df_final['Produit'] = df_final['Produit'].fillna('Produit Inconnu (ID: ' + df_final['ID Produit'] + ')')
                else:
                     df_final = df_cost_by_product
                     df_final['Produit'] = df_final['ID Produit'].apply(lambda x: f"ID {x}")
                # Top 10 sur la période sélectionnée (somme sur la période la plus récente)
                if not df_final.empty:
                    last_period = df_final['Période'].max()
                    df_top_10 = df_final[df_final['Période'] == last_period].sort_values(by='Coût Total Achat', ascending=False).head(10)
                    fig_product_cost = px.bar(
                        df_top_10,
                        x='Produit',
                        y='Coût Total Achat',
                        title=f'Top 10 des Produits les plus Coûteux en Achat ({period} : {last_period.date()})',
                        color='Produit',
                        text_auto='.2s'
                    )
                    st.plotly_chart(fig_product_cost, use_container_width=True)
                else:
                    st.info("Aucun détail de produit dans les commandes enregistrées pour cette période.")
            else:
                st.info("Aucun détail de produit dans les commandes enregistrées.")
        else:
            st.info("Aucune donnée d'achat disponible pour l'analyse statistique.")
        
    st.markdown("---")
    
    # --- Conteneur pour les graphiques de charges ---
    with st.container(border=True):
        st.markdown("#### Analyse des Charges Opérationnelles (Dépenses Locales)")
        if not df_charges.empty:
            
            col_chart_3, col_chart_4 = st.columns(2)
            
            # Chart 3: Répartition des Charges par Nature (Barres)
            df_charges_nature = df_charges.groupby('Nature de la Charge')['Montant (FCFA)'].sum().reset_index()
            
            fig_charges_nature = px.bar(
                df_charges_nature, 
                x='Nature de la Charge', 
                y='Montant (FCFA)', 
                title='Répartition des Charges par Nature',
                color='Nature de la Charge',
                text_auto=True 
            )
            with col_chart_3:
                st.plotly_chart(fig_charges_nature, use_container_width=True)
            
            # Chart 4: Évolution des Charges (Barres)
            df_charges_period = df_charges.set_index('Date').resample(resample_freq)['Montant (FCFA)'].sum().reset_index()
            df_charges_period.columns = ['Période', 'Total des Charges']
            fig_period_charges = px.bar(
                df_charges_period,
                x='Période',
                y='Total des Charges',
                title=f'Évolution du Total des Charges par {period}',
                text_auto=True
            )
            with col_chart_4:
                st.plotly_chart(fig_period_charges, use_container_width=True)
        
        else:
            st.info("Aucune charge enregistrée pour l'analyse statistique des dépenses.")

# ----------------------------------------------------------------------
# --- Page Client ---
# ----------------------------------------------------------------------

def show_client_page():
    # Afficher le nom d'utilisateur et un bouton pour l'administration si admin
    current_user_name = st.session_state.username
    current_settings = st.session_state.user_settings.get(current_user_name, {"display_name_format": "full", "company_logo_base64": None})
    st.sidebar.title(f"Bienvenue, {get_display_name(current_user_name, current_settings['display_name_format'])}")
    if st.session_state.is_admin:
        st.sidebar.button("Accès au Tableau de Bord Admin", on_click=set_view_admin, type="primary")

    # Onglets de navigation (5 onglets)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🛒 Passer Commande", 
        "📦 Produits", 
        "👤 Fournisseurs", 
        "📈 Commandes Historique & Stats", 
        "⚙️ Paramètres"
    ])

    # ----------------------------------------------------
    # TAB 1 : Passer Commande
    # ----------------------------------------------------
    with tab1:
        st.header("Passer une Nouvelle Commande")
        df_products = load_products_data()
        df_fournisseurs = load_fournisseurs_data()
        
        if df_products.empty or df_fournisseurs.empty:
            st.warning("Impossible de procéder. Les données des Produits ou Fournisseurs n'ont pas pu être chargées depuis l'API ou sont vides.")
            
            selected_fournisseur_id = "N/A"
            selected_fournisseur_name = "Fournisseur Inconnu"
            
            if not df_fournisseurs.empty:
                fournisseur_options = {
                    id_: name for id_, name in zip(df_fournisseurs['ID Fournisseur'], df_fournisseurs['Nom Fournisseur'])
                }
                selected_fournisseur_name = st.selectbox(
                    "Sélectionnez le fournisseur", 
                    options=list(fournisseur_options.values()),
                    key="new_order_fournisseur_name"
                )
                selected_fournisseur_id = next(id_ for id_, name in fournisseur_options.items() if name == selected_fournisseur_name)
            else:
                 st.text_input("Sélectionnez le fournisseur", value="Aucun fournisseur chargé", disabled=True)
            
            st.markdown("---")
            st.warning("Impossible d'ajouter des produits au panier car les données ne sont pas disponibles.")

        # L'exécution continue ici si les DataFrames ne sont pas vides
        else:
             # Sélection du Fournisseur
            fournisseur_options = {
                id_: name for id_, name in zip(df_fournisseurs['ID Fournisseur'], df_fournisseurs['Nom Fournisseur'])
            }
            selected_fournisseur_name = st.selectbox(
                "Sélectionnez le fournisseur", 
                options=list(fournisseur_options.values()),
                key="new_order_fournisseur_name"
            )
            selected_fournisseur_id = next(id_ for id_, name in fournisseur_options.items() if name == selected_fournisseur_name)
            
            st.markdown("---")

            # Sélection du produit et ajout au panier
            st.subheader("Ajouter un Produit au Panier")
            col_prod, col_qty, col_price, col_add = st.columns([3, 1.5, 2, 1])

            product_options = df_products['Produit'].tolist()
            product_name = None
            
            with col_prod:
                if not product_options:
                    st.warning("Aucun produit disponible. Veuillez ajouter des produits via l'onglet 'Produits'.")
                else:
                    # Utilisation de st.selectbox pour le support de la recherche (taper au clavier)
                    product_name = st.selectbox(
                        "Produit (Tapez pour chercher dans la liste)", 
                        options=product_options, 
                        key="cart_product_name"
                    )
            
            # --- DÉBUT DE LA LOGIQUE DE SÉLECTION SÉCURISÉE ---
            suggested_price = 1.0 # Prix par défaut sécurisé
            is_ready_to_add = False
            
            if product_name and product_name != 'Inconnu':
                # Filtrage sécurisé
                selected_product_df = df_products[df_products['Produit'] == product_name]
                
                if not selected_product_df.empty:
                    selected_product = selected_product_df.iloc[0]
                    # L'accès est sécurisé grâce à la correction dans load_products_data
                    suggested_price = selected_product['Prix Achat Unitaire (FCFA)']
                    is_ready_to_add = True

            # --- Bloc d'Input Conditionnel ---
            if is_ready_to_add:
                with col_price:
                     # CORRECTION: Assurer que la valeur est >= min_value (1.0)
                    safe_suggested_price = max(1.0, float(suggested_price)) 
                    
                    price_input = st.number_input(
                        f"Prix d'Achat Unitaire ({safe_suggested_price:,.0f} FCFA suggéré)",
                        min_value=1.0, 
                        value=safe_suggested_price, # Utilisation de la valeur sécurisée
                        key="cart_price_input"
                    )

                with col_qty:
                    quantity_input = st.number_input(
                        "Quantité", 
                        min_value=1, 
                        value=1, 
                        step=1, 
                        key="cart_quantity_input"
                    )

                with col_add:
                    st.markdown("<br>", unsafe_allow_html=True) # Espacement pour alignement
                    if st.button("➕ Ajouter", key="add_to_cart_btn", use_container_width=True):
                         # L'accès à selected_product['ID Produit'] est sécurisé ici
                        product_id = selected_product['ID Produit']
                        add_to_cart(product_id, quantity_input, price_input)
                        st.success(f"{quantity_input} x {product_name} ajouté au panier!")
                        st.rerun()

            else:
                # Afficher les champs désactivés/vides si pas prêt (pour éviter le crash)
                with col_price:
                    st.text_input("Prix d'Achat Unitaire", value="N/A", disabled=True)
                with col_qty:
                    st.text_input("Quantité", value="N/A", disabled=True)
                with col_add:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.button("➕ Ajouter", key="add_to_cart_btn_disabled", use_container_width=True, disabled=True)
            # --- FIN DE LA LOGIQUE DE SÉLECTION SÉCURISÉE ---

        st.markdown("---")

        # Affichage et Finalisation du Panier
        st.subheader("Panier Actuel")
        if st.session_state.cart:
            cart_data = []
            total_cost = 0
            for product_id, item in st.session_state.cart.items():
                cost = item['quantity'] * item['price']
                total_cost += cost
                cart_data.append({
                    "ID Produit": product_id,
                    "Produit": item.get('name', f"ID Inconnu: {product_id}"),
                    "Quantité": item['quantity'],
                    "Prix U. Achat": f"{item['price']:,.0f} FCFA",
                    "Coût Total": f"{cost:,.0f} FCFA"
                })
            df_cart = pd.DataFrame(cart_data)
            st.dataframe(df_cart.drop(columns=['ID Produit']), hide_index=True, use_container_width=True)
            st.metric("Coût Total de la Commande", f"{total_cost:,.0f} FCFA")
            col_final, col_clear = st.columns([3, 1])
            with col_final:
                societe_name = st.text_input("Nom de l'entité/société passante la commande", value="Ma Société", key="societe_name_final")
                if st.button("✅ Finaliser la Commande", type="primary", use_container_width=True):
                    finalize_purchase(selected_fournisseur_id, societe_name) 
                    st.rerun()
            with col_clear:
                if st.button("❌ Vider le Panier", key="clear_cart_btn", use_container_width=True):
                    st.session_state.cart = {}
                    st.success("Panier vidé.")
                    st.rerun()
        else:
            st.info("Votre panier est vide. Veuillez ajouter des produits.")

        # --- SECTION HISTORIQUE ---
        commandes_list = load_commandes_data()
        if commandes_list:
            st.markdown("---")
            st.header("📜 Modifier ou Supprimer une Commande")
            commandes_valides = [c for c in commandes_list if isinstance(c.get('id', None), int)]
            commandes_options = {str(c['id']): purchase_formatter(c['id'], c) for c in commandes_valides}
            if not commandes_options:
                st.info("Aucune commande valide à modifier côté API.")
            else:
                command_to_modify_id = st.selectbox(
                    "Sélectionner une commande", 
                    options=list(commandes_options.keys()), 
                    format_func=lambda x: commandes_options[x], 
                    key="modify_command_select_tab1"
                )
                if command_to_modify_id:
                    current_command = next((c for c in commandes_valides if str(c['id']) == str(command_to_modify_id)), None)
                    if not current_command:
                        st.error("Commande introuvable ou supprimée côté API.")
                    else:
                        st.markdown("**Détails de la commande :**")
                        details = current_command.get('details', [])
                        if not details:
                            st.info("Aucun article dans cette commande.")
                        else:
                            df_details = pd.DataFrame(details)
                            if not df_details.empty:
                                if 'nom' not in df_details.columns:
                                    df_products = load_products_data()
                                    prod_id_to_name = df_products.set_index('ID Produit')['Produit'].to_dict() if not df_products.empty else {}
                                    df_details['nom'] = df_details['produit_id'].map(lambda x: prod_id_to_name.get(x, f"ID {x}"))
                                st.dataframe(df_details[['produit_id', 'nom', 'quantite', 'prix_achat']], hide_index=True, use_container_width=True)
                        # Modification du statut et suppression (inchangé)
                        current_status = current_command['statut']
                        new_status = st.selectbox(
                            "Modifier le Statut",
                            options=["En attente", "Confirmée", "Reçue", "Annulée"],
                            index=["En attente", "Confirmée", "Reçue", "Annulée"].index(current_status),
                            key="update_status_select_tab1"
                        )
                        col_mod, col_del = st.columns(2)
                        with col_mod:
                            with st.form(f"form_modif_statut_{command_to_modify_id}", clear_on_submit=True):
                                submit_modif = st.form_submit_button("Modifier le Statut")
                                if submit_modif:
                                    update_data = {"statut": new_status}
                                    try:
                                        command_id_int = int(command_to_modify_id)
                                    except Exception:
                                        command_id_int = command_to_modify_id
                                    success, result = handle_api_request('PUT', f"/commandes/{command_id_int}", data=update_data)
                                    if success:
                                        st.success(f"Statut de la commande **{command_to_modify_id}** mis à jour à **{new_status}**.")
                                        st.rerun()
                                    else:
                                        st.error(f"Échec de la modification : {result}")
                        with col_del:
                            with st.form(f"form_del_commande_{command_to_modify_id}", clear_on_submit=True):
                                submit_del = st.form_submit_button("Supprimer la Commande")
                                if submit_del:
                                    st.info(f"Suppression de la commande ID : {command_to_modify_id}")
                                    try:
                                        command_id_str = str(int(command_to_modify_id))
                                    except ValueError:
                                        command_id_str = str(command_to_modify_id)
                                    success, result = handle_api_request('DELETE', f"/commandes/{command_id_str}")
                                    if success:
                                        st.success(f"La commande **{command_to_modify_id}** a été supprimée.")
                                        st.rerun()
                                    else:
                                        st.error(f"Échec de la suppression : {result}")
        else:
            pass  # Ne rien afficher si aucune commande

    # ----------------------------------------------------
    # TAB 2 : Gestion des Produits
    # ----------------------------------------------------
    with tab2:
        st.header("Gestion et Stock des Produits")
        df_products = load_products_data()
        # On renomme pour l'affichage : 'Nom Fournisseur' devient 'Nom du Fournisseur'
        df_fournisseurs = load_fournisseurs_data().rename(columns={'Nom Fournisseur': 'Nom du Fournisseur'})
        
        # Jointure pour afficher le nom du fournisseur
        if not df_products.empty and not df_fournisseurs.empty and 'ID Fournisseur' in df_products.columns:
            # Cette jointure est maintenant sûre car df_fournisseurs n'a plus l'index ambigu
            df_merged = pd.merge(
                df_products, 
                df_fournisseurs[['ID Fournisseur', 'Nom du Fournisseur']], 
                on='ID Fournisseur', 
                how='left'
            )
            # Retirer la colonne ID Fournisseur et la remplacer par le nom
            df_display = df_merged.drop(columns=['ID Fournisseur'])
            # Réordonner les colonnes pour un affichage plus lisible
            cols = [
                'ID Produit', 'Produit', 'Stock Actuel', 
                'Prix Achat Unitaire (FCFA)', 'Prix Vente Unitaire (FCFA)', 
                'Nom du Fournisseur'
            ]
            # S'assurer que seules les colonnes existantes sont utilisées pour le réordonnancement
            cols_to_use = [col for col in cols if col in df_display.columns]
            df_display = df_display[cols_to_use]
        elif not df_products.empty:
             # Si les fournisseurs ne sont pas chargés, afficher au moins les produits
             df_display = df_products
        else:
            df_display = pd.DataFrame()

        if not df_display.empty:
            st.subheader("Liste des Produits")
            for idx, row in df_display.iterrows():
                cols = st.columns([3,2,2,2,2,2,1])
                cols[0].markdown(f"**{row['Produit']}**")
                cols[1].write(row.get('Stock Actuel', ''))
                cols[2].write(row.get('Prix Achat Unitaire (FCFA)', ''))
                cols[3].write(row.get('Prix Vente Unitaire (FCFA)', ''))
                cols[4].write(row.get('Nom du Fournisseur', ''))
                if cols[5].button("Modifier", key=f"edit_prod_{row['ID Produit']}"):
                    st.session_state.edit_product_id = row['ID Produit']
            st.markdown("---")
            st.subheader("Ajouter ou Modifier un Produit")
            edit_id = st.session_state.get('edit_product_id', None)
            if edit_id:
                prod_row = df_display[df_display['ID Produit'] == edit_id].iloc[0]
                default_name = prod_row['Produit']
                default_ref = prod_row.get('Référence', '') if 'Référence' in prod_row else ''
                default_stock = prod_row.get('Stock Actuel', 0)
                default_prix_unitaire = prod_row.get('Prix Achat Unitaire (FCFA)', 1.0)
                default_fourn = prod_row.get('Nom du Fournisseur', '')
            else:
                default_name = ''
                default_ref = ''
                default_stock = 0
                default_prix_unitaire = 1.0
                default_fourn = ''
            with st.form("add_or_edit_product_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    product_name = st.text_input("Nom du Produit", value=default_name)
                    reference = st.text_input("Référence Produit (obligatoire)", value=default_ref)
                    stock_actuel = st.number_input("Stock Initial", min_value=0, value=int(default_stock))
                with col2:
                    safe_prix_unitaire = max(1.0, float(default_prix_unitaire))
                    prix_unitaire = st.number_input("Prix Unitaire (obligatoire pour API)", min_value=1.0, value=safe_prix_unitaire)
                    f_options = {name: id_ for id_, name in zip(df_fournisseurs['ID Fournisseur'], df_fournisseurs['Nom du Fournisseur'])}
                    if not f_options:
                        st.error("Aucun fournisseur trouvé. Veuillez ajouter un fournisseur d'abord.")
                        fournisseur_id = None
                    else:
                        fournisseur_name = st.selectbox(
                            "Fournisseur Principal", 
                            options=list(f_options.keys()), 
                            key="edit_product_fournisseur",
                            index=list(f_options.keys()).index(default_fourn) if default_fourn in f_options else 0
                        )
                        fournisseur_id = f_options[fournisseur_name]
                submit_label = "Modifier le Produit" if edit_id else "Ajouter le Produit"
                submit_btn = st.form_submit_button(submit_label, type="primary")
                if submit_btn and fournisseur_id is not None:
                    if not product_name or not reference:
                        st.error("Le nom et la référence du produit sont obligatoires.")
                    else:
                        product_data = {
                            "nom": product_name,
                            "reference": reference,
                            "prix_unitaire": prix_unitaire,
                            "stock_actuel": stock_actuel,
                            "fournisseur_id": int(fournisseur_id)
                        }
                        if edit_id:
                            # Vérifier que l'ID existe vraiment dans la base
                            df_products_check = load_products_data()
                            if int(edit_id) not in df_products_check['ID Produit'].astype(int).values:
                                st.error("Impossible de modifier : ce produit n'existe plus dans la base.")
                                st.session_state.edit_product_id = None
                            else:
                                endpoint = f"/produits/{int(edit_id)}"
                                success, result = handle_api_request('PUT', endpoint, product_data)
                                if success:
                                    st.success(f"Produit '{product_name}' modifié avec succès !")
                                    st.session_state.edit_product_id = None
                                    st.rerun()
                                else:
                                    st.error(f"Échec de la modification : {result}")
                        else:
                            success, result = handle_api_request('POST', "/produits/", data=product_data)
                            if success:
                                st.success(f"Produit '{product_name}' ajouté avec succès (ID: {result['id']})!")
                                st.rerun()
                            else:
                                st.error(f"Échec de l'ajout du produit : {result}")
        else:
            st.info("Aucun produit disponible (API inaccessible ou base vide).")
            
    # ----------------------------------------------------
    # TAB 3 : Gestion des Fournisseurs
    # ----------------------------------------------------
    with tab3:
        st.header("Gestion des Fournisseurs")
        df_fournisseurs = load_fournisseurs_data()
        
        if not df_fournisseurs.empty:
            df_display_f = df_fournisseurs.rename(columns={'Nom Fournisseur': 'Nom du Fournisseur'}).drop(columns=['ID Fournisseur']) # Cacher l'ID pour l'affichage
            st.dataframe(df_display_f, hide_index=True, use_container_width=True)
            generate_download_buttons(df_display_f, "Rapport_Fournisseurs")
        else:
             st.info("Aucun fournisseur disponible (API inaccessible ou base vide).")

        st.markdown("---")
        st.subheader("Ajouter un Nouveau Fournisseur")
        with st.form("add_fournisseur_form", clear_on_submit=True):
            new_f_nom = st.text_input("Nom du Fournisseur")
            new_f_contact = st.text_input("Contact (Téléphone/Email)")
            new_f_adresse = st.text_area("Adresse (Optionnel)")
            
            add_button = st.form_submit_button("Ajouter le Fournisseur", type="primary")

            if add_button:
                if not new_f_nom:
                    st.error("Le nom du fournisseur est obligatoire.")
                else:
                    fournisseur_data = {
                        "nom": new_f_nom,
                        "contact": new_f_contact,
                        "adresse": new_f_adresse,
                    }
                    success, result = handle_api_request('POST', "/fournisseurs/", data=fournisseur_data)
                    if success:
                        st.success(f"Fournisseur '{new_f_nom}' ajouté avec succès (ID: {result['id']})!")
                        st.rerun()
                    else:
                        st.error(f"Échec de l'ajout du fournisseur : {result}")

    # ----------------------------------------------------
    # TAB 4 : Historique des Commandes (API) & Statistiques
    # ----------------------------------------------------
    with tab4:
        # --- NOUVELLE SECTION STATISTIQUES (AFFICHAGE IMMÉDIAT) ---
        st.title("📈 Synthèse et Statistiques Globales des Achats")
        st.markdown("---")
        # Les statistiques et diagrammes sont générés ici à chaque fois que l'onglet est sélectionné
        show_statistics_page()
        st.markdown("---")
        
        # --- SECTION HISTORIQUE ---
        st.header("📜 Historique Détaillé des Commandes d'Achat")
        commandes_list = load_commandes_data()
        
        if commandes_list:
            # Préparer les données pour l'affichage (table)
            df_commandes = pd.DataFrame(commandes_list)
            
            # Calculer le coût total si ce n'est pas déjà dans l'API response
            if 'cout_total' not in df_commandes.columns:
                df_commandes['cout_total'] = df_commandes['details'].apply(
                    lambda details: sum(item.get('quantite', 0) * item.get('prix_achat', 0) for item in details)
                )

            # Remplacer fournisseur_id par le nom si les données fournisseurs sont là
            df_fournisseurs = load_fournisseurs_data()
            if not df_fournisseurs.empty:
                # Créer le mapping
                f_map = df_fournisseurs.set_index('ID Fournisseur')['Nom Fournisseur'].to_dict()
                # Appliquer le mapping 
                df_commandes['Nom Fournisseur'] = df_commandes['fournisseur_id'].astype(str).map(f_map).fillna("Inconnu")
            else:
                df_commandes['Nom Fournisseur'] = df_commandes['fournisseur_id']
                
            df_display_cmd = df_commandes.rename(columns={
                'id': 'ID Commande',
                'date_commande': 'Date',
                'societe': 'Société',
                'statut': 'Statut',
                'cout_total': 'Total (FCFA)',
            })
            
            cols_to_show = ['ID Commande', 'Date', 'Nom Fournisseur', 'Société', 'Statut', 'Total (FCFA)']
            df_display_cmd = df_display_cmd[cols_to_show]
            
            # Affichage de l'historique
            st.dataframe(df_display_cmd, hide_index=True, use_container_width=True)
            generate_download_buttons(df_display_cmd, "Rapport_Commandes")
            
            # Modification/Suppression
            st.markdown("---")
            st.subheader("Modifier ou Supprimer une Commande")
            # S'assurer que l'ID utilisé est bien celui de la commande (champ 'id')
            # Filtrer uniquement les commandes ayant un ID entier valide (présentes côté API)
            commandes_valides = [c for c in commandes_list if isinstance(c.get('id', None), int)]
            commandes_options = {str(c['id']): purchase_formatter(c['id'], c) for c in commandes_valides}
            if not commandes_options:
                st.info("Aucune commande valide à modifier côté API.")
                return
            command_to_modify_id = st.selectbox(
                "Sélectionner une commande", 
                options=list(commandes_options.keys()), 
                format_func=lambda x: commandes_options[x], 
                key="modify_command_select"
            )

            if command_to_modify_id:
                with st.form("modify_delete_command_form"):
                    # Récupérer la commande réelle par son ID (champ 'id')
                    current_command = next((c for c in commandes_valides if str(c['id']) == str(command_to_modify_id)), None)
                    if not current_command:
                        st.error("Commande introuvable ou supprimée côté API.")
                        return
                    current_status = current_command['statut']
                    
                    new_status = st.selectbox(
                        "Modifier le Statut",
                        options=["En attente", "Confirmée", "Reçue", "Annulée"],
                        index=["En attente", "Confirmée", "Reçue", "Annulée"].index(current_status),
                        key="update_status_select"
                    )
                    
                    col_mod, col_del = st.columns(2)
                    with col_mod:
                        modify_button = st.form_submit_button("Modifier le Statut", type="primary")
                    with col_del:
                        delete_button = st.form_submit_button("Supprimer la Commande", type="secondary")

                    if modify_button:
                        update_data = {"statut": new_status}
                        # S'assurer que l'ID est bien un entier pour l'API
                        try:
                            command_id_int = int(command_to_modify_id)
                        except Exception:
                            command_id_int = command_to_modify_id
                        success, result = handle_api_request('PUT', f"/commandes/{command_id_int}", data=update_data)
                        if success:
                            st.success(f"Statut de la commande **{command_to_modify_id}** mis à jour à **{new_status}**.")
                            st.rerun()
                        else:
                            st.error(f"Échec de la modification : {result}")
                            
                    if delete_button:
                        st.info(f"Suppression de la commande ID : {command_to_modify_id}")
                        
                        # CORRECTION ROBUSTE du 404: Assurer que l'ID est un entier propre avant la conversion en string
                        try:
                            # Tenter de convertir en int, puis en str pour être sûr de la propreté du format numérique
                            command_id_str = str(int(command_to_modify_id)) 
                        except ValueError:
                            # En cas d'échec (ID non numérique), utiliser le string tel quel
                            command_id_str = str(command_to_modify_id)
                        
                        success, result = handle_api_request('DELETE', f"/commandes/{command_id_str}")
                        
                        if success:
                            st.success(f"La commande **{command_to_modify_id}** a été supprimée.")
                            st.rerun()
                        else:
                            st.error(f"Échec de la suppression : {result}")
            else:
                st.info("Aucune commande à modifier ou supprimer.")
        else:
            st.info("Vous n'avez pas encore effectué de commandes (via l'API).")
            
    # ----------------------------------------------------
    # TAB 5 : Paramètres Utilisateur (Ancien TAB 6)
    # ----------------------------------------------------
    with tab5:
        show_user_settings_page()


# --- Point d'entrée de l'application ---
def main():
    if st.session_state.logged_in:
        # Vérification de l'abonnement
        if not check_subscription_status() and not st.session_state.is_admin:
            show_payment_page()
        # Tableau de bord Admin
        elif st.session_state.is_admin and st.session_state.current_view == "admin":
            show_admin_dashboard() # show_admin_dashboard() appelle show_charge_management()
        # Espace Client
        else:
            show_client_page()
            
        # Bouton de déconnexion toujours dans la barre latérale si connecté
        st.sidebar.button("Déconnexion", on_click=logout)
    else:
        # Page de connexion / Inscription
        show_login_page()

if __name__ == '__main__':
    main()