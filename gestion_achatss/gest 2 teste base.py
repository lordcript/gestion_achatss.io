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
                error_detail = response.json().get('detail', response.text)
                if isinstance(error_detail, list):
                    error_message = "Erreur de validation (422) : " + "; ".join([f"{d.get('loc', ['N/A'])[-1]} -> {d.get('msg')}" for d in error_detail])
                else:
                    error_message = f"Erreur API ({response.status_code}): {error_detail}"
            except Exception:
                error_message = f"Erreur API ({response.status_code}): {response.text}"
        
        return False, error_message

# ----------------------------------------------------------------------
# --- FONCTIONS DE CHARGEMENT DE DONNÉES (API) ---
# ----------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_products_data():
    """Charge les produits depuis l'API et retourne un DataFrame vide ou rempli."""
    data = get_data_from_api("/produits/")
    if data is None or not isinstance(data, list):
        if st.session_state.logged_in:
             pass 
        return pd.DataFrame()

    df = pd.DataFrame(data)
    
    if not df.empty:
        rename_map = {
            'id': 'ID Produit', 'nom': 'Produit', 'stock': 'Stock Actuel', 
            'prix_achat': 'Prix Achat Unitaire (FCFA)', 'prix_vente': 'Prix Vente Unitaire (FCFA)', 
            'fournisseur_id': 'ID Fournisseur'
        }
        valid_rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=valid_rename_map)

        required_cols = ['ID Produit', 'Produit', 'Stock Actuel', 'Prix Achat Unitaire (FCFA)', 'Prix Vente Unitaire (FCFA)', 'ID Fournisseur']
        for col in required_cols:
            if col not in df.columns:
                 df[col] = 0.0 if 'Prix' in col or 'Stock' in col else ('' if 'ID' in col else 'Inconnu')

        if 'ID Produit' in df.columns: df['ID Produit'] = df['ID Produit'].astype(str) 
        if 'ID Fournisseur' in df.columns: df['ID Fournisseur'] = df['ID Fournisseur'].astype(str) 
            
        for col_name in ['Prix Achat Unitaire (FCFA)', 'Prix Vente Unitaire (FCFA)', 'Stock Actuel']:
             if col_name in df.columns:
                 df[col_name] = pd.to_numeric(df[col_name], errors='coerce').fillna(0)
                 if 'Stock' in col_name: df[col_name] = df[col_name].astype(int) 
            
    return df if not df.empty else pd.DataFrame() 

@st.cache_data(ttl=60)
def load_fournisseurs_data():
    """Charge les fournisseurs depuis l'API et retourne un DataFrame vide ou rempli."""
    data = get_data_from_api("/fournisseurs/")
    if data is None or not isinstance(data, list):
        if st.session_state.logged_in:
             pass
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if not df.empty:
         df = df.rename(columns={'nom': 'Nom Fournisseur', 'contact': 'Contact', 'adresse': 'Adresse', 'id': 'ID Fournisseur'})
         if 'ID Fournisseur' in df.columns:
             df['ID Fournisseur'] = df['ID Fournisseur'].astype(str) 
             
    return df if not df.empty else pd.DataFrame()

@st.cache_data(ttl=60)
def load_commandes_data():
    """Charge les commandes depuis l'API et retourne une liste vide ou remplie."""
    data = get_data_from_api("/commandes/")
    if data is None or not isinstance(data, list):
        if st.session_state.logged_in:
             pass
        return []
    return data

# FONCTION CLÉ POUR L'ADMIN : CHARGEMENT DES UTILISATEURS VIA API
@st.cache_data(ttl=30)
def load_users_data():
    """Charge tous les utilisateurs depuis l'API pour l'administrateur."""
    data = get_data_from_api("/users/") # Nécessite la route /users/ dans l'API
    if data is None or not isinstance(data, list):
         return []
    
    # Exclure l'administrateur courant et les autres administrateurs de la liste de gestion
    current_admin_user = st.session_state.username
    return [u for u in data if u.get('username') != current_admin_user and u.get('is_admin', False) == False]

# ----------------------------------------------------------------------
# --- FONCTIONS UTILITAIRES DE GESTION DE SESSION (MISES À JOUR) ---
# ----------------------------------------------------------------------

