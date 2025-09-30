from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime

# =========================================================================
# 1. Définition de la Base Déclarative
# =========================================================================
class Base(DeclarativeBase):
    pass

# =========================================================================
# 2. Modèle Fournisseur (Supplier)
# =========================================================================
class Fournisseur(Base):
    __tablename__ = 'fournisseurs'

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, index=True, nullable=False)
    contact = Column(String)

    # Relation : Un fournisseur peut avoir plusieurs commandes
    commandes = relationship("Commande", back_populates="fournisseur")

# =========================================================================
# 3. Modèle Produit (Product)
# =========================================================================
class Produit(Base):
    __tablename__ = 'produits'

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, index=True, nullable=False)
    description = Column(String)
    # AJOUTÉ/CORRIGÉ : Pour correspondre à ProduitBase dans api.py
    reference = Column(String, unique=True, nullable=False)
    prix_unitaire = Column(Float, nullable=False)
    # RENOMMÉ : 'stock' devient 'stock_actuel' pour correspondre à ProduitBase
    stock_actuel = Column(Integer, default=0) 

    # Relation : Un produit peut apparaître dans plusieurs détails de commande
    details = relationship("DetailCommande", back_populates="produit")

# =========================================================================
# 4. Modèle Commande (Order)
# =========================================================================
class Commande(Base):
    __tablename__ = 'commandes'

    id = Column(Integer, primary_key=True, index=True)
    date_commande = Column(DateTime, default=datetime.utcnow)
    statut = Column(String, default="En attente") # Ex: En attente, Livrée, Annulée
    
    # AJOUTÉ : Pour correspondre à CommandeCreate dans api.py
    societe = Column(String)
    # AJOUTÉ : Pour stocker le coût total calculé dans api.py
    cout_total = Column(Float) 

    # Clé étrangère vers le fournisseur
    fournisseur_id = Column(Integer, ForeignKey('fournisseurs.id'))

    # Relations
    fournisseur = relationship("Fournisseur", back_populates="commandes")
    details = relationship("DetailCommande", back_populates="commande")

# =========================================================================
# 5. Modèle DetailCommande (Order Detail)
# =========================================================================
class DetailCommande(Base):
    __tablename__ = 'details_commandes'

    id = Column(Integer, primary_key=True, index=True)
    quantite = Column(Integer, nullable=False)
    prix_achat = Column(Float, nullable=False) # Prix au moment de l'achat

    # Clés étrangères
    commande_id = Column(Integer, ForeignKey('commandes.id'))
    produit_id = Column(Integer, ForeignKey('produits.id'))

    # Relations
    commande = relationship("Commande", back_populates="details")
    produit = relationship("Produit", back_populates="details")