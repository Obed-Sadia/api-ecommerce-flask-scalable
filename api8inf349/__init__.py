from datetime import datetime
from flask import Flask, jsonify, request, render_template
import redis
import requests
from .models import Product, Order, OrderProduct, database
from .redis_config import cache_order, get_cached_order
from .tasks import queue
from .fonctions_utiles import TAUX_IMPOSITION, calculate_shipping
from http import HTTPStatus
import os

app = Flask(__name__)

# Fonction pour nettoyer les chaînes de caractères
def clean_string(value):
    if isinstance(value, str):
        return value.replace('\0', '')  
    return value

# Initialisation des tables
def initialisation():
    database.connect()
    database.create_tables([Product, Order, OrderProduct], safe=True)
    if Product.select().count() == 0:
        response = requests.get('http://dimensweb.uqac.ca/~jgnault/shops/products/')
        if response.status_code == 200:
            products = response.json()['products']
            with database.atomic():
                for p in products:
                    Product.create(
                        id=p['id'],
                        name=clean_string(p['name']),           
                        description=clean_string(p['description']),  
                        price=p['price'],
                        in_stock=p.get('in_stock', True),
                        weight=p['weight'],
                        image=clean_string(p['image'])  
                    )
    database.close()

@app.cli.command("init-db")
def init_db():
    initialisation()
    print("Base de données initialisée avec succès.")

# Routes pour les pages HTML
@app.route('/')
def products_page():
    products = Product.select()
    return render_template('products.html')

@app.route('/order/new')
def create_order_page():
    return render_template('create_order.html')

@app.route('/view/order/<int:order_id>', methods=['GET'])
def view_order_page(order_id):
    return render_template('order.html', order_id=order_id)

@app.route('/orders/completed')
def completed_orders_page():
    return render_template('completed_orders.html')

@app.route('/orders/pending')
def pending_orders_page():
    return render_template('pending_orders.html')

# Récupération les produits
@app.route('/api/products', methods=['GET'])
def get_products():
    products = Product.select()
    return jsonify({
        'products': [
            {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price': p.price,
                'in_stock': p.in_stock,
                'weight': p.weight,
                'image': p.image
            } for p in products
        ]
    })

# Création d'une commande (POST /order)
@app.route('/order', methods=['POST'])
def create_order():
    try:
        data = request.get_json()
        if not data or 'products' not in data:
            return jsonify({
                'errors': {
                    'products': {
                        'code': 'missing-fields',
                        'name': 'La création d’une commande nécessite au moins un produit'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        products = data['products']
        if not isinstance(products, list) or not products:
            return jsonify({
                'errors': {
                    'products': {
                        'code': 'invalid-format',
                        'name': 'Les produits doivent être une liste non vide'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        total_price = 0
        total_weight = 0

        for product_data in products:
            if 'id' not in product_data or 'quantity' not in product_data:
                return jsonify({
                    'errors': {
                        'product': {
                            'code': 'missing-fields',
                            'name': 'Chaque produit doit avoir un id et une quantité'
                        }
                    }
                }), HTTPStatus.UNPROCESSABLE_ENTITY

            product_id = product_data['id']
            quantity = product_data['quantity']

            if not isinstance(quantity, int) or quantity < 1:
                return jsonify({
                    'errors': {
                        'product': {
                            'code': 'invalid-quantity',
                            'name': 'La quantité doit être un entier supérieur ou égal à 1'
                        }
                    }
                }), HTTPStatus.UNPROCESSABLE_ENTITY

            product = Product.get_or_none(Product.id == product_id)
            if not product or not product.in_stock:
                return jsonify({
                    'errors': {
                        'product': {
                            'code': 'out-of-inventory',
                            'name': f'Le produit {product_id} n’est pas en inventaire'
                        }
                    }
                }), HTTPStatus.UNPROCESSABLE_ENTITY

            total_price += product.price * quantity
            total_weight += product.weight * quantity

        shipping_price = calculate_shipping(total_weight)

        with database.atomic():
            order = Order.create(
                total_price=total_price,
                shipping_price=shipping_price
            )

            for product_data in products:
                product = Product.get(Product.id == product_data['id'])
                OrderProduct.create(
                    order=order,
                    product=product,
                    quantity=product_data['quantity']
                )

        return jsonify({
            'order': {
                'id': order.id,
                'total_price': order.total_price,
                'shipping_price': order.shipping_price,
                'products': products
            }
        }), HTTPStatus.CREATED

    except Exception as e:
        return jsonify({
            'error': {
                'code': 'server-error',
                'message': f'Erreur lors de la création de la commande: {str(e)}'
            }
        }), HTTPStatus.INTERNAL_SERVER_ERROR

# Récupération d'une commande (GET /order/<int:order_id>)
@app.route('/order/<int:order_id>', methods=['GET'])
def get_order(order_id):
    try:
        # Vérifier le cache Redis en premier
        cached_order = get_cached_order(order_id)
        if cached_order and cached_order.get('paid'):
            return jsonify({"order": cached_order}), HTTPStatus.OK

        # Récupérer la commande depuis la base de données une seule fois
        order = Order.get_or_none(Order.id == order_id)
        if not order:
            return jsonify({
                'error': {
                    'code': 'not-found',
                    'message': f'Commande avec l\'ID {order_id} non trouvée'
                }
            }), HTTPStatus.NOT_FOUND

        # Vérifier si la commande est en cours de traitement
        if order.is_processing:
            return '', HTTPStatus.ACCEPTED

        # Récupérer les produits associés à la commande avec une gestion explicite des erreurs
        try:
            products = [{"id": op.product.id, "quantity": op.quantity} for op in order.orderproducts]
        except Exception as e:
            return jsonify({
                'error': {
                    'code': 'invalid-data',
                    'message': f'Erreur lors de la récupération des produits de la commande: {str(e)}'
                }
            }), HTTPStatus.INTERNAL_SERVER_ERROR

        # Construire les données de la commande
        order_data = {
            "id": order.id,
            "total_price": float(order.total_price) if order.total_price is not None else 0.0,
            "total_price_tax": float(order.total_price_tax) if order.total_price_tax is not None else None,
            "shipping_price": float(order.shipping_price) if order.shipping_price is not None else None,
            "email": order.email,
            "shipping_information": None if not order.shipping_country else {
                "country": order.shipping_country,
                "address": order.shipping_address,
                "postal_code": order.shipping_postal_code,
                "city": order.shipping_city,
                "province": order.shipping_province
            },
            "paid": bool(order.paid),
            "products": products,
            "credit_card": {} if not order.credit_card_name else {
                "name": order.credit_card_name,
                "first_digits": order.credit_card_first_digits,
                "last_digits": order.credit_card_last_digits,
                "expiration_year": order.credit_card_expiration_year,
                "expiration_month": order.credit_card_expiration_month
            },
            "transaction": {} if not order.transaction_id else {
                "id": order.transaction_id,
                "success": bool(order.transaction_success),
                "error": {
                    "code": order.transaction_error_code,
                    "name": order.transaction_error_name
                } if order.transaction_error_code else {},
                "amount_charged": float(order.transaction_amount) if order.transaction_amount is not None else None
            },
            "amount_charged": float(order.transaction_amount) if order.transaction_amount is not None else None
        }

        # Mettre en cache si la commande est payée
        if order.paid:
            try:
                cache_order(order.id, order_data)
            except Exception as e:
                print(f"Erreur lors de la mise en cache de la commande {order_id}: {str(e)}")

        return jsonify({"order": order_data}), HTTPStatus.OK

    except Exception as e:
        return jsonify({
            'error': {
                'code': 'server-error',
                'message': f'Erreur lors de la récupération de la commande: {str(e)}'
            }
        }), HTTPStatus.INTERNAL_SERVER_ERROR
        
# Mise à jour des informations de livraison et paiement (PUT /order/<int:order_id>)
@app.route('/order/<int:order_id>', methods=['PUT'])
def update_order(order_id):
    order = Order.get_or_none(Order.id == order_id)
    if not order:
        return '', HTTPStatus.NOT_FOUND

    data = request.get_json()

    # Mise à jour des informations de livraison
    if 'shipping_information' in data and 'email' in data:
        shipping = data['shipping_information']
        required_fields = ['country', 'address', 'postal_code', 'city', 'province']
        if not all(field in shipping for field in required_fields):
            return jsonify({
                'errors': {
                    'order': {
                        'code': 'missing-fields',
                        'name': 'Il manque un ou plusieurs champs qui sont obligatoires'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        order.email = data['email']
        order.shipping_country = shipping['country']
        order.shipping_address = shipping['address']
        order.shipping_postal_code = shipping['postal_code']
        order.shipping_city = shipping['city']
        order.shipping_province = shipping['province']
        taxe = TAUX_IMPOSITION.get(shipping['province'], 0)
        order.total_price_tax = (order.total_price * (1 + taxe))
        order.save()
        return get_order(order_id)

    # Paiement de la commande
    elif 'credit_card' in data:
        required_fields = ['name', 'number', 'expiration_year', 'expiration_month', 'cvv']
        if not all(field in data['credit_card'] for field in required_fields):
            return jsonify({
                'errors': {
                    'credit_card': {
                        'code': 'missing-fields',
                        'name': 'Il manque un ou plusieurs champs de la carte de crédit'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        credit_card = data['credit_card']

        # Validation des champs
        if not isinstance(credit_card['expiration_year'], int) or not isinstance(credit_card['expiration_month'], int):
            return jsonify({
                'errors': {
                    'credit_card': {
                        'code': 'invalid-format',
                        'name': 'Les champs expiration_year et expiration_month doivent être des entiers'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        if not isinstance(credit_card['cvv'], str) or not credit_card['cvv'].isdigit() or len(credit_card['cvv']) != 3:
            return jsonify({
                'errors': {
                    'credit_card': {
                        'code': 'invalid-format',
                        'name': 'Le champ cvv doit être une chaîne de 3 chiffres'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY
            
        # Ajout de la validation pour le numéro de carte
        if not isinstance(credit_card['number'], str) or not credit_card['number'].isdigit() or len(credit_card['number']) != 16:
            return jsonify({
                'errors': {
                    'credit_card': {
                        'code': 'invalid-format',
                        'name': 'Le numéro de carte doit être une chaîne de 16 chiffres'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY
            
        # Vérification de la date d'expiration
        current_year = datetime.now().year
        current_month = datetime.now().month

        
        if (credit_card['expiration_year'] < current_year) or \
            (credit_card['expiration_year'] == current_year and credit_card['expiration_month'] < current_month) or \
            (credit_card['expiration_month'] < 1 or credit_card['expiration_month'] > 12):
             return jsonify({
                 'errors': {
                     'credit_card': {
                         'code': 'card-expired',
                         'name': 'La carte de crédit est expirée ou la date est invalide'
                     }
                 }
             }), HTTPStatus.UNPROCESSABLE_ENTITY

        if not order.email or not order.shipping_country:
            return jsonify({
                'errors': {
                    'order': {
                        'code': 'missing-fields',
                        'name': 'Les informations du client sont nécessaires avant d’appliquer une carte de crédit'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        if order.paid:
            return jsonify({
                'errors': {
                    'order': {
                        'code': 'already-paid',
                        'name': 'La commande a déjà été payée'
                    }
                }
            }), HTTPStatus.CONFLICT

        # Vérifier si la commande est en cours de traitement
        if order.is_processing:
            return jsonify({
                'errors': {
                    'order': {
                        'code': 'being-processed',
                        'name': 'La commande est en cours de traitement'
                    }
                }
            }), HTTPStatus.CONFLICT

        # Marquer la commande comme étant en cours de traitement
        order.is_processing = True
        order.save()

        # Enfiler la tâche de paiement dans RQ
        queue.enqueue('api8inf349.tasks.process_payment', order_id, credit_card)

        # Renvoyer un statut 202 Accepted sans corps de réponse
        return '', HTTPStatus.ACCEPTED

    # Si ni shipping_information ni credit_card ne sont fournis
    return jsonify({
        'errors': {
            'order': {
                'code': 'missing-fields',
                'name': 'Il manque des champs obligatoires (shipping_information ou credit_card)'
            }
        }
    }), HTTPStatus.UNPROCESSABLE_ENTITY
    
    
@app.cli.command("worker")
def run_worker():
    from rq import Worker
    redis_conn = redis.Redis.from_url(os.getenv('REDIS_URL'))
    worker = Worker([queue], connection=redis_conn)
    worker.work()