# --- Fonctions de hachage du mot de passe ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- Fonctions utilitaires pour le téléchargement (conservées) ---
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
    
    amount_col = 'Montant' if 'Montant' in df.columns else 'Montant Total'
    
    if amount_col in df.columns or 'Montant Total' in df.columns:
        amount_col_final = amount_col if amount_col in df.columns else 'Montant Total'
        try:
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

# --- Fonctions de gestion des charges (reste local pour l'instant) ---
def add_charge(nature, montant, date):
    st.session_state.charges_db.append({
        "id": st.session_state.next_charge_id,
        "nature": nature,
        "montant": montant,
        "date": date
    })
    st.session_state.next_charge_id += 1

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
    st.session_state.user_data = {} # Vider les données utilisateur de l'API
    st.session_state.cart = {}
    st.cache_data.clear() 
    st.rerun()

def get_display_name(username):
    """Retourne le nom d'affichage."""
    return username.capitalize()

# FONCTION D'INSCRIPTION MISE À JOUR (Utilise l'API /register)
def register_user(username, password, country_code, phone_number):
    if not username or not password or not country_code or not phone_number:
        return False, "Veuillez remplir tous les champs obligatoires."

    registration_payload = {
        "username": username,
        "password": password, 
        "country_code": country_code,
        "phone_number": phone_number,
        "is_admin": False, 
        "is_active": False 
    }

    # Appel API pour l'inscription (POST /register)
    success, result = handle_api_request("POST", "/register", data=registration_payload)
    
    if success:
        return True, f"Compte **{username}** créé avec succès ! Veuillez payer 5000 FCFA sur le numéro {NUMERO_PAIEMENT} pour l'activation."
    else:
        return False, f"Échec de l'inscription : {result}"

# FONCTION DE VÉRIFICATION D'ABONNEMENT MISE À JOUR (Utilise les données de l'API)
def check_subscription_status():
    if st.session_state.is_admin:
        return True
    
    user_info = st.session_state.user_data
    if not user_info:
        return False 

    if user_info.get("is_active", False):
        sub_end_date_str = user_info.get("subscription_end_date")
        
        if sub_end_date_str:
            try:
                sub_end_date = datetime.strptime(sub_end_date_str, "%Y-%m-%d").date()
                if sub_end_date < datetime.now().date():
                    # L'abonnement a expiré selon l'API. Déconnexion forcée.
                    st.session_state.logged_in = False
                    st.session_state.auth_mode = "login" 
                    st.error("Votre abonnement a expiré. Veuillez vous reconnecter.")
                    return False
            except ValueError:
                 st.warning("Date d'abonnement invalide reçue de l'API. Contactez l'administrateur.")
                 return False
        return True
    
    return False

# --- Initialisation de l'état de la session (NETTOYÉ) ---
if "charges_db" not in st.session_state:
    st.session_state.charges_db = [
        {"id": 1, "nature": "Salaire", "montant": 200000.0, "date": "2025-09-19"},
        {"id": 2, "nature": "Loyer", "montant": 150000.0, "date": "2025-09-20"},
        {"id": 3, "nature": "Marketing", "montant": 50000.0, "date": "2025-09-21"},
    ]
if "next_charge_id" not in st.session_state:
    st.session_state.next_charge_id = 4 

if "user_settings" not in st.session_state: st.session_state.user_settings = {} 
if "cart" not in st.session_state: st.session_state.cart = {} 

# --- NOUVELLE INITIALISATION : Données Utilisateur (Venant de l'API) ---
if "user_data" not in st.session_state: st.session_state.user_data = {} 

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = None
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "current_view" not in st.session_state: st.session_state.current_view = "client"
if "auth_mode" not in st.session_state: st.session_state.auth_mode = "login"


# ----------------------------------------------------------------------
# --- PAGES D'AUTHENTIFICATION (MISES À JOUR) ---
# ----------------------------------------------------------------------

def show_password_reset():
    st.subheader("Réinitialiser le Mot de Passe")
    st.warning("Veuillez contacter l'administrateur pour la réinitialisation.")
    st.markdown("---")
    if st.button("Retour à la connexion", key="back_to_login_btn"):
        set_auth_mode("login")

