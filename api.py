# api_achats.py - API de Gestion des Achats (Prêt pour le Cloud)
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session, joinedload
from datetime import datetime
from typing import List, Optional

# --- NOTE IMPORTANTE : Dépendance aux Modèles ---
# Assurez-vous que votre fichier 'models_achats.py' est dans le même répertoire.
from models_achats import Base, Produit, Fournisseur, Commande, DetailCommande 


# ====================================================================
# 1. Configuration de la Base de Données (Cloud Ready)
# ====================================================================

# Utilise la variable d'environnement DATABASE_URL (pour PostgreSQL sur Render/Heroku)
# Si elle n'est pas définie (développement local), utilise SQLite.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./achats_local.db")

# Si on utilise SQLite, l'argument 'check_same_thread' est nécessaire.
# Sinon, on utilise un engine standard pour le Cloud (PostgreSQL, etc.)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

# Crée les tables si elles n'existent pas (utile pour la première exécution en ligne)
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dépendance pour obtenir la session de base de données
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ====================================================================
# 2. Modèles Pydantic (Schémas de Données pour l'API)
# ====================================================================

from pydantic import BaseModel

# Schémas de Base
class ProduitBase(BaseModel):
    nom: str
    reference: str
    prix_unitaire: float
    stock_actuel: int

class FournisseurBase(BaseModel):
    nom: str

class DetailCommandeBase(BaseModel):
    produit_id: int
    quantite: int
    prix_achat: float
    
# Schémas de Création (pour les données entrantes)
class CommandeCreate(BaseModel):
    fournisseur_id: int
    societe: str
    statut: str
    details: List[DetailCommandeBase]

# Schémas de Lecture (pour les données sortantes)
class ProduitInDB(ProduitBase):
    id: int
    class Config:
        orm_mode = True

class FournisseurInDB(FournisseurBase):
    id: int
    class Config:
        orm_mode = True

class DetailCommandeInDB(DetailCommandeBase):
    id: int
    class Config:
        orm_mode = True

class CommandeInDB(BaseModel):
    id: int
    fournisseur_id: int
    societe: str
    date_commande: datetime
    statut: str
    cout_total: float
    details: List[DetailCommandeInDB] = [] # Afficher les détails si nécessaires
    
    class Config:
        orm_mode = True


# ====================================================================
# 3. Initialisation de l'API et CORS
# ====================================================================

app = FastAPI(
    title="API Gestion des Achats",
    description="API RESTful pour la gestion des produits, fournisseurs et commandes d'achat.",
    version="1.0.0"
)

# CORS (Cross-Origin Resource Sharing) est essentiel pour que Streamlit (sur un autre domaine) puisse parler à cette API.
# Permet toutes les origines (pratique pour le développement/déploiement Streamlit)
origins = ["*"] 

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================================================================
# 4. Routes de l'API (CRUD et Logique Métier)
# ====================================================================

# --- Route de Bienvenue (Test de l'API) ---
@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API de Gestion des Achats. Santé du service : OK."}

# --- Routes Produits (Lecture et Création) ---
@app.post("/produits/", response_model=ProduitInDB)
def create_produit(produit: ProduitBase, db: Session = Depends(get_db)):
    db_produit = Produit(**produit.model_dump())
    db.add(db_produit)
    db.commit()
    db.refresh(db_produit)
    return db_produit

@app.get("/produits/", response_model=List[ProduitInDB])
def read_produits(db: Session = Depends(get_db)):
    return db.query(Produit).all()

# --- Routes Fournisseurs (Lecture et Création) ---
@app.post("/fournisseurs/", response_model=FournisseurInDB)
def create_fournisseur(fournisseur: FournisseurBase, db: Session = Depends(get_db)):
    db_fournisseur = Fournisseur(**fournisseur.model_dump())
    db.add(db_fournisseur)
    db.commit()
    db.refresh(db_fournisseur)
    return db_fournisseur

@app.get("/fournisseurs/", response_model=List[FournisseurInDB])
def read_fournisseurs(db: Session = Depends(get_db)):
    return db.query(Fournisseur).all()


# --- Route Commande (Logique Métier : Création et Stock) ---
@app.post("/commandes/", response_model=CommandeInDB)
def create_commande(commande: CommandeCreate, db: Session = Depends(get_db)):
    
    # 1. Calculer le coût total
    cout_total = 0.0
    for detail in commande.details:
        cout_total += detail.quantite * detail.prix_achat

    # 2. Créer l'objet Commande
    db_commande = Commande(
        fournisseur_id=commande.fournisseur_id,
        societe=commande.societe,
        statut=commande.statut,
        cout_total=cout_total
    )
    db.add(db_commande)
    db.commit()
    db.refresh(db_commande)

    # 3. Traiter les Détails de Commande et Mettre à Jour le Stock
    for detail in commande.details:
        
        # Créer le Détail de Commande
        db_detail = DetailCommande(
            commande_id=db_commande.id,
            produit_id=detail.produit_id,
            quantite=detail.quantite,
            prix_achat=detail.prix_achat
        )
        db.add(db_detail)

        # Mettre à jour le stock du produit (Augmentation pour un achat)
        produit = db.query(Produit).filter(Produit.id == detail.produit_id).first()
        if produit:
            produit.stock_actuel += detail.quantite
        
    db.commit()
    db.refresh(db_commande)
    return db_commande

@app.get("/commandes/", response_model=List[CommandeInDB])
def read_commandes(db: Session = Depends(get_db)):
    # Charge les détails pour que Pydantic puisse les sérialiser
    return db.query(Commande).options(joinedload(Commande.details)).all()


# --- Route Statistiques ---
@app.get("/statistiques/produits/")
def get_produit_stats(db: Session = Depends(get_db)):
    
    # 1. Joindre DetailCommande et Produit
    # 2. Grouper par produit (nom)
    # 3. Calculer la somme des quantités (quantite_vendue)
    # 4. Calculer la somme du coût total (prix_achat * quantite) (revenu_total)
    stats = db.query(
        Produit.nom.label('nom_produit'),
        func.sum(DetailCommande.quantite).label('quantite_vendue'),
        func.sum(DetailCommande.prix_achat * DetailCommande.quantite).label('revenu_total')
    ).join(DetailCommande, Produit.id == DetailCommande.produit_id
    ).group_by(Produit.nom
    ).all()
    
    # Convertir les résultats en une liste de dictionnaires
    results = [
        {
            "nom_produit": row.nom_produit,
            "quantite_vendue": float(row.quantite_vendue),
            "revenu_total": float(row.revenu_total)
        }
        for row in stats
    ]
    
    return results