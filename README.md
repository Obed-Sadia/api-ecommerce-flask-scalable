# API E-commerce Scalable (Flask, Postgres, Redis, RQ)

**Statut du projet :** Terminé 

> Un projet académique démontrant l'évolution d'une simple API de paiement (Flask/SQLite) en un système web robuste, conteneurisé et asynchrone (Postgres/Redis/Docker/RQ).

Ce projet a été réalisé en deux phases, simulant le cycle de vie réel d'une application web : d'un produit minimum viable (MVP) à une architecture scalable prête pour la production.

---

### 📺 Démonstration Visuelle

Ce projet n'étant pas déployé, voici une démonstration de ses concepts clés.

**(Nom : architecture-evolution.png, Type : Schéma PNG)**
> **[Action] :** [alt text](image.jpg)
> * **Partie 1 :** Client -> API Flask (avec SQLite) -> API externes.
> * **Partie 2 :** Client -> API Flask -> **Worker RQ** -> API de paiement.
>     (La Flask API et le Worker lisent/écrivent dans **Postgres** et **Redis**).


---

### 📋 Table des Matières

1.  [Problématique & Évolution](#problématique--évolution)
2.  [Fonctionnalités Clés](#fonctionnalités-clés)
3.  [Stack Technique](#stack-technique)
4.  [Installation & Lancement (Docker)](#installation--lancement-docker)
5.  [Structure de l'API](#structure-de-lapi)

---

### 🎯 Problématique & Évolution

#### Partie 1 : Le MVP (Produit Minimum Viable)

* **Objectif :** Créer une API RESTful (avec **Flask** et **Peewee**) capable de gérer un flux de commande simple :
    1.  Lister les produits (chargés depuis une API externe au démarrage).
    2.  Créer une commande (avec un seul produit).
    3.  Ajouter les informations client (adresse, email).
    4.  Calculer les taxes (par province) et les frais de port (par poids).
    5.  Appeler une API de paiement externe pour finaliser la transaction.
* **Base de données :** **SQLite** pour sa simplicité d'initialisation.

#### Partie 2 : La Montée en Charge (Scaling & Résilience)

* **Objectif :** Transformer le MVP en une application robuste prête pour la production.
* **Évolutions techniques :**
    1.  **Migration de Base de Données :** Remplacement de SQLite par **PostgreSQL** pour gérer la concurrence et la fiabilité.
    2.  **Conteneurisation :** Création d'un `Dockerfile` pour l'application Flask et d'un `docker-compose.yml` pour orchestrer l'API, Postgres et Redis.
    3.  **Traitement Asynchrone :** Extraction du processus de paiement (l'appel à l'API externe) de la requête web principale. Le paiement est maintenant géré en arrière-plan par un *worker* **Redis Queue (RQ)** pour une réponse client instantanée (HTTP 202).
    4.  **Caching & Résilience :** Ajout de **Redis** pour mettre en cache les commandes payées. Le `GET /order/<id>` vérifie d'abord le cache Redis, rendant l'application plus rapide et résiliente aux pannes de base de données.
    5.  **Mise à jour de l'API :** L'API `POST /order` a été améliorée pour accepter plusieurs produits dans une même commande.

### ✨ Fonctionnalités Clés

* **API RESTful complète** avec gestion d'état (commande en attente, en paiement, payée, échouée).
* **Intégration d'API tierces** (Service de produits et service de paiement).
* **Traitement de paiement asynchrone** (non bloquant) via **Redis Queue (RQ)**.
* **Mise en cache** des commandes payées dans **Redis** pour la résilience et la performance.
* **Environnement de développement et production** entièrement conteneurisé avec **Docker** et **Docker-Compose**.
* **Gestion de la configuration** via des variables d'environnement (`DB_HOST`, `REDIS_URL`, etc.).

### 🛠️ Stack Technique

| Domaine | Technologie |
| :--- | :--- |
| **Backend** | Python 3.6+, **Flask** |
| **Base de Données** | **PostgreSQL** (primaire), SQLite (initiale) |
| **File d'attente / Cache** | **Redis** |
| **Gestionnaire de Tâches** | **RQ (Redis Queue)** |
| **ORM** | **Peewee** (ou SQLAlchemy, selon votre choix) |
| **DevOps** | **Docker**, **Docker Compose** |
| **Tests** | pytest, pytest-flask |

### 🚀 Installation & Lancement (Docker)

Ce projet est conçu pour être lancé avec Docker Compose.

**Prérequis :**
* [Docker](https://www.docker.com/get-started)
* [Docker Compose](https://docs.docker.com/compose/install/)

**Instructions :**

1.  Configuration des variables d’environnement
    Ces variables définissent les paramètres de connexion à Flask, Redis, et PostgreSQL.

    Dans PowerShell, exécutez les commandes suivantes :

    ```powershell
    $env:FLASK_DEBUG="True"
    $env:FLASK_APP="api8inf349"
    $env:REDIS_URL="redis://localhost"
    $env:DB_HOST="localhost"
    $env:DB_USER="user"
    $env:DB_PASSWORD="pass"
    $env:DB_PORT="5432"
    $env:DB_NAME="api8inf349"
    ```

    Si vous utilisez un autre terminal (par exemple, Bash), vous pouvez définir les variables comme suit :

    ```bash
    export FLASK_DEBUG=True
    export FLASK_APP=api8inf349
    export REDIS_URL=redis://localhost
    export DB_HOST=localhost
    export DB_USER=user
    export DB_PASSWORD=pass
    export DB_PORT=5432
    export DB_NAME=api8inf349
    ```

2.  Construire l’image Docker

    ```bash
    docker build -t api8inf349 .
    ```

3.  Lancez l'ensemble de la pile de services (API, DB, Cache, Worker) :
    ```bash
    docker-compose up -d
    ```

4.  Initialiser la base de données

    Initialisez la base de données PostgreSQL en créant les tables nécessaires pour l’application :

    ```bash
    docker run -e FLASK_DEBUG=True \
              -e FLASK_APP=api8inf349 \
              -e REDIS_URL=redis://host.docker.internal \
              -e DB_HOST=host.docker.internal \
              -e DB_USER=user \
              -e DB_PASSWORD=pass \
              -e DB_PORT=5432 \
              -e DB_NAME=api8inf349 \
              api8inf349 flask init-db
    ```
5.  Lancer l’application Flask
    Démarrez le serveur Flask pour gérer les requêtes HTTP :

    ```bash
    docker run -p 5000:5000 \
              -e REDIS_URL=redis://host.docker.internal \
              -e DB_HOST=host.docker.internal \
              -e DB_USER=user \
              -e DB_PASSWORD=pass \
              -e DB_PORT=5432 \
              -e DB_NAME=api8inf349 \
              api8inf349
    ```
5. Lancer le worker RQ
    Lancez le worker RQ pour traiter les paiements de manière asynchrone :

    ```bash
    docker run -e FLASK_DEBUG=True \
              -e FLASK_APP=api8inf349 \
              -e REDIS_URL=redis://host.docker.internal \
              -e DB_HOST=host.docker.internal \
              -e DB_USER=user \
              -e DB_PASSWORD=pass \
              -e DB_PORT=5432 \
              -e DB_NAME=api8inf349 \
              api8inf349 flask worker
    ```

Ce worker consomme les tâches de la file d’attente Redis et traite les paiements en arrière-plan.

L'application est maintenant accessible sur `http://localhost:5000` (ou le port que vous avez défini).