# FONCTION DE CONNEXION MISE À JOUR (Utilise l'API /login)
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
                    login_payload = {
                        "username": username,
                        "password": password 
                    }
                    # Appel API pour se connecter (POST /login)
                    success, result = handle_api_request("POST", "/login", data=login_payload)
                    
                    if success:
                        user_info = result 
                        
                        st.session_state.logged_in = True
                        st.session_state.username = user_info.get("username", username)
                        st.session_state.is_admin = user_info.get("is_admin", False)
                        st.session_state.user_data = user_info 
                        
                        st.success(f"Connexion réussie pour {st.session_state.username} !")
                        st.rerun()
                    else:
                        st.error(f"Nom d'utilisateur ou mot de passe incorrect : {result}")
            
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
                st.markdown("**Contact :**")
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
        
        **Pour activer votre compte, veuillez payer sur le numéro :** **{NUMERO_PAIEMENT}**
        
        L'administrateur validera votre abonnement après confirmation du paiement.
        """)

def show_payment_page():
    st.title("Abonnement Expiré ou Inactif")
    st.warning("Votre compte est inactif ou votre abonnement est expiré. Veuillez le renouveler pour accéder à l'application.")
    st.subheader("Instructions de paiement (5000 FCFA/mois)")
    st.markdown(f"Pour renouveler votre abonnement, veuillez effectuer un paiement de **5000 FCFA** sur le numéro : **{NUMERO_PAIEMENT}**.")
    whatsapp_link = f"https://wa.me/{NUMERO_PAIEMENT}?text=Bonjour,%20je%20souhaite%20activer%20mon%20abonnement%20de%205000%20FCFA.%20Mon%20nom%20d'utilisateur%20est%20*{st.session_state.username}*.%20J'ai%20effectué%20le%20paiement."
    st.link_button(
        f"📲 Contacter l'administrateur ({NUMERO_PAIEMENT})",
        url=whatsapp_link,
        type="primary",
        use_container_width=True
    )
    st.markdown("L'administrateur activera manuellement votre compte après confirmation.")
    st.markdown("---")
    if st.button("Retour à la page de connexion"):
        logout()

# ----------------------------------------------------------------------
# --- TABLEAU DE BORD ADMIN (MIS À JOUR) ---
# ----------------------------------------------------------------------

def show_charge_management():
    """Gestion des charges dans le dashboard admin (reste locale pour l'instant)."""
    st.header("Gestion des Charges (Dépenses) - ⚠️ Locale")
    df_charges = pd.DataFrame(st.session_state.charges_db)
    if not df_charges.empty:
        df_charges['date'] = pd.to_datetime(df_charges['date'])
        df_charges['Montant (FCFA)'] = df_charges['montant'].apply(lambda x: f"{x:,.0f} FCFA")
        st.dataframe(df_charges.drop(columns=['montant']), hide_index=True, use_container_width=True)
        generate_download_buttons(df_charges, "rapport_charges")

    with st.expander("➕ Ajouter une Nouvelle Charge"):
        with st.form("add_charge_form"):
            new_nature = st.text_input("Nature de la charge", key="new_charge_nature")
            new_montant = st.number_input("Montant (FCFA)", min_value=1.0, step=100.0, key="new_charge_montant")
            new_date = st.date_input("Date", value="today", key="new_charge_date")
            add_charge_button = st.form_submit_button("Ajouter la Charge", type="primary")

            if add_charge_button:
                if new_nature and new_montant > 0:
                    add_charge(new_nature, new_montant, new_date.strftime("%Y-%m-%d"))
                    st.success(f"Charge '{new_nature}' de {new_montant:,.0f} FCFA ajoutée.")
                    st.rerun()
                else:
                    st.error("Veuillez remplir la nature et un montant valide.")


# DASHBOARD ADMIN AVEC GESTION DES UTILISATEURS VIA API
def show_admin_dashboard():
    st.title("Tableau de Bord Administrateur")
    st.button("Voir l'espace client", on_click=set_view_client)
    st.header("Gestion des Utilisateurs")
    
    users_list = load_users_data() # APPEL API
    
    user_data = []
    for user_info in users_list:
        sub_end = user_info.get("subscription_end_date")
        user_data.append({
            "Nom d'utilisateur": user_info.get('username'),
            "Téléphone": f"{user_info.get('country_code', '')}{user_info.get('phone_number')}",
            "Statut d'abonnement": "🟢 Actif" if user_info.get("is_active") else "🔴 Inactif",
            "Date d'expiration": sub_end if sub_end else "N/A"
        })
    
    df_users = pd.DataFrame(user_data)
    st.dataframe(df_users, hide_index=True, use_container_width=True)
    
    st.subheader("Modifier l'abonnement d'un utilisateur")
    
    if not users_list:
        st.info("Aucun autre utilisateur client à gérer (Vérifiez la connexion API /users/).")
    else:
        user_usernames = [u['username'] for u in users_list]
        user_to_update_name = st.selectbox("Sélectionner un utilisateur", options=user_usernames, key="admin_user_select")
        
        if user_to_update_name:
            current_info = next(u for u in users_list if u['username'] == user_to_update_name)
            
            st.write(f"**Utilisateur sélectionné :** `{user_to_update_name}`")
            st.markdown(f"**Statut actuel :** {current_info['is_active'] and '🟢 Actif' or '🔴 Inactif'}")
            st.write(f"**Expire le :** {current_info['subscription_end_date'] if current_info.get('subscription_end_date') else 'N/A'}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Activer / Prolonger l'abonnement (1 Mois)", key="btn_activate", type="primary"):
                    new_end_date = (datetime.now().date() + timedelta(days=30)).strftime("%Y-%m-%d")
                    # Appel API pour activation/prolongation (PUT /users/{username}/subscription)
                    payload = {"is_active": True, "subscription_end_date": new_end_date}
                    success, result = handle_api_request("PUT", f"/users/{user_to_update_name}/subscription", data=payload)
                    
                    if success:
                        st.success(f"Abonnement de **{user_to_update_name}** activé/prolongé jusqu'au **{new_end_date}**.")
                        st.cache_data.clear() 
                        st.rerun()
                    else:
                        st.error(f"Échec de l'activation : {result}")

            with col2:
                if current_info.get('is_active', False):
                    if st.button("🔴 Suspendre l'abonnement", key="btn_suspend"):
                        # Appel API pour suspension (PUT /users/{username}/subscription)
                        payload = {"is_active": False, "subscription_end_date": current_info.get('subscription_end_date')}
                        success, result = handle_api_request("PUT", f"/users/{user_to_update_name}/subscription", data=payload)
                        
                        if success:
                            st.warning(f"Abonnement de **{user_to_update_name}** suspendu.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Échec de la suspension : {result}")
                else:
                    st.info("L'abonnement est déjà suspendu ou expiré.")

    st.markdown("---")
    show_charge_management()

# ----------------------------------------------------------------------
# --- PAGES CLIENT (NON MODIFIÉES POUR L'AUTH) ---
# ----------------------------------------------------------------------

def submit_purchase_order(fournisseur_id, total_montant, items):
    """Soumet la commande d'achat à l'API."""
    if not items:
        return False, "Le panier est vide."
        
    commande_data = {
        "fournisseur_id": fournisseur_id,
        "montant_total": total_montant,
        "items": items,
        "date_commande": datetime.now().isoformat(),
        "cout_total": total_montant 
    }
    
    success, result = handle_api_request('POST', '/commandes/', data=commande_data)
    
    if success:
        st.session_state.cart = {} 
        st.cache_data.clear() 
    
    return success, result

def show_cart_summary(df_fournisseurs):
    st.markdown("---")
    st.subheader("🛒 Récapitulatif du Panier d'Achat")
    
    if not st.session_state.cart:
        st.info("Le panier est vide.")
        return

    cart_list = []
    total_montant = 0
    first_fournisseur_id = None
    
    for product_id, item in st.session_state.cart.items():
        montant_item = item['quantity'] * item['price_achat']
        total_montant += montant_item
        
        if first_fournisseur_id is None:
            first_fournisseur_id = item['fournisseur_id']
        elif first_fournisseur_id != item['fournisseur_id']:
            pass 

        fournisseur_name = df_fournisseurs[df_fournisseurs['ID Fournisseur'] == item['fournisseur_id']]['Nom Fournisseur'].iloc[0] if not df_fournisseurs.empty and item['fournisseur_id'] in df_fournisseurs['ID Fournisseur'].values else "Inconnu"

        cart_list.append({
            'ID Produit': product_id,
            'Produit': item['product_name'],
            'Quantité': item['quantity'],
            "Prix Achat Unitaire (FCFA)": item['price_achat'],
            'Montant (FCFA)': montant_item,
            'Fournisseur': fournisseur_name
        })

    df_cart = pd.DataFrame(cart_list)
    
    st.dataframe(
        df_cart[['Produit', 'Quantité', 'Prix Achat Unitaire (FCFA)', 'Montant (FCFA)', 'Fournisseur']], 
        hide_index=True, 
        use_container_width=True,
        column_config={
            "Prix Achat Unitaire (FCFA)": st.column_config.NumberColumn("Prix Achat Unitaire (FCFA)", format="%.0f FCFA"),
            "Montant (FCFA)": st.column_config.NumberColumn("Montant (FCFA)", format="%.0f FCFA"),
        }
    )

    st.markdown(f"**Montant Total de la Commande :** **{total_montant:,.0f} FCFA**")
    
    col_submit, col_clear = st.columns([2, 1])

    with col_submit:
        if st.button("✅ Soumettre la Commande d'Achat", type="primary"):
            if first_fournisseur_id:
                items_for_api = [
                    {"product_id": item['ID Produit'], "quantite_commandee": item['Quantité'], "prix_unitaire_achat": item['Prix Achat Unitaire (FCFA)']}
                    for item in cart_list
                ]
                
                success, result = submit_purchase_order(first_fournisseur_id, total_montant, items_for_api)
                
                if success:
                    st.success(f"Commande d'Achat soumise avec succès ! ID: {result.get('id', 'N/A')}")
                    st.session_state.cart = {} 
                    st.rerun()
                else:
                    st.error(f"Échec de la soumission de la commande : {result}")
            else:
                 st.error("Impossible de déterminer le fournisseur pour la commande.")
                 
    with col_clear:
        if st.button("🗑️ Vider le Panier"):
            st.session_state.cart = {}
            st.success("Panier vidé.")
            st.rerun()

def show_product_management(df_products, df_fournisseurs):
    df_prods_display = df_products.copy()
    if not df_fournisseurs.empty and 'ID Fournisseur' in df_prods_display.columns:
        df_prods_display = df_prods_display.merge(
            df_fournisseurs[['ID Fournisseur', 'Nom Fournisseur']], 
            on='ID Fournisseur', 
            how='left'
        )
        df_prods_display['Nom Fournisseur'] = df_prods_display['Nom Fournisseur'].fillna('Non défini')
    
    st.title("Gestion des Produits et Commandes d'Achat")

    tab_list = ["Liste des Produits", "Ajouter/Modifier Produit", "Analyse des Prix", "Nouvelle Commande d'Achat"]
    tab_produits, tab_add, tab_analyse, tab_commande = st.tabs(tab_list)

    with tab_produits:
        st.subheader("Inventaire Actuel des Produits")
        if not df_prods_display.empty:
            cols_to_display = [
                'ID Produit', 'Produit', 'Stock Actuel', 
                'Prix Achat Unitaire (FCFA)', 'Prix Vente Unitaire (FCFA)', 
                'Nom Fournisseur'
            ]
            st.dataframe(
                df_prods_display[[col for col in cols_to_display if col in df_prods_display.columns]], 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "Prix Achat Unitaire (FCFA)": st.column_config.NumberColumn("Prix Achat Unitaire (FCFA)", format="%.0f FCFA"),
                    "Prix Vente Unitaire (FCFA)": st.column_config.NumberColumn("Prix Vente Unitaire (FCFA)", format="%.0f FCFA"),
                }
            )
            generate_download_buttons(df_prods_display, "rapport_produits")
        else:
            st.info("Aucun produit trouvé. Veuillez en ajouter un.")

    with tab_add:
        st.subheader("Ajouter ou Modifier un Produit")
        st.info("Cette section nécessite un formulaire d'ajout et de modification des produits.")

    with tab_analyse:
        st.subheader("Analyse des Marge et des Prix")
        if not df_products.empty:
            df_analysis = df_products.copy()
            df_analysis['Prix Achat Unitaire (FCFA)'] = pd.to_numeric(df_analysis['Prix Achat Unitaire (FCFA)'], errors='coerce').fillna(0)
            df_analysis['Prix Vente Unitaire (FCFA)'] = pd.to_numeric(df_analysis['Prix Vente Unitaire (FCFA)'], errors='coerce').fillna(0)
            
            df_analysis['Marge Brute (FCFA)'] = df_analysis['Prix Vente Unitaire (FCFA)'] - df_analysis['Prix Achat Unitaire (FCFA)']
            df_analysis['Marge %'] = (df_analysis['Marge Brute (FCFA)'] / df_analysis['Prix Achat Unitaire (FCFA)']) * 100
            df_analysis['Marge %'] = df_analysis['Marge %'].replace([float('inf'), float('-inf')], 0).fillna(0)

            st.dataframe(
                df_analysis[[
                    'Produit', 
                    'Prix Achat Unitaire (FCFA)', 
                    'Prix Vente Unitaire (FCFA)', 
                    'Marge Brute (FCFA)', 
                    'Marge %'
                ]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Prix Achat Unitaire (FCFA)": st.column_config.NumberColumn("Prix Achat (FCFA)", format="%.0f FCFA"),
                    "Prix Vente Unitaire (FCFA)": st.column_config.NumberColumn("Prix Vente (FCFA)", format="%.0f FCFA"),
                    "Marge Brute (FCFA)": st.column_config.NumberColumn("Marge Brute (FCFA)", format="%.0f FCFA"),
                    "Marge %": st.column_config.NumberColumn("Marge (%)", format="%.2f %%"),
                }
            )
            
            fig = px.bar(
                df_analysis.sort_values('Marge Brute (FCFA)', ascending=False),
                x='Produit', 
                y='Marge Brute (FCFA)',
                color='Marge Brute (FCFA)',
                title='Marge Brute par Produit (FCFA)',
                labels={'Marge Brute (FCFA)': 'Marge Brute (FCFA)'}
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.info("Aucune donnée de produit pour l'analyse.")

    with tab_commande:
        st.subheader("Ajouter un Produit au Panier d'Achat (Nouvelle Commande)")
        
        if df_products.empty:
            st.error("Aucun produit trouvé. Veuillez en ajouter un d'abord.")
            return

        product_options = {
            f"{str(row['Produit'])} (Stock: {int(row['Stock Actuel']):,})": str(row['ID Produit'])
            for _, row in df_products.iterrows()
            if row.get('ID Produit') is not None and row.get('Produit') is not None
        }

        if not product_options:
            st.warning("Aucun produit avec un ID valide n'a pu être chargé. (Vérifiez la base de données).")
            return
            
        product_display_names = list(product_options.keys())
        selected_display_name = st.selectbox(
            "Sélectionner un produit pour la commande",
            product_display_names,
            key="selected_product_cart"
        )
        
        selected_product_id = product_options.get(selected_display_name)

        if selected_product_id:
            selected_row = df_products[df_products['ID Produit'] == selected_product_id].iloc[0]
            current_stock = selected_row['Stock Actuel'] 
            achat_price = selected_row['Prix Achat Unitaire (FCFA)']
            
            col_qty, _ = st.columns([1, 4])

            with col_qty:
                quantity = st.number_input(
                    "Quantité à Commander", 
                    min_value=1, 
                    max_value=None, 
                    value=1, 
                    step=1, 
                    key="cart_quantity"
                )
            
            st.markdown(f"""
            **Stock Actuel:** **{current_stock:,.0f}**
            
            **Prix unitaire d'achat:** **{achat_price:,.0f} FCFA** (Le prix final sera utilisé lors de la soumission de la commande via l'API)
            """)

            is_add_disabled = (quantity < 1) 

            if st.button("🛒 Ajouter au Panier", type="primary", disabled=is_add_disabled):
                if selected_product_id in st.session_state.cart:
                    st.session_state.cart[selected_product_id]['quantity'] += int(quantity)
                else:
                    st.session_state.cart[selected_product_id] = {
                        'product_name': selected_row['Produit'],
                        'quantity': int(quantity),
                        'price_achat': achat_price,
                        'fournisseur_id': selected_row['ID Fournisseur'],
                        'current_stock': current_stock 
                    }
                st.success(f"**{int(quantity)} x {selected_row['Produit']}** ajouté(s) au panier.")
                st.rerun() 
            
            if is_add_disabled:
                st.info("Veuillez entrer une quantité pour ajouter au panier.")
            
            show_cart_summary(df_fournisseurs)
        else:
            st.warning("Veuillez sélectionner un produit.")
            
def show_fournisseur_management(df_fournisseurs):
    st.title("Gestion des Fournisseurs")
    if not df_fournisseurs.empty:
        st.dataframe(df_fournisseurs, hide_index=True, use_container_width=True)
    else:
        st.info("Aucun fournisseur trouvé.")
    st.warning("Section en cours de construction pour l'ajout/modification.")

def show_command_history(commandes_data, df_fournisseurs, df_products):
    st.title("Historique des Commandes d'Achat")
    if commandes_data:
        df_commandes = pd.DataFrame(commandes_data)
        
        all_items = []
        for index, row in df_commandes.iterrows():
            commande_id = row.get('id', 'N/A')
            date_commande = row.get('date_commande', 'N/A')[:10]
            fournisseur_id = row.get('fournisseur_id', 'N/A')
            montant_total = row.get('montant_total', 0)
            statut = row.get('statut', 'N/A')
            
            fournisseur_name = df_fournisseurs[df_fournisseurs['ID Fournisseur'] == str(fournisseur_id)]['Nom Fournisseur'].iloc[0] if not df_fournisseurs.empty and str(fournisseur_id) in df_fournisseurs['ID Fournisseur'].astype(str).values else "Inconnu"

            for item in row.get('items', []):
                product_id = item.get('product_id', 'N/A')
                product_name = df_products[df_products['ID Produit'] == str(product_id)]['Produit'].iloc[0] if not df_products.empty and str(product_id) in df_products['ID Produit'].astype(str).values else "Produit Inconnu"
                
                all_items.append({
                    'ID Commande': commande_id,
                    'Date': date_commande,
                    'Fournisseur': fournisseur_name,
                    'Produit': product_name,
                    'Quantité': item.get('quantite_commandee', 0),
                    'Prix Achat Unitaire': item.get('prix_unitaire_achat', 0),
                    'Statut': statut,
                    'Total Commande (FCFA)': montant_total
                })
        
        if all_items:
            df_history = pd.DataFrame(all_items)
            st.dataframe(
                df_history, 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "Total Commande (FCFA)": st.column_config.NumberColumn("Total Commande (FCFA)", format="%.0f FCFA"),
                    "Prix Achat Unitaire": st.column_config.NumberColumn("Prix Achat Unitaire (FCFA)", format="%.0f FCFA"),
                }
            )
            generate_download_buttons(df_history, "historique_commandes_achat")
        else:
             st.info("Aucun détail d'article de commande à afficher.")
    else:
        st.info("Aucune commande enregistrée pour le moment.")
    
    st.warning("Section en cours de construction pour la modification/suppression des commandes.")


