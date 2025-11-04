from rq import Queue
from redis import Redis
import requests
from .models import Order, database
from .redis_config import cache_order
from .fonctions_utiles import TAUX_IMPOSITION
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis_conn = Redis.from_url(os.getenv('REDIS_URL'))
queue = Queue(connection=redis_conn)

def process_payment(order_id, credit_card):
    with database:
        order = Order.get_or_none(Order.id == order_id)
        if not order:
            logger.error(f"Commande avec l'ID {order_id} non trouvée")
            return

        try:
            # Supprimer les espaces du numéro de carte avant validation
            card_number = credit_card['number'].replace(" ", "")
            
            # Validation du numéro de carte
            if not isinstance(card_number, str) or not card_number.isdigit() or len(card_number) != 16:
                order.transaction_success = False
                order.transaction_error_code = "invalid-format"
                order.transaction_error_name = "Le numéro de carte doit être une chaîne de 16 chiffres"
                logger.error(f"Échec du paiement pour la commande {order_id} : Numéro de carte invalide")
                return

            # Mettre à jour le numéro de carte sans espaces
            credit_card['number'] = card_number

            time.sleep(5)

            taxe = TAUX_IMPOSITION.get(order.shipping_province, 0)
            total_price_tax = (order.total_price * (1 + taxe))
            order.total_price_tax = total_price_tax
            amount = total_price_tax + order.shipping_price

            logger.info(f"Tentative de paiement pour la commande {order_id}, montant: {amount}, carte: {credit_card['number']}")
            logger.info(f" les infos de la carte : {credit_card}")

            
            response = requests.post(
                'http://dimprojetu.uqac.ca/~jgnault/shops/pay/',
                json={'credit_card': credit_card, 'amount_charged': amount}
            )
            
            logger.info(f"Statut de la réponse du service de paiement : {response.status_code}")

            if response.status_code != 200:
                # Vérifier si la réponse est du JSON avant de parser
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    error_data = response.json().get('errors', {})
                    # Vérifier si l'erreur concerne la carte ou la commande
                    if 'credit_card' in error_data:
                        credit_card_error = error_data['credit_card']
                        error_code = credit_card_error.get('code', 'unknown-error')
                        error_name = credit_card_error.get('name', 'Erreur inconnue lors du paiement')
                    elif 'order' in error_data:
                        order_error = error_data['order']
                        error_code = order_error.get('code', 'unknown-error')
                        error_name = order_error.get('name', 'Erreur inconnue lors du paiement')
                    else:
                        error_code = 'unknown-error'
                        error_name = 'Erreur inconnue lors du paiement'
                else:
                    error_code = 'http-error'
                    error_name = f"Erreur HTTP {response.status_code}: {response.text[:100]}"
                order.transaction_success = False
                order.transaction_error_code = error_code
                order.transaction_error_name = error_name
                order.transaction_amount = amount
                logger.error(f"Échec du paiement pour la commande {order_id} : {error_code} - {error_name}")
            else:
                payment_data = response.json()
                logger.info(f"Réponse du service de paiement pour la commande {order_id} : {payment_data}")

                if 'credit_card' not in payment_data or 'transaction' not in payment_data:
                    raise ValueError("Réponse du service de paiement invalide : clés manquantes")

                order.credit_card_name = payment_data['credit_card'].get('name')
                order.credit_card_first_digits = payment_data['credit_card'].get('first_digits')
                order.credit_card_last_digits = payment_data['credit_card'].get('last_digits')
                order.credit_card_expiration_year = payment_data['credit_card'].get('expiration_year')
                order.credit_card_expiration_month = payment_data['credit_card'].get('expiration_month')
                order.transaction_id = payment_data['transaction'].get('id')
                order.transaction_success = payment_data['transaction'].get('success', False)
                order.transaction_amount = payment_data['transaction'].get('amount_charged')
                order.paid = payment_data['transaction'].get('success', False)

                # Toujours persister les erreurs, même si success est False
                error = payment_data['transaction'].get('error', {})
                if error or not order.transaction_success:
                    order.transaction_error_code = error.get('code', 'unknown-error')
                    order.transaction_error_name = error.get('name', 'Erreur inconnue lors du paiement')
                    logger.warning(f"La transaction pour la commande {order_id} a échoué : {order.transaction_error_code} - {order.transaction_error_name}")

                if order.paid:
                    products = [{"id": op.product.id, "quantity": op.quantity} for op in order.orderproducts]
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
                    cache_order(order_id, order_data)
                    logger.info(f"Commande {order_id} payée avec succès et mise en cache")

        except Exception as e:
            order.transaction_success = False
            order.transaction_error_code = "server-error"
            order.transaction_error_name = f"Erreur serveur: {str(e)}"
            order.transaction_amount = amount
            logger.error(f"Erreur lors du traitement du paiement pour la commande {order_id} : {str(e)}")

        finally:
            order.is_processing = False
            order.save()
            logger.info(f"Traitement du paiement terminé pour la commande {order_id}, is_processing=False, paid={order.paid}")