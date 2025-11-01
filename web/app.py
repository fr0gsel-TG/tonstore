# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import sqlite3
import json
from datetime import datetime
import os
from coinbase_commerce.client import Client
from coinbase_commerce.webhook import Webhook

app = Flask(__name__)
# It's better to load the secret key from an environment variable for security
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key') 

# --- Coinbase Commerce Setup ---
# Load API key from environment variable
COINBASE_API_KEY = os.environ.get('COINBASE_COMMERCE_API_KEY')
# Load webhook secret from environment variable
COINBASE_WEBHOOK_SECRET = os.environ.get('COINBASE_WEBHOOK_SECRET')

# Initialize the client if the API key is available
if COINBASE_API_KEY:
    client = Client(api_key=COINBASE_API_KEY)
else:
    client = None
    print("Warning: COINBASE_COMMERCE_API_KEY environment variable not set. Crypto payments will be disabled.")
# --- End of Coinbase Setup ---


# Absolute path to the database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'iphones_catalog.db')


class iPhoneCatalog:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
    
    def get_all_products(self, category=None, sort_by='price_desc', search=None):
        """Получение всех товаров с фильтрацией"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Базовый запрос
        query = '''
            SELECT ic.*, 
                   GROUP_CONCAT(DISTINCT icc.color_name) as all_colors,
                   GROUP_CONCAT(DISTINCT icm.memory_size) as all_memory
            FROM iphones_catalog ic
            LEFT JOIN iphone_catalog_colors icc ON ic.product_id = icc.product_id
            LEFT JOIN iphone_catalog_memory icm ON ic.product_id = icm.product_id
        '''
        
        conditions = []
        params = []
        
        # Фильтр по категории
        if category and category != 'all':
            conditions.append("ic.category = ?")
            params.append(category)
        
        # Поиск
        if search:
            conditions.append("(ic.model LIKE ? OR ic.current_color LIKE ?)")
            params.extend([f'%{search}%', f'%{search}%'])
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # Группировка
        query += " GROUP BY ic.product_id"
        
        # Сортировка
        if sort_by == 'price_asc':
            query += " ORDER BY ic.price ASC"
        elif sort_by == 'price_desc':
            query += " ORDER BY ic.price DESC"
        elif sort_by == 'name':
            query += " ORDER BY ic.model ASC"
        else:
            query += " ORDER BY ic.display_order ASC"
        
        cursor.execute(query, params)
        products = [dict(row) for row in cursor.fetchall()]
        
        # Форматируем данные для отображения
        for product in products:
            product['formatted_price'] = f"{product['price']:,} руб.".replace(',', ' ')
            product['short_model'] = product['model'][:30] + '...' if len(product['model']) > 30 else product['model']
            
            # Обрабатываем цвета и память
            if product['all_colors']:
                product['colors_list'] = product['all_colors'].split(',')
            else:
                product['colors_list'] = [product['current_color']] if product['current_color'] else []
            
            if product['all_memory']:
                product['memory_list'] = product['all_memory'].split(',')
            else:
                product['memory_list'] = [product['current_memory']] if product['current_memory'] else []
        
        conn.close()
        return products
    
    def get_categories(self):
        """Получение списка категорий"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT category, COUNT(*) as count 
            FROM iphones_catalog 
            GROUP BY category 
            ORDER BY count DESC
        ''')
        
        categories = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        conn.close()
        return categories
    
    def get_featured_products(self, limit=6):
        """Получение рекомендуемых товаров"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM iphones_catalog 
            WHERE is_featured = 1 
            ORDER BY price DESC 
            LIMIT ?
        ''', (limit,))
        
        products = [dict(row) for row in cursor.fetchall()]
        for product in products:
            product['formatted_price'] = f"{product['price']:,} руб.".replace(',', ' ')
        
        conn.close()
        return products
    
    def get_product_by_id(self, product_id):
        """Получение товара по ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ic.*, 
                   GROUP_CONCAT(DISTINCT icc.color_name) as all_colors,
                   GROUP_CONCAT(DISTINCT icm.memory_size) as all_memory
            FROM iphones_catalog ic
            LEFT JOIN iphone_catalog_colors icc ON ic.product_id = icc.product_id
            LEFT JOIN iphone_catalog_memory icm ON ic.product_id = icm.product_id
            WHERE ic.product_id = ?
            GROUP BY ic.product_id
        ''', (product_id,))
        
        product = cursor.fetchone()
        if product:
            product = dict(product)
            product['formatted_price'] = f"{product['price']:,} руб.".replace(',', ' ')
            
            if product['all_colors']:
                product['colors_list'] = product['all_colors'].split(',')
            else:
                product['colors_list'] = []
            
            if product['all_memory']:
                product['memory_list'] = product['all_memory'].split(',')
            else:
                product['memory_list'] = []
        
        conn.close()
        return product

# Инициализация каталога
catalog = iPhoneCatalog()



@app.route('/')
def index():
    """Главная страница"""
    featured_products = catalog.get_featured_products(6)
    categories = catalog.get_categories()
    
    return render_template('index.html', 
                         featured_products=featured_products,
                         categories=categories,
                         total_products=len(catalog.get_all_products()))

@app.route('/catalog')
def catalog_page():
    """Страница каталога"""
    category = request.args.get('category', 'all')
    sort_by = request.args.get('sort', 'price_desc')
    search = request.args.get('search', '')
    
    products = catalog.get_all_products(category, sort_by, search)
    categories = catalog.get_categories()
    
    return render_template('catalog.html',
                         products=products,
                         categories=categories,
                         current_category=category,
                         current_sort=sort_by,
                         search_query=search,
                         total_products=len(products))

@app.route('/product/<product_id>')
def product_detail(product_id):
    """Страница товара"""
    product = catalog.get_product_by_id(product_id)
    if not product:
        return "Товар не найден", 404
    
    # Похожие товары
    similar_products = catalog.get_all_products(category=product['category'])[:4]
    
    return render_template('product.html',
                         product=product,
                         similar_products=similar_products)

@app.route('/crypto_pay_cart')
def crypto_pay_cart():
    """Creates a single Coinbase charge for the entire cart."""
    if not client:
        flash('Crypto payments are currently disabled.', 'danger')
        return redirect(url_for('cart'))

    cart_session = session.get('cart', {})
    if not cart_session:
        flash('Your cart is empty.', 'info')
        return redirect(url_for('cart'))

    # 1. Calculate total price and gather item details
    total_price = 0
    item_ids = []
    item_descriptions = []
    for product_id, quantity in cart_session.items():
        product = catalog.get_product_by_id(product_id)
        if product:
            total_price += product['price'] * quantity
            item_ids.append(product_id)
            item_descriptions.append(f"{product['model']} (x{quantity})")

    if total_price == 0:
        flash('Cannot process a zero-value cart.', 'danger')
        return redirect(url_for('cart'))

    # 2. Create a single order for the whole cart
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Store a comma-separated list of product IDs for simplicity
    product_ids_str = ",".join(item_ids)
    cursor.execute(
        'INSERT INTO orders (product_id, price, status) VALUES (?, ?, ?)',
        (product_ids_str, total_price, 'new')
    )
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()

    # 3. Create a Coinbase Commerce charge for the cart
    charge_info = {
        'name': f'Your Order #{order_id} from TonStore',
        'description': ", ".join(item_descriptions),
        'local_price': {
            'amount': str(total_price),
            'currency': 'RUB'
        },
        'pricing_type': 'fixed_price',
        'metadata': {
            'order_id': order_id,
            'cart_items': json.dumps(cart_session)
        },
        'redirect_url': url_for('order_status', order_id=order_id, _external=True),
        'cancel_url': url_for('cart', _external=True),
    }

    try:
        charge = client.charge.create(**charge_info)
        
        # Save the charge code to the order
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE orders SET charge_code = ?, status = ? WHERE id = ?',
            (charge.code, 'pending', order_id)
        )
        conn.commit()
        conn.close()

        return redirect(charge.hosted_url)
    except Exception as e:
        flash(f'Error creating payment: {e}', 'danger')
        return redirect(url_for('cart'))


@app.route('/crypto_pay/<product_id>')
def crypto_pay(product_id):
    """Creates an order and redirects to a Coinbase Commerce charge page."""
    if not client:
        flash('Crypto payments are currently disabled.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    product = catalog.get_product_by_id(product_id)
    if not product:
        return "Товар не найден", 404

    # 1. Create a new order in the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO orders (product_id, price, status) VALUES (?, ?, ?)',
        (product['product_id'], product['price'], 'new')
    )
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()

    # 2. Create a Coinbase Commerce charge
    charge_info = {
        'name': product['model'],
        'description': f"Order #{order_id}",
        'local_price': {
            'amount': str(product['price']),
            'currency': 'RUB'
        },
        'pricing_type': 'fixed_price',
        'metadata': {
            'order_id': order_id,
            'product_id': product['product_id']
        },
        'redirect_url': url_for('order_status', order_id=order_id, _external=True),
        'cancel_url': url_for('product_detail', product_id=product_id, _external=True),
    }

    try:
        charge = client.charge.create(**charge_info)
        
        # Save the charge code to the order
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE orders SET charge_code = ?, status = ? WHERE id = ?',
            (charge.code, 'pending', order_id)
        )
        conn.commit()
        conn.close()

        return redirect(charge.hosted_url)
    except Exception as e:
        flash(f'Error creating payment: {e}', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))


@app.route('/webhooks/coinbase', methods=['POST'])
def coinbase_webhook():
    """Handles incoming webhooks from Coinbase Commerce."""
    if not COINBASE_WEBHOOK_SECRET:
        return "Webhook secret not configured", 500

    sig_header = request.headers.get('X-CC-Webhook-Signature')
    payload = request.data

    try:
        event = Webhook.construct_event(payload, sig_header, COINBASE_WEBHOOK_SECRET)
    except (Webhook.SignatureVerificationError, Webhook.WebhookInvalidPayload) as e:
        return str(e), 400

    # Handle the event
    if event.type == 'charge:confirmed':
        order_id = event.data.metadata.get('order_id')
        if order_id:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = 'paid' WHERE id = ?",
                (order_id,)
            )
            conn.commit()
            conn.close()
            print(f"✅ Order {order_id} marked as paid.")

    elif event.type == 'charge:failed':
        order_id = event.data.metadata.get('order_id')
        if order_id:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = 'failed' WHERE id = ?",
                (order_id,)
            )
            conn.commit()
            conn.close()
            print(f"❌ Order {order_id} marked as failed.")
            
    return 'OK', 200

@app.route('/order_status/<int:order_id>')
def order_status(order_id):
    """Displays the status of an order after payment attempt."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        return "Order not found", 404
        
    product = catalog.get_product_by_id(order['product_id'])

    return render_template('order_status.html', order=order, product=product)