def show_user_settings_page():
    st.title("Paramètres Utilisateur et Application")
    user_info = st.session_state.user_data
    
    st.subheader("Statut de l'Abonnement")
    if user_info:
        if st.session_state.is_admin:
            st.success("Statut: Administrateur (Accès illimité)")
        elif user_info.get("is_active"):
            end_date = user_info.get("subscription_end_date", "N/A")
            st.success(f"Statut: Actif 🟢. Date d'expiration: **{end_date}**")
        else:
            st.error("Statut: Inactif 🔴. Votre abonnement est expiré ou n'est pas activé.")

    st.subheader("Informations de Contact")
    st.info(f"""
    **Nom d'utilisateur:** `{st.session_state.username}`
    **Téléphone:** `{user_info.get('country_code', '')}{user_info.get('phone_number', 'N/A')}`
    """)


def show_client_page():
    st.sidebar.title(f"Bienvenue, {get_display_name(st.session_state.username)}")
    
    df_products = load_products_data()
    df_fournisseurs = load_fournisseurs_data()
    commandes_data = load_commandes_data()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Tableau de Bord", 
        "📦 Produits & Achats", 
        "🤝 Fournisseurs", 
        "📜 Historique Commandes",
        "⚙️ Paramètres"
    ])
    
    with tab1:
        st.title("Synthèse des Achats")
        st.info("Le tableau de bord est en cours de construction.")
        
    with tab2:
        show_product_management(df_products, df_fournisseurs)
        
    with tab3:
        show_fournisseur_management(df_fournisseurs)
        
    with tab4:
        show_command_history(commandes_data, df_fournisseurs, df_products)
        
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
            show_admin_dashboard() 
        # Espace Client
        else:
            show_client_page()
            
        # Bouton de déconnexion toujours dans la barre latérale si connecté
        st.sidebar.button("Déconnexion", on_click=logout)
    else:
        # Page de connexion / Inscription
        show_login_page()
        
if __name__ == "__main__":
    main()