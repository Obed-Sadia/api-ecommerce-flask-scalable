let cart = JSON.parse(localStorage.getItem('cart')) || [];

async function fetchProducts() {
    try {
        const response = await fetch('/api/products');
        if (!response.ok) throw new Error('Erreur lors de la récupération des produits');
        const data = await response.json();
        const products = data.products;
        const productsList = document.getElementById('products-list');
        if (productsList) {
            productsList.innerHTML = '';
            products.forEach(product => {
                const productCard = document.createElement('div');
                productCard.className = 'product-card';
                productCard.innerHTML = `
                    <img src="http://dimensweb.uqac.ca/~jgnault/shops/${product.image}" alt="${product.name}" onerror="this.style.display='none'">
                    <h2>${product.name}</h2>
                    <p>${product.description}</p>
                    <p>Prix: ${product.price} $</p>
                    <p>Poids: ${product.weight} kg</p>
                    <p>En stock: ${product.in_stock ? 'Oui' : 'Non'}</p>
                    <form class="add-to-cart-form">
                        <input type="hidden" name="product_id" value="${product.id}">
                        <label>Quantité: <input type="number" name="quantity" value="1" min="1" ${!product.in_stock ? 'disabled' : ''}></label>
                        <button type="button" onclick="addToCart(${product.id}, this.closest('form'))" ${!product.in_stock ? 'disabled' : ''}>Ajouter au panier</button>
                    </form>
                `;
                productsList.appendChild(productCard);
            });
        }
        updateCartDisplay();
    } catch (error) {
        console.error('Erreur:', error);
        const productsList = document.getElementById('products-list');
        if (productsList) productsList.innerHTML = '<p>Erreur lors du chargement des produits.</p>';
    }
}

async function loadProducts() {
    try {
        const response = await fetch('/api/products');
        if (!response.ok) throw new Error('Erreur lors de la récupération des produits');
        const data = await response.json();
        const products = data.products;
        document.querySelectorAll('select[name^="products"]').forEach(select => {
            select.innerHTML = '<option value="" disabled selected>Sélectionnez un produit</option>';
            products.forEach(product => {
                if (product.in_stock) {
                    const option = document.createElement('option');
                    option.value = product.id;
                    option.textContent = `${product.name} - ${product.price} $`;
                    select.appendChild(option);
                }
            });
        });
    } catch (error) {
        console.error('Erreur:', error);
        const errorDiv = document.getElementById('form-error');
        if (errorDiv) {
            errorDiv.textContent = 'Erreur lors du chargement des produits.';
            errorDiv.style.display = 'block';
        }
    }
}

function addProductField() {
    const container = document.getElementById('products-container');
    if (!container) return;
    const productIndex = container.querySelectorAll('.product-field').length;
    const newDiv = document.createElement('div');
    newDiv.className = 'product-field';
    newDiv.setAttribute('data-index', productIndex);
    newDiv.innerHTML = `
        <label for="product_${productIndex}_id">Produit :</label>
        <select name="products[${productIndex}][id]" id="product_${productIndex}_id" required>
            <option value="" disabled selected>Sélectionnez un produit</option>
        </select>
        <label for="product_${productIndex}_quantity">Quantité :</label>
        <input type="number" name="products[${productIndex}][quantity]" id="product_${productIndex}_quantity" min="1" value="1" required>
        <button type="button" onclick="this.parentElement.remove()">Supprimer</button>
    `;
    container.appendChild(newDiv);
    loadProducts();
}

async function createOrderFormSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const products = [];
    const productFields = form.querySelectorAll('.product-field');
    let hasError = false;

    productFields.forEach(field => {
        const index = field.dataset.index;
        const productId = form.querySelector(`#product_${index}_id`).value;
        const quantity = parseInt(form.querySelector(`#product_${index}_quantity`).value);
        if (!productId || quantity < 1) {
            hasError = true;
            const errorDiv = document.getElementById('form-error');
            if (errorDiv) {
                errorDiv.textContent = 'Veuillez sélectionner un produit et une quantité valide.';
                errorDiv.style.display = 'block';
            }
            return;
        }
        products.push({ id: parseInt(productId), quantity });
    });

    if (hasError) return;

    try {
        const response = await fetch('/order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ products })
        });
        const result = await response.json();
        const errorDiv = document.getElementById('form-error');
        if (response.ok) {
            window.location.href = `/view/order/${result.order.id}`; 
        } else {
            if (errorDiv) {
                errorDiv.textContent = 'Erreur : ' + JSON.stringify(result.errors);
                errorDiv.style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Erreur:', error);
        const errorDiv = document.getElementById('form-error');
        if (errorDiv) {
            errorDiv.textContent = 'Erreur lors de la création de la commande.';
            errorDiv.style.display = 'block';
        }
    }
}

function addToCart(productId, form) {
    const quantityInput = form.querySelector('input[name="quantity"]');
    const quantity = parseInt(quantityInput.value);
    if (quantity < 1) {
        alert('La quantité doit être au moins 1.');
        return;
    }
    cart.push({ id: productId, quantity });
    localStorage.setItem('cart', JSON.stringify(cart));
    alert(`Produit ${productId} (x${quantity}) ajouté au panier !`);
    updateCartDisplay();
}

function updateCartDisplay() {
    const cartCount = document.getElementById('cart-count');
    const cartList = document.getElementById('cart-list');
    if (cartCount) {
        cartCount.textContent = cart.reduce((total, item) => total + item.quantity, 0);
    }
    if (cartList) {
        if (cart.length === 0) {
            cartList.innerHTML = '<p>Votre panier est vide.</p>';
        } else {
            cartList.innerHTML = '';
            cart.forEach((item, index) => {
                const cartItem = document.createElement('div');
                cartItem.className = 'cart-item';
                cartItem.innerHTML = `
                    <span>Produit ID ${item.id} (x${item.quantity})</span>
                    <button onclick="removeFromCart(${index})">Supprimer</button>
                `;
                cartList.appendChild(cartItem);
            });
        }
    }
}

function toggleCart() {
    const cartItems = document.getElementById('cart-items');
    if (cartItems) {
        cartItems.style.display = cartItems.style.display === 'block' ? 'none' : 'block';
        updateCartDisplay();
    }
}

function removeFromCart(index) {
    cart.splice(index, 1);
    localStorage.setItem('cart', JSON.stringify(cart));
    updateCartDisplay();
}

function clearCart() {
    cart = [];
    localStorage.setItem('cart', JSON.stringify(cart));
    updateCartDisplay();
}

async function submitCart() {
    if (cart.length === 0) {
        alert('Le panier est vide !');
        return;
    }
    try {
        const response = await fetch('/order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ products: cart })
        });
        const data = await response.json();
        if (response.ok) {
            window.location.href = `/view/order/${data.order.id}`; 
            cart = [];
            localStorage.setItem('cart', JSON.stringify(cart));
            updateCartDisplay();
        } else {
            alert('Erreur: ' + JSON.stringify(data.errors));
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur lors de la création de la commande.');
    }
}

async function fetchOrder(orderId) {
    try {
        console.log(`Récupération de la commande #${orderId}`);
        const url = `/order/${orderId}`;
        console.log(`URL de la requête: ${url}`);
        const response = await fetch(url, {
            headers: {
                'Accept': 'application/json'
            }
        });
        const errorDiv = document.getElementById('order-error');

        console.log(`Statut HTTP: ${response.status}`);

        if (response.status === 202) {
            document.getElementById('order-details').innerHTML = '<p>Commande en cours de traitement...</p>';
            setTimeout(() => fetchOrder(orderId), 1000);
            return;
        }

        
        const contentType = response.headers.get('Content-Type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Réponse inattendue : le serveur n\'a pas renvoyé du JSON');
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error?.message || 'Erreur serveur inconnue');
        }

        const order = data.order;
        console.log('Données de la commande:', order);

        const detailsDiv = document.getElementById('order-details');
        detailsDiv.innerHTML = `
            <p><strong>ID :</strong> ${order.id}</p>
            <p><strong>Prix total :</strong> ${order.total_price_tax || order.total_price} $</p>
            <p><strong>Frais de livraison :</strong> ${order.shipping_price || 'N/A'} $</p>
            <p><strong>Payé :</strong> ${order.paid ? 'Oui' : 'Non'}</p>
            <p><strong>Produits :</strong> ${order.products.map(p => `ID ${p.id} (x${p.quantity})`).join(', ')}</p>
            ${order.email ? `<p><strong>Email :</strong> ${order.email}</p>` : ''}
            ${order.shipping_information ? `
                <p><strong>Livraison :</strong> ${order.shipping_information.address}, ${order.shipping_information.city}, 
                ${order.shipping_information.province}, ${order.shipping_information.postal_code}, ${order.shipping_information.country}</p>
            ` : ''}
            ${order.transaction && order.transaction.id ? `
                <p><strong>Transaction :</strong> ${order.transaction.id} (${order.transaction.success ? 'Réussie' : 'Échouée'})</p>
                ${order.transaction.error && order.transaction.error.code ? `<p><strong>Erreur :</strong> ${order.transaction.error.name} (${order.transaction.error.code})</p>` : ''}
            ` : ''}
        `;

        const shouldShowShipping = (!order.email || !order.shipping_information) && !order.paid;
        const shouldShowPayment = order.email && order.shipping_information && !order.paid;
        console.log('Visibilité des sections - shipping:', shouldShowShipping, 'payment:', shouldShowPayment);

        const shippingSection = document.getElementById('shipping-section');
        const paymentSection = document.getElementById('payment-section');
        if (shippingSection) {
            shippingSection.style.display = shouldShowShipping ? 'block' : 'none';
        } else {
            console.error('Élément #shipping-section non trouvé dans le DOM');
        }
        if (paymentSection) {
            paymentSection.style.display = shouldShowPayment ? 'block' : 'none';
        } else {
            console.error('Élément #payment-section non trouvé dans le DOM');
        }

        if (errorDiv) errorDiv.style.display = 'none';
    } catch (error) {
        console.error('Erreur lors de fetchOrder:', error);
        const detailsDiv = document.getElementById('order-details');
        const errorDiv = document.getElementById('order-error');
        if (detailsDiv) detailsDiv.innerHTML = '<p>Erreur lors du chargement de la commande.</p>';
        if (errorDiv) {
            errorDiv.textContent = error.message;
            errorDiv.style.display = 'block';
        }
    }
}

async function updateShipping(e) {
    e.preventDefault();
    const form = e.target;
    const email = form.querySelector('input[name="email"]').value;
    const shipping_information = {
        country: form.querySelector('input[name="shipping_information[country]"]').value,
        address: form.querySelector('input[name="shipping_information[address]"]').value,
        postal_code: form.querySelector('input[name="shipping_information[postal_code]"]').value,
        city: form.querySelector('input[name="shipping_information[city]"]').value,
        province: form.querySelector('select[name="shipping_information[province]"]').value
    };
    const errorDiv = document.getElementById('order-error');

    try {
        const response = await fetch(`/order/${window.orderId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, shipping_information })
        });
        if (response.ok) {
            fetchOrder(window.orderId);
            if (errorDiv) errorDiv.style.display = 'none';
        } else {
            const error = await response.json();
            if (errorDiv) {
                errorDiv.innerHTML = `<p>Erreur: ${JSON.stringify(error.errors)}</p>`;
                errorDiv.style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Erreur:', error);
        if (errorDiv) {
            errorDiv.textContent = 'Erreur lors de la mise à jour des informations de livraison.';
            errorDiv.style.display = 'block';
        }
    }
}

async function processPayment(e) {
    e.preventDefault();
    const form = e.target;

    let cardNumber;
    const selectElement = form.querySelector('select[name="credit_card[number]"]');
    const customInputElement = form.querySelector('input[name="credit_card[number]"]');

    console.log('selectElement:', selectElement);
    console.log('customInputElement:', customInputElement);

    if (selectElement) {
        console.log('Option prédéfinie sélectionnée, valeur:', selectElement.value);
        cardNumber = selectElement.value;
    } else if (customInputElement) {
        console.log('Option custom sélectionnée, valeur:', customInputElement.value);
        cardNumber = customInputElement.value;
    } else {
        console.log('Aucun numéro de carte trouvé');
        const errorDiv = document.getElementById('order-error');
        if (errorDiv) {
            errorDiv.textContent = 'Erreur : Numéro de carte manquant.';
            errorDiv.style.display = 'block';
        }
        return;
    }

    const credit_card = {
        name: form.querySelector('input[name="credit_card[name]"]').value,
        number: cardNumber,
        expiration_year: parseInt(form.querySelector('input[name="credit_card[expiration_year]"]').value),
        expiration_month: parseInt(form.querySelector('input[name="credit_card[expiration_month]"]').value),
        cvv: form.querySelector('input[name="credit_card[cvv]"]').value
    };

    console.log('Objet credit_card envoyé:', credit_card);

    const errorDiv = document.getElementById('order-error');

    try {
        const response = await fetch(`/order/${window.orderId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ credit_card })
        });
        if (response.status === 202) {
            if (errorDiv) {
                errorDiv.textContent = 'Paiement en cours de traitement...';
                errorDiv.style.display = 'block';
            }
            fetchOrder(window.orderId);
        } else if (response.ok) {
            fetchOrder(window.orderId);
            if (errorDiv) errorDiv.style.display = 'none';
        } else {
            const error = await response.json();
            if (errorDiv) {
                errorDiv.innerHTML = `<p>Erreur: ${JSON.stringify(error.errors)}</p>`;
                errorDiv.style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Erreur:', error);
        if (errorDiv) {
            errorDiv.textContent = 'Erreur lors du traitement du paiement.';
            errorDiv.style.display = 'block';
        }
    }
}

// Initialiser les écouteurs d'événements
document.addEventListener('DOMContentLoaded', () => {
    const createOrderForm = document.getElementById('create-order-form');
    if (createOrderForm) createOrderForm.addEventListener('submit', createOrderFormSubmit);
    const productsList = document.getElementById('products-list');
    if (productsList) fetchProducts();
    const productsContainer = document.getElementById('products-container');
    if (productsContainer) loadProducts();
    const orderDetails = document.getElementById('order-details');
    if (orderDetails && window.orderId) {
        console.log('Appel de fetchOrder avec orderId:', window.orderId);
        fetchOrder(window.orderId);
    }
    const shippingForm = document.getElementById('shipping-form');
    if (shippingForm) shippingForm.addEventListener('submit', updateShipping);
    const paymentForm = document.getElementById('payment-form');
    if (paymentForm) paymentForm.addEventListener('submit', processPayment);
});