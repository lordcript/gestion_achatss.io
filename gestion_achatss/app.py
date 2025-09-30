import streamlit as st
import hashlib
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import io
import base64

# Configuration de la page
st.set_page_config(
    page_title="Gestion des Achats",
    layout="wide"
)

# --- Constantes ---
NUMERO_PAIEMENT = "+221773867580"
DEFAULT_COUNTRY_CODE = "+221" # Indicatif par défaut (Sénégal)

# --- Fonction de hachage du mot de passe ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- Fonctions utilitaires pour le téléchargement ---

@st.cache_data
def to_excel(df):
    """Convertit un DataFrame en fichier Excel (XLSX) en mémoire."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Rapport')
    processed_data = output.getvalue()
    return processed_data

@st.cache_data
def to_plain_text_report(df, title="Rapport"):
    """
    Convertit un DataFrame en un rapport textuel formaté (simulant le contenu d'un PDF simple).
    CORRECTION: Cette fonction génère un fichier texte brut pour garantir l'ouverture.
    """
    report = f"\n\n*** {title.upper()} ***\n\n"
    
    # Formatage simple du DataFrame en string
    report += df.to_string(index=False, justify='left', line_width=120)
    
    # Ajout d'un total si la colonne 'Montant' existe
    if 'Montant' in df.columns or 'Montant Total' in df.columns:
        # On essaie d'abord 'Montant' (pour les rapports de tab2) puis 'Montant Total' (pour l'historique d'achats tab3)
        amount_col = 'Montant' if 'Montant' in df.columns else 'Montant Total'
        try:
            total_amount = df[amount_col].sum()
            report += f"\n\n---"
            report += f"\nTOTAL GÉNÉRAL DES MONTANTS: {total_amount:,.0f} FCFA\n"
            report += f"---"
        except Exception:
             # Si la colonne n'est pas numérique, on ignore le total
             pass
        
    return report.encode('utf-8')


def generate_download_buttons(df, filename_base):
    """Affiche les boutons de téléchargement TXT (principal) et XLSX."""
    if df.empty:
        st.warning("Aucune donnée disponible pour le téléchargement.")
        return

    # Deux colonnes pour les boutons de téléchargement (TXT en principal)
    col_txt, col_xlsx, _ = st.columns([1, 1, 4]) 

    # 1. TXT Download (Correction: utilise le bon MIME et l'extension)
    txt_title = filename_base.replace('_', ' ').replace('Rapport', 'Rapport').capitalize()
    txt_data = to_plain_text_report(df, title=txt_title) # Appel à la fonction corrigée

    with col_txt:
        st.download_button(
            label="📄 Télécharger en TXT", # Affichage correct
            data=txt_data,
            file_name=f'{filename_base}.txt', # Extension .txt
            mime='text/plain', # MIME type correct
            key=f'txt_download_{filename_base}',
            type="primary" # Mettre l'accent sur le TXT
        )
        
    # 2. XLSX Download
    with col_xlsx:
        st.download_button(
            label="💾 Télécharger en XLSX",
            data=to_excel(df),
            file_name=f'{filename_base}.xlsx',
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f'xlsx_download_{filename_base}'
        )


# --- Base de données : Fonctions d'aide (inchangées) ---

def get_phone_number_from_db(username):
    """Récupère le numéro de téléphone formaté pour un utilisateur."""
    user_info = st.session_state.USER_DB.get(username)
    if user_info and user_info.get("country_code") and user_info.get("phone_number"):
        return f"{user_info['country_code']}{user_info['phone_number']}"
    return "N/A"

def is_phone_unique(country_code, phone_number, exclude_user=None):
    """Vérifie si la combinaison indicatif/numéro est déjà utilisée, en excluant optionnellement un utilisateur."""
    full_number = f"{country_code}{phone_number}"
    for user, user_info in st.session_state.USER_DB.items():
        if user == exclude_user:
            continue
        if f"{user_info.get('country_code', '')}{user_info.get('phone_number', '')}" == full_number:
            return False
    return True

# Initialisation de la base de données Utilisateurs (inchangée)
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
    # Ajout du numéro pour client2 s'il existe
    if "client2" in st.session_state.USER_DB:
        st.session_state.USER_DB["client2"].update({
            "country_code": DEFAULT_COUNTRY_CODE,
            "phone_number": "772222222"
        })

# Le reste de l'initialisation de la DB reste inchangé
if "products_db" not in st.session_state:
    st.session_state.products_db = {
        1: {"name": "Ordinateur portable", "price": 500, "stock": 10},
        2: {"name": "Souris sans fil", "price": 25, "stock": 50},
        3: {"name": "Clavier mécanique", "price": 75, "stock": 20},
    }

if "next_product_id" not in st.session_state:
    st.session_state.next_product_id = 4 

if "purchases_db" not in st.session_state:
    st.session_state.purchases_db = {
        "commande_001": {
            "client": "client1",
            "date": "2025-09-20",
            "articles": [
                {"product_id": 1, "quantity": 1, "total_amount": 500},
                {"product_id": 2, "quantity": 2, "total_amount": 50},
            ],
            "total_commande": 550
        },
        "commande_002": {
            "client": "client2",
            "date": "2024-07-15",
            "articles": [
                {"product_id": 3, "quantity": 1, "total_amount": 75}
            ],
            "total_commande": 75
        },
        "commande_003": {
            "client": "client1",
            "date": "2025-09-21",
            "articles": [
                {"product_id": 3, "quantity": 1, "total_amount": 75}
            ],
            "total_commande": 75
        }
    }

if "charges_db" not in st.session_state:
    st.session_state.charges_db = [
        {"id": 1, "nature": "Salaire", "montant": 2000.0, "date": "2025-09-19"},
        {"id": 2, "nature": "Loyer", "montant": 1500.0, "date": "2025-09-20"},
        {"id": 3, "nature": "Marketing", "montant": 500.0, "date": "2025-09-21"},
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

# --- NOUVELLE INITIALISATION : Panier d'achat temporaire ---
if "cart" not in st.session_state: 
    st.session_state.cart = {} # {product_id: quantity}

# --- Initialisation de l'état de la session (inchangée) ---
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

# --- Fonctions de basculement, déconnexion et abonnement (inchangées) ---

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
    
    # Vider le panier à la déconnexion
    st.session_state.cart = {}

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
    # 1. Vérification de l'unicité du nom d'utilisateur
    if username in st.session_state.USER_DB:
        return False, "Ce nom d'utilisateur existe déjà. Il doit être unique."
    
    if not username or not password or not country_code or not phone_number:
        return False, "Veuillez remplir tous les champs obligatoires."

    # 2. Vérification de l'unicité du numéro de téléphone
    if not is_phone_unique(country_code, phone_number):
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
            sub_end_date = datetime.strptime(sub_end_date_str, "%Y-%m-%d")
            if sub_end_date.date() < datetime.now().date():
                st.session_state.USER_DB[st.session_state.username]["is_active"] = False
                st.session_state.logged_in = False
                st.error("Votre abonnement a expiré. Veuillez vous reconnecter.")
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
         return

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

def show_charge_management():
    st.header("Gestion des Charges du Magasin")
    
    if not st.session_state.charges_db:
        st.info("Aucune charge enregistrée.")
        df_charges = pd.DataFrame()
    else:
        df_charges = pd.DataFrame(st.session_state.charges_db)
        df_charges['montant'] = df_charges['montant'].astype(float) 
        df_charges['date'] = pd.to_datetime(df_charges['date'])
        df_charges = df_charges.sort_values(by="date", ascending=False).reset_index(drop=True)
        df_charges = df_charges.rename(columns={"nature": "Nature de la Charge", "montant": "Montant (FCFA)", "date": "Date"})

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
        charge_options = {row['id']: f"{row['Nature de la Charge']} - {row['Montant (FCFA)']:,.0f} CFA ({row['Date'].strftime('%Y-%m-%d')})" for _, row in df_charges.iterrows()}
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


# --- Page de paramètres utilisateur (inchangée) ---
def show_user_settings_page():
    st.header("⚙️ Paramètres Utilisateur & Société")
    current_username = st.session_state.username
    current_settings = st.session_state.user_settings[current_username]
    current_user_db = st.session_state.USER_DB[current_username]
    
    # --- 1. Modification du Numéro de Téléphone ---
    st.subheader("Modifier votre Numéro de Téléphone")
    
    with st.form("update_phone_form"):
        col_code, col_phone = st.columns([1, 2])
        
        with col_code:
            # Récupère l'indicatif actuel pour le pré-remplir
            current_code = current_user_db.get("country_code", DEFAULT_COUNTRY_CODE)
            new_country_code = st.text_input("Nouvel Indicatif Pays", value=current_code, key="settings_country_code")
        
        with col_phone:
            # Récupère le numéro actuel pour le pré-remplir
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

    # --- 2. Préférences d'affichage du Nom (inchangée) ---
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
    
    # --- 3. Logo de la Société (inchangée) ---
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
            st.info("Utilisez le champ ci-dessus pour charger un nouveau logo.")


    with col_display:
        if current_settings["company_logo_base64"]:
            logo_base64 = current_settings["company_logo_base64"]
            logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 150px; max-width: 100%; border-radius: 5px; border: 1px solid #ccc; padding: 5px;">'
            st.markdown("Votre Logo Actuel :")
            st.markdown(logo_html, unsafe_allow_html=True)
        else:
            st.info("Aucun logo enregistré.")
            
    st.markdown("---")
    
    # --- 4. Partage de l'Application (inchangée) ---
    st.subheader("Partage de l'Application")
    
    st.info("Pour partager cette application, copiez et collez le lien ci-dessous.")
    
    app_link = "https://votre-application-gestion-achats.streamlit.app" 
    
    st.text_input("Lien de partage de l'application", value=app_link, disabled=True)
    
    st.link_button("Partager sur WhatsApp", url=f"https://wa.me/?text=Découvrez%20mon%20outil%20de%20gestion%20des%20achats%20:%20{app_link}", type="primary")


# --- NOUVELLES FONCTIONS DE PANIER ---

def add_to_cart(product_id, quantity):
    """Ajoute un produit au panier temporaire et déduit le stock."""
    # S'assurer qu'on n'ajoute pas plus que ce qu'il y a en stock (après avoir tenu compte de ce qui est déjà dans le panier)
    available_stock = st.session_state.products_db[product_id]["stock"]
    
    if quantity > available_stock:
        st.error(f"Seulement {available_stock} articles restants en stock pour {st.session_state.products_db[product_id]['name']}.")
        return

    if product_id in st.session_state.cart:
        st.session_state.cart[product_id] += quantity
    else:
        st.session_state.cart[product_id] = quantity
    
    # Déduire du stock (immédiatement pour éviter les surventes)
    st.session_state.products_db[product_id]["stock"] -= quantity 
    st.success(f"Ajouté {quantity}x **{st.session_state.products_db[product_id]['name']}** au panier.")

def finalize_purchase(username):
    """Finalise le panier actuel en une commande."""
    if not st.session_state.cart:
        st.error("Le panier est vide. Veuillez ajouter des produits avant de finaliser l'achat.")
        return False

    articles_list = []
    total_commande = 0

    for product_id, quantity in st.session_state.cart.items():
        product_info = st.session_state.products_db[product_id]
        total_amount = product_info["price"] * quantity
        articles_list.append({
            "product_id": product_id,
            "quantity": quantity,
            "total_amount": total_amount
        })
        total_commande += total_amount
    
    # Générer un nouvel ID de commande
    new_command_id = f"commande_{len(st.session_state.purchases_db) + 1:03d}"
    
    # Stocker l'achat dans la base de données
    new_purchase = {
        "client": username,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "articles": articles_list,
        "total_commande": total_commande
    }
    st.session_state.purchases_db[new_command_id] = new_purchase
    
    # Vider le panier pour la prochaine commande
    st.session_state.cart = {}
    
    st.success(f"Commande **{new_command_id}** finalisée avec succès pour un total de **{total_commande:,.0f} FCFA**!")
    st.balloons()
    return True

# --- Fin des NOUVELLES FONCTIONS DE PANIER ---


def show_client_page():
    
    current_username = st.session_state.username
    current_settings = st.session_state.user_settings.get(current_username, {"display_name_format": "full", "company_logo_base64": None})
    user_format = current_settings["display_name_format"]
    display_name = get_display_name(current_username, user_format)

    st.title("Tableau de Bord de votre Magasin")
    
    col_welcome, col_logo = st.columns([4, 1])
    with col_welcome:
        st.write(f"👋 Bienvenue, **{display_name}** !")
    
    with col_logo:
        logo_base64 = current_settings["company_logo_base64"]
        if logo_base64:
            logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 60px; max-width: 100%; border-radius: 5px; float: right;">'
            st.markdown(logo_html, unsafe_allow_html=True)

    if st.session_state.is_admin:
        st.button("Retour au Tableau de Bord Admin", on_click=set_view_admin)
        
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Gestion des Produits", "Statistiques & Rapports", "Catalogue des Achats", "Gestion des Charges", "Paramètres Utilisateur"])
    
    with tab1:
        st.header("Gestion des Produits")
        df_products = pd.DataFrame(st.session_state.products_db.values(), index=st.session_state.products_db.keys())
        st.subheader("Catalogue de produits")
        st.dataframe(df_products)
        
        st.subheader("Ajouter un nouveau produit")
        with st.form("add_product_form", clear_on_submit=True):
            next_id = st.session_state.next_product_id
            st.info(f"Le nouvel ID produit sera : {next_id}")
            new_name = st.text_input("Nom du produit", key="add_name")
            new_price = st.number_input("Prix (FCFA)", min_value=1.0, key="add_price")
            new_stock = st.number_input("Stock", min_value=0, step=1, key="add_stock")
            add_button = st.form_submit_button("Ajouter le produit")
            
            if add_button:
                if new_name and new_price:
                    st.session_state.products_db[next_id] = {"name": new_name, "price": new_price, "stock": new_stock}
                    st.session_state.next_product_id += 1 
                    st.success("Produit ajouté avec succès !")
                    st.rerun()
                else:
                    st.warning("Veuillez remplir tous les champs.")

        st.subheader("Modifier ou supprimer un produit")
        product_ids = list(st.session_state.products_db.keys())
        if product_ids:
            product_to_modify = st.selectbox("Sélectionner un produit", options=product_ids, format_func=lambda x: f"{x} - {st.session_state.products_db[x]['name']}", key="modify_select")
            
            if product_to_modify:
                with st.form("modify_product_form"):
                    current_name = st.session_state.products_db[product_to_modify]['name']
                    current_price = st.session_state.products_db[product_to_modify]['price']
                    current_stock = st.session_state.products_db[product_to_modify]['stock']
                    
                    updated_name = st.text_input("Nouveau nom du produit", value=current_name)
                    updated_price = st.number_input("Nouveau prix (FCFA)", value=float(current_price), min_value=1.0)
                    updated_stock = st.number_input("Nouveau stock", value=int(current_stock), min_value=0, step=1)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        modify_button = st.form_submit_button("Modifier le produit")
                    with col2:
                        delete_button = st.form_submit_button("Supprimer le produit")
                        
                if modify_button:
                    st.session_state.products_db[product_to_modify]['name'] = updated_name
                    st.session_state.products_db[product_to_modify]['price'] = updated_price
                    st.session_state.products_db[product_to_modify]['stock'] = updated_stock
                    st.success("Produit mis à jour avec succès !")
                    st.rerun()
                
                if delete_button:
                    del st.session_state.products_db[product_to_modify]
                    st.success("Produit supprimé avec succès !")
                    st.rerun()
        else:
            st.info("Aucun produit à modifier ou supprimer.")
            
        st.subheader("Flux de stock (Répartition)")
        if st.session_state.products_db:
            stock_data = pd.DataFrame(st.session_state.products_db.values())
            fig_stock = px.pie(stock_data, values='stock', names='name', title="Répartition des stocks par produit", hole=0.5)
            fig_stock.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_stock, use_container_width=True)
        else:
            st.info("Ajoutez des produits pour voir la répartition des stocks.")


    with tab2:
        st.header("Statistiques et Rapports")
        
        purchase_revenues = {}
        all_purchase_records = [] 
        for cmd_id, details in st.session_state.purchases_db.items():
            date_str = details["date"]
            amount = details["total_commande"]
            
            if date_str not in purchase_revenues:
                purchase_revenues[date_str] = 0
            purchase_revenues[date_str] += amount

            for item in details["articles"]:
                product_name = st.session_state.products_db.get(item['product_id'], {}).get('name', 'Inconnu')
                all_purchase_records.append({
                    "ID_Commande": cmd_id,
                    "Date": date_str,
                    "Client": details["client"],
                    "ID_Produit": item["product_id"],
                    "Produit": product_name,
                    "Quantité": item["quantity"],
                    "Montant": item["total_amount"]
                })


        df_revenues = pd.DataFrame(list(purchase_revenues.items()), columns=['Date', 'Montant'])
        df_revenues['Type'] = 'Achats (Revenus)'
        
        charge_amounts = {}
        for charge in st.session_state.charges_db:
            date_str = charge["date"]
            amount = charge["montant"]
            
            if date_str not in charge_amounts:
                charge_amounts[date_str] = 0
            charge_amounts[date_str] += amount
            
        df_charges_daily = pd.DataFrame(st.session_state.charges_db)
        df_charges_daily = df_charges_daily.rename(columns={"nature": "Nature", "montant": "Montant", "date": "Date"})
        
        df_charges_agg = pd.DataFrame(list(charge_amounts.items()), columns=['Date', 'Montant'])
        df_charges_agg['Type'] = 'Charges'

        total_ventes = df_revenues['Montant'].sum() if not df_revenues.empty else 0
        total_charges = df_charges_agg['Montant'].sum() if not df_charges_agg.empty else 0
        
        st.subheader("Résumé des transactions")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total des Achats", f"{total_ventes:,.0f} CFA")
        with col2:
            st.metric("Total des Charges", f"{total_charges:,.0f} CFA")
        with col3:
            st.metric("Marge Nette (Achats - Charges)", f"{total_ventes - total_charges:,.0f} CFA")
        
        st.markdown("---")

        st.subheader("Évolution Quotidienne des Achats vs. Charges")

        if not df_revenues.empty or not df_charges_agg.empty:
            df_combined_daily = pd.concat([df_revenues, df_charges_agg], ignore_index=True)
            df_combined_daily['Date'] = pd.to_datetime(df_combined_daily['Date'])
            df_combined_daily = df_combined_daily.sort_values(by='Date')
            
            fig_evolution = px.line(
                df_combined_daily, 
                x='Date', 
                y='Montant', 
                color='Type',
                title="Achats (Revenus) et Charges par Jour",
                markers=True,
                color_discrete_map={
                    'Achats (Revenus)': 'green', 
                    'Charges': 'red'
                }
            )
            fig_evolution.update_layout(xaxis_title="Date de la Transaction", yaxis_title="Montant (FCFA)")
            st.plotly_chart(fig_evolution, use_container_width=True)
        else:
            st.info("Aucune donnée d'achat ou de charge pour visualiser l'évolution quotidienne.")
        
        st.markdown("---")

        st.subheader("📊 Téléchargement des Rapports")
        
        # Rapport Achats (renommer la colonne Montant pour la fonction to_text_report)
        df_full_purchases_report = pd.DataFrame(all_purchase_records)
        df_full_purchases_report['Date'] = pd.to_datetime(df_full_purchases_report['Date'])
        # La colonne Montant existe déjà pour le total PDF
        
        # Rapport Charges (garder la colonne Montant)
        df_full_charges_report = df_charges_daily.drop(columns=['id'], errors='ignore')
        df_full_charges_report['Date'] = pd.to_datetime(df_full_charges_report['Date'])
        
        col_dl_achat, col_dl_charge = st.columns(2)
        
        with col_dl_achat:
            st.markdown("**Historique Détaillé des Achats :**")
            generate_download_buttons(df_full_purchases_report, "Rapport_Achats_Detaille")

        with col_dl_charge:
            st.markdown("**Historique Détaillé des Charges :**")
            generate_download_buttons(df_full_charges_report, "Rapport_Charges_Detaille")

        st.markdown("---")

        st.subheader("Répartition Globale : Achats vs. Charges")
        
        if total_ventes > 0 or total_charges > 0:
            df_repartition = pd.DataFrame({
                'Catégorie': ['Total Achats (Revenus)', 'Total Charges'],
                'Montant': [total_ventes, total_charges]
            })

            fig_repartition = px.pie(
                df_repartition, 
                values='Montant', 
                names='Catégorie', 
                title="Part des Achats et des Charges dans le Flux Financier", 
                hole=0.4, 
                color='Catégorie',
                color_discrete_map={
                    'Total Achats (Revenus)': 'darkgreen', 
                    'Total Charges': 'crimson'
                }
            )
            fig_repartition.update_traces(textinfo='percent+label', marker=dict(line=dict(color='#000000', width=1)))
            st.plotly_chart(fig_repartition, use_container_width=True)
        else:
            st.info("Les totaux des Achats et des Charges sont nuls. Le graphique de répartition ne peut pas être affiché.")
            
        st.markdown("---")

        all_articles = [item for sublist in [c['articles'] for c in st.session_state.purchases_db.values()] for item in sublist]
        
        if all_articles:
            df_articles = pd.DataFrame(all_articles)
            df_articles['product_name'] = df_articles['product_id'].apply(lambda x: st.session_state.products_db.get(x, {}).get('name', 'Inconnu'))
            
            st.subheader("Analyse des Ventes par Produit")
            product_sales = df_articles.groupby('product_name')['total_amount'].sum().reset_index()
            fig_sales = px.bar(product_sales, x='product_name', y='total_amount', title="Ventes Totales par Produit (FCFA)")
            st.plotly_chart(fig_sales, use_container_width=True)
            
            
            product_sales_agg = df_articles.groupby('product_name').agg(
                total_quantity=('quantity', 'sum'),
                total_amount=('total_amount', 'sum'),
            ).reset_index()

            st.subheader("Analyse de la performance des produits (Ventes vs Quantité)")
            fig_qty_sales = px.scatter(
                product_sales_agg, 
                x='total_quantity', 
                y='total_amount', 
                size='total_amount', 
                color='product_name',
                hover_name='product_name',
                title="Quantité Totale Vendue vs Montant Total des Ventes par Produit",
                labels={'total_quantity': 'Quantité Totale Vendue', 'total_amount': 'Montant Total des Ventes (FCFA)'}
            )
            st.plotly_chart(fig_qty_sales, use_container_width=True)

            purchase_records_trend = []
            for cmd_id, details in st.session_state.purchases_db.items():
                date = pd.to_datetime(details["date"])
                for item in details["articles"]:
                    product_name = st.session_state.products_db.get(item['product_id'], {}).get('name', 'Inconnu')
                    purchase_records_trend.append({
                        "Date": date,
                        "Produit": product_name,
                        "Quantité": item["quantity"],
                    })
            df_purchases_full = pd.DataFrame(purchase_records_trend)
            
            if not df_purchases_full.empty:
                st.subheader("Tendances d'Achat (par Période)")
                
                time_unit = st.radio(
                    "Sélectionner la granularité temporelle:",
                    ('Jour', 'Semaine', 'Mois', 'Année'),
                    horizontal=True,
                    key="time_unit_radio" 
                )
                
                if time_unit == 'Jour':
                    df_purchases_full['Time_Period'] = df_purchases_full['Date'].dt.strftime('%Y-%m-%d')
                elif time_unit == 'Semaine':
                    df_purchases_full['Time_Period'] = df_purchases_full['Date'].dt.to_period('W').astype(str)
                elif time_unit == 'Mois':
                    df_purchases_full['Time_Period'] = df_purchases_full['Date'].dt.strftime('%Y-%m') 
                else: 
                    df_purchases_full['Time_Period'] = df_purchases_full['Date'].dt.strftime('%Y')
                
                time_series_sales = df_purchases_full.groupby(['Time_Period', 'Produit'])['Quantité'].sum().reset_index()
                time_series_sales = time_series_sales.rename(columns={'Quantité': 'Quantité Totale Vendue'})
                
                fig_time_series = px.line(
                    time_series_sales, 
                    x='Time_Period', 
                    y='Quantité Totale Vendue', 
                    color='Produit',
                    title=f"Quantité de Produits Achetés par {time_unit}",
                    labels={'Time_Period': time_unit}
                )
                fig_time_series.update_xaxes(tickangle=45)
                st.plotly_chart(fig_time_series, use_container_width=True)
            
            st.subheader("Répartition des charges par type")
            if st.session_state.charges_db:
                charges_df_type = pd.DataFrame(st.session_state.charges_db)
                charges_type_agg = charges_df_type.groupby('nature')['montant'].sum().reset_index()
                charges_type_agg = charges_type_agg.rename(columns={'nature': 'Type de charge', 'montant': 'Montant'})
                fig_charges_type = px.pie(charges_type_agg, values='Montant', names='Type de charge', title="Répartition des charges par type")
                st.plotly_chart(fig_charges_type, use_container_width=True)
            else:
                st.info("Aucune charge enregistrée pour l'analyse.")
        else:
            st.info("Aucune donnée d'achat disponible pour l'analyse par produit.")

    with tab3:
        st.header("Catalogue des Achats")
        df_products = pd.DataFrame(st.session_state.products_db.values(), index=st.session_state.products_db.keys())
        df_products = df_products.rename(columns={"name": "Nom", "price": "Prix (FCFA)", "stock": "Stock"})
        st.dataframe(df_products, hide_index=True)

        st.subheader("🛒 Ajouter des produits au panier")
        
        available_products = {id: item for id, item in st.session_state.products_db.items() if item['stock'] > 0}
        
        if available_products:
            product_options = {id: f"{id} - {item['name']} ({item['price']} FCFA, Stock: {item['stock']})" for id, item in available_products.items()}
            
            with st.form("add_to_cart_form", clear_on_submit=True):
                selected_product_id = st.selectbox(
                    "Sélectionner un produit", 
                    options=list(product_options.keys()), 
                    format_func=lambda x: product_options[x], 
                    key="buy_select"
                )
                
                # Check selected product again inside the form for max qty
                if selected_product_id:
                    # Le stock affiché ici est le stock initial MOINS ce qui est déjà dans le panier
                    max_qty = st.session_state.products_db[selected_product_id]["stock"]
                    
                    quantity = st.number_input(
                        f"Quantité à ajouter (Max: {max_qty})", 
                        min_value=1, 
                        max_value=max_qty, 
                        value=1, 
                        step=1, 
                        key="buy_quantity"
                    )
                    
                    add_button = st.form_submit_button("➕ Ajouter au Panier", type="secondary")
                    
                    if add_button:
                        add_to_cart(selected_product_id, quantity)
                        st.rerun()
        else:
            st.error("Aucun produit disponible en stock pour l'achat.")

        st.markdown("---")
        st.subheader("📝 Panier Actuel")
        
        if st.session_state.cart:
            cart_items = []
            cart_total = 0
            
            # Reconstruire le panier pour l'affichage (avec les noms et les totaux)
            for product_id, quantity in st.session_state.cart.items():
                # On ne vérifie plus le stock ici, car il a déjà été déduit lors de l'ajout
                product_info = st.session_state.products_db[product_id]
                price = product_info['price']
                total_item = price * quantity
                cart_items.append({
                    "Produit": product_info['name'],
                    "Prix Unitaire": f"{price:,.0f} FCFA",
                    "Quantité": quantity,
                    "Total Article": f"{total_item:,.0f} FCFA"
                })
                cart_total += total_item
                
            df_cart = pd.DataFrame(cart_items)
            st.dataframe(df_cart, hide_index=True, use_container_width=True)
            
            st.markdown(f"**Total de la commande en cours :** **{cart_total:,.0f} FCFA**")
            
            col_checkout, col_clear = st.columns(2)
            with col_checkout:
                if st.button("✅ Finaliser la Commande", type="primary", use_container_width=True):
                    if finalize_purchase(current_username):
                        st.rerun()
            with col_clear:
                if st.button("❌ Vider le Panier", use_container_width=True):
                    # Restaurer le stock avant de vider le panier
                    for product_id, quantity in st.session_state.cart.items():
                        st.session_state.products_db[product_id]["stock"] += quantity
                    st.session_state.cart = {}
                    st.warning("Le panier a été vidé et le stock restauré.")
                    st.rerun()
        else:
            st.info("Votre panier est actuellement vide.")


        st.markdown("---")
        st.subheader("Mon historique d'achats")
        user_purchases_list = [
            {
                "ID Commande": cmd_id,
                "Date d'achat": details["date"],
                "Articles": ", ".join([f"{st.session_state.products_db.get(item['product_id'], {}).get('name', 'Inconnu')} x{item['quantity']}" for item in details["articles"]]),
                "Montant Total": details["total_commande"]
            }
            for cmd_id, details in st.session_state.purchases_db.items() if details["client"] == st.session_state.username
        ]
        if user_purchases_list:
            df_purchases = pd.DataFrame(user_purchases_list)
            st.dataframe(df_purchases, hide_index=True, use_container_width=True)
            
            st.markdown("**Télécharger mon historique d'achats :**")
            # Appel à la fonction mise à jour
            generate_download_buttons(df_purchases, f"Historique_Achats_{current_username}")
            
            st.markdown("---")
            st.subheader("Modifier ou supprimer un achat précédent")
            
            # Filtrer seulement les IDs de commandes de l'utilisateur actuel
            user_command_ids = [cmd_id for cmd_id, details in st.session_state.purchases_db.items() if details["client"] == st.session_state.username]
            
            if user_command_ids:
                # Créer une fonction de formatage pour l'affichage dans le selectbox
                def format_command_option(cmd_id):
                    details = st.session_state.purchases_db[cmd_id]
                    return f"{cmd_id} ({details['date']} - {details['total_commande']:,} FCFA)"
                
                command_to_modify_id = st.selectbox(
                    "Sélectionner l'ID de la Commande", 
                    options=user_command_ids,
                    format_func=format_command_option,
                    key="select_command_to_modify"
                )
                
                if command_to_modify_id:
                    command_details = st.session_state.purchases_db[command_to_modify_id]
                    
                    st.markdown(f"**Détails de la commande sélectionnée :**")
                    st.info(f"Date: {command_details['date']} | Montant: {command_details['total_commande']:,} FCFA")
                    # Afficher la liste des articles de la commande (même si modification simplifiée)
                    articles_summary = [f"{st.session_state.products_db.get(item['product_id'], {}).get('name', 'Inconnu')} x{item['quantity']} ({item['total_amount']:,} FCFA)" for item in command_details["articles"]]
                    st.markdown("Articles : " + " | ".join(articles_summary))


                    # --- Formulaire de Modification (simplifiée) ---
                    st.markdown("##### ✏️ Modifier la Commande (Date & Montant Total)")
                    with st.form(f"modify_command_form_{command_to_modify_id}"):
                        current_date = datetime.strptime(command_details['date'], "%Y-%m-%d").date()
                        modified_date = st.date_input("Nouvelle date de l'achat", value=current_date, key=f"mod_date_{command_to_modify_id}")
                        modified_total = st.number_input("Nouveau Montant Total de la Commande (FCFA)", value=float(command_details['total_commande']), min_value=1.0, key=f"mod_total_{command_to_modify_id}")

                        modify_confirmed = st.form_submit_button("Modifier l'Achat")
                        
                        if modify_confirmed:
                            st.session_state.purchases_db[command_to_modify_id]['date'] = modified_date.strftime("%Y-%m-%d")
                            st.session_state.purchases_db[command_to_modify_id]['total_commande'] = modified_total
                            st.success(f"La commande **{command_to_modify_id}** a été mise à jour.")
                            st.rerun()

                    # --- Formulaire de Suppression ---
                    st.markdown("##### 🚨 Supprimer la Commande")
                    with st.form(f"delete_command_form_{command_to_modify_id}"):
                        st.warning("Attention : La suppression restaurera le stock de **tous les produits** achetés dans cette commande.")
                        
                        delete_confirmed = st.form_submit_button("Supprimer Définitivement la Commande", type="primary")
                        
                        if delete_confirmed:
                            # 1. Restaurer le Stock (Fonctionne pour les commandes multi-articles)
                            for item in command_details["articles"]:
                                product_id = item['product_id']
                                quantity = item['quantity']
                                if product_id in st.session_state.products_db:
                                    st.session_state.products_db[product_id]['stock'] += quantity
                                    
                            # 2. Supprimer la Commande
                            del st.session_state.purchases_db[command_to_modify_id]
                            
                            st.success(f"La commande **{command_to_modify_id}** a été supprimée et le stock a été restauré.")
                            st.rerun()
            else:
                st.info("Vous n'avez aucun achat à modifier ou supprimer.")
        else:
            st.info("Vous n'avez pas encore effectué d'achats.")
            
    with tab4:
        show_charge_management()

    with tab5:
        show_user_settings_page()


# --- Point d'entrée de l'application ---
def main():
    if st.session_state.logged_in:
        if not check_subscription_status() and not st.session_state.is_admin:
            show_payment_page()
        elif st.session_state.is_admin and st.session_state.current_view == "admin":
            show_admin_dashboard()
        else:
            show_client_page()
        st.sidebar.button("Déconnexion", on_click=logout)
    else:
        show_login_page()

if __name__ == "__main__":
    main()