@app.route('/api/products')
def api_products():
    """API для получения товаров (для AJAX)"""
    category = request.args.get('category', 'all')
    sort_by = request.args.get('sort', 'price_desc')
    search = request.args.get('search', '')
    
    products = catalog.get_all_products(category, sort_by, search)
    return jsonify(products)

@app.route('/api/categories')
def api_categories():
    """API для получения категорий"""
    categories = catalog.get_categories()
    return jsonify(categories)

@app.route('/cart')
def cart():
    """Страница корзины"""
    if 'cart' not in session:
        session['cart'] = {}
    
    cart_products = []
    total_price = 0
    
    for product_id, quantity in session['cart'].items():
        product = catalog.get_product_by_id(product_id)
        if product:
            product['quantity'] = quantity
            product['total_price'] = product['price'] * quantity
            cart_products.append(product)
            total_price += product['total_price']
            
    return render_template('cart.html', cart_products=cart_products, total_price=total_price, catalog=catalog, total_products=len(catalog.get_all_products()))

@app.route('/add_to_cart/<product_id>')
def add_to_cart(product_id):
    """Добавление товара в корзину"""
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    cart[product_id] = cart.get(product_id, 0) + 1
    session['cart'] = cart
    
    flash('Товар добавлен в корзину!', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/remove_from_cart/<product_id>')
def remove_from_cart(product_id):
    """Удаление товара из корзины"""
    if 'cart' in session and product_id in session['cart']:
        session['cart'].pop(product_id)
        flash('Товар удален из корзины!', 'info')
    return redirect(url_for('cart'))

@app.route('/clear_cart')
def clear_cart():
    """Очистка корзины"""
    session.pop('cart', None)
    flash('Корзина очищена!', 'info')
    return redirect(url_for('cart'))

@app.context_processor
def inject_cart_count():
    """Доступное количество товаров в корзине во всех шаблонах"""
    cart_count = 0
    if 'cart' in session:
        cart_count = sum(session['cart'].values())
    return dict(cart_count=cart_count)

@app.after_request
def add_header(response):
    """Add headers to prevent caching."""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)