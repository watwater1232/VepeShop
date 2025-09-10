import os
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import redis

app = Flask(__name__, static_folder="static")
CORS(app)

# Redis connection
redis_url = os.getenv("REDIS_URL", "redis://red-d2m4543uibrs73fqt7c0:6379")
try:
    redis_client = redis.from_url(redis_url, decode_responses=True)
    # Test connection
    redis_client.ping()
    print("✅ Connected to Redis")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    exit(1)

# Redis keys
PRODUCTS_KEY = "vape_shop:products"
ORDERS_KEY = "vape_shop:orders"
USERS_KEY = "vape_shop:users"
PROMOS_KEY = "vape_shop:promos"
STATS_KEY = "vape_shop:stats"

# Admin Telegram IDs
ADMIN_IDS = {1286638668}  # Add your Telegram IDs here

# Helper functions
def get_current_time():
    return datetime.now().isoformat()

def get_next_id(key_prefix):
    """Get next available ID for entities"""
    counter_key = f"{key_prefix}:counter"
    return redis_client.incr(counter_key)

# Product management
def get_all_products():
    """Get all products from Redis"""
    try:
        product_keys = redis_client.keys(f"{PRODUCTS_KEY}:*")
        if not product_keys:
            return []
        
        products = []
        for key in product_keys:
            if key.endswith(':counter'):
                continue
            product_data = redis_client.hgetall(key)
            if product_data:
                # Convert numeric fields
                product_data['id'] = int(product_data['id'])
                product_data['price'] = int(product_data['price'])
                product_data['stock'] = int(product_data['stock'])
                products.append(product_data)
        
        return sorted(products, key=lambda x: x['id'])
    except Exception as e:
        print(f"Error getting products: {e}")
        return []

def save_product(product_data):
    """Save product to Redis"""
    try:
        if 'id' not in product_data:
            product_data['id'] = get_next_id(PRODUCTS_KEY)
        
        product_key = f"{PRODUCTS_KEY}:{product_data['id']}"
        
        # Ensure required fields
        product_data.setdefault('created_at', get_current_time())
        product_data['updated_at'] = get_current_time()
        
        redis_client.hset(product_key, mapping=product_data)
        return product_data
    except Exception as e:
        print(f"Error saving product: {e}")
        return None

def delete_product(product_id):
    """Delete product from Redis"""
    try:
        product_key = f"{PRODUCTS_KEY}:{product_id}"
        return redis_client.delete(product_key) > 0
    except Exception as e:
        print(f"Error deleting product: {e}")
        return False

# Order management
def get_all_orders():
    """Get all orders from Redis"""
    try:
        order_keys = redis_client.keys(f"{ORDERS_KEY}:*")
        if not order_keys:
            return []
        
        orders = []
        for key in order_keys:
            if key.endswith(':counter'):
                continue
            order_data = redis_client.hgetall(key)
            if order_data:
                # Convert numeric fields and parse JSON
                order_data['id'] = int(order_data['id'])
                order_data['userId'] = int(order_data['userId'])
                order_data['total'] = int(order_data['total'])
                order_data['items'] = json.loads(order_data['items'])
                orders.append(order_data)
        
        return sorted(orders, key=lambda x: x['id'], reverse=True)
    except Exception as e:
        print(f"Error getting orders: {e}")
        return []

def save_order(order_data):
    """Save order to Redis"""
    try:
        if 'id' not in order_data:
            order_data['id'] = get_next_id(ORDERS_KEY)
        
        order_key = f"{ORDERS_KEY}:{order_data['id']}"
        
        # Ensure required fields
        order_data.setdefault('created_at', get_current_time())
        order_data.setdefault('status', 'pending')
        
        # Convert items to JSON string for Redis storage
        items = order_data.pop('items', [])
        order_data['items'] = json.dumps(items)
        
        redis_client.hset(order_key, mapping=order_data)
        
        # Put items back for return
        order_data['items'] = items
        
        # Update stats
        update_stats()
        
        return order_data
    except Exception as e:
        print(f"Error saving order: {e}")
        return None

def get_orders_by_user(user_id):
    """Get orders for specific user"""
    try:
        all_orders = get_all_orders()
        return [order for order in all_orders if order['userId'] == user_id]
    except Exception as e:
        print(f"Error getting user orders: {e}")
        return []

# User management
def get_user(user_id):
    """Get user data from Redis"""
    try:
        user_key = f"{USERS_KEY}:{user_id}"
        user_data = redis_client.hgetall(user_key)
        if user_data:
            user_data['id'] = int(user_data['id'])
            user_data['bonus'] = int(user_data.get('bonus', 0))
            user_data['referrals'] = json.loads(user_data.get('referrals', '[]'))
            user_data['isAdmin'] = user_id in ADMIN_IDS
        return user_data
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def save_user(user_data):
    """Save user to Redis"""
    try:
        user_key = f"{USERS_KEY}:{user_data['id']}"
        
        # Convert referrals to JSON string
        referrals = user_data.get('referrals', [])
        user_data['referrals'] = json.dumps(referrals)
        
        user_data.setdefault('created_at', get_current_time())
        user_data['updated_at'] = get_current_time()
        
        redis_client.hset(user_key, mapping=user_data)
        
        # Put referrals back for return
        user_data['referrals'] = referrals
        
        return user_data
    except Exception as e:
        print(f"Error saving user: {e}")
        return None

# Promo management
def get_all_promos():
    """Get all promos from Redis"""
    try:
        promo_keys = redis_client.keys(f"{PROMOS_KEY}:*")
        if not promo_keys:
            return []
        
        promos = []
        for key in promo_keys:
            promo_data = redis_client.hgetall(key)
            if promo_data:
                # Convert numeric fields
                promo_data['discount'] = int(promo_data['discount'])
                promo_data['uses'] = int(promo_data['uses'])
                promo_data['used'] = int(promo_data.get('used', 0))
                promos.append(promo_data)
        
        return promos
    except Exception as e:
        print(f"Error getting promos: {e}")
        return []

def save_promo(promo_data):
    """Save promo to Redis"""
    try:
        promo_key = f"{PROMOS_KEY}:{promo_data['code']}"
        
        promo_data.setdefault('used', 0)
        promo_data.setdefault('created_at', get_current_time())
        promo_data['updated_at'] = get_current_time()
        
        redis_client.hset(promo_key, mapping=promo_data)
        return promo_data
    except Exception as e:
        print(f"Error saving promo: {e}")
        return None

# Stats management
def update_stats():
    """Update global statistics"""
    try:
        stats = {
            'total_orders': len(get_all_orders()),
            'total_products': len(get_all_products()),
            'total_users': len(redis_client.keys(f"{USERS_KEY}:*")),
            'total_revenue': sum(order['total'] for order in get_all_orders() if order['status'] == 'completed'),
            'updated_at': get_current_time()
        }
        redis_client.hset(STATS_KEY, mapping=stats)
        return stats
    except Exception as e:
        print(f"Error updating stats: {e}")
        return {}

def get_stats():
    """Get global statistics"""
    try:
        stats = redis_client.hgetall(STATS_KEY)
        if stats:
            for key in ['total_orders', 'total_products', 'total_users', 'total_revenue']:
                stats[key] = int(stats.get(key, 0))
        return stats or update_stats()
    except Exception as e:
        print(f"Error getting stats: {e}")
        return update_stats()

# Routes
@app.route("/")
def index():
    """Serve React app"""
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    """Serve static files"""
    return send_from_directory(app.static_folder, path)

# API Routes
@app.route("/api/products", methods=["GET"])
def api_get_products():
    """Get all products"""
    try:
        products = get_all_products()
        return jsonify(products)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/products", methods=["POST"])
def api_add_product():
    """Add new product"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Validate required fields
        required_fields = ['name', 'category', 'price', 'stock']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400
        
        product = save_product(data)
        if product:
            return jsonify({"success": True, "product": product})
        else:
            return jsonify({"error": "Failed to save product"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/products/<int:product_id>", methods=["PUT"])
def api_update_product(product_id):
    """Update product"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        data['id'] = product_id
        product = save_product(data)
        if product:
            return jsonify({"success": True, "product": product})
        else:
            return jsonify({"error": "Failed to update product"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def api_delete_product(product_id):
    """Delete product"""
    try:
        if delete_product(product_id):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/orders", methods=["GET"])
def api_get_orders():
    """Get all orders (admin only)"""
    try:
        # In production, add admin check here
        orders = get_all_orders()
        return jsonify(orders)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/orders", methods=["POST"])
def api_create_order():
    """Create new order"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Validate required fields
        required_fields = ['userId', 'items', 'total']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400
        
        if not data['items']:
            return jsonify({"error": "Order must contain items"}), 400
        
        order = save_order(data)
        if order:
            return jsonify({"success": True, "order": order})
        else:
            return jsonify({"error": "Failed to create order"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/orders/<int:user_id>", methods=["GET"])
def api_get_user_orders(user_id):
    """Get orders for specific user"""
    try:
        orders = get_orders_by_user(user_id)
        return jsonify(orders)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/orders/<int:order_id>/status", methods=["PUT"])
def api_update_order_status(order_id):
    """Update order status"""
    try:
        data = request.json
        if not data or 'status' not in data:
            return jsonify({"error": "Status is required"}), 400
        
        order_key = f"{ORDERS_KEY}:{order_id}"
        if redis_client.exists(order_key):
            redis_client.hset(order_key, 'status', data['status'])
            redis_client.hset(order_key, 'updated_at', get_current_time())
            update_stats()
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Order not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/users/<int:user_id>", methods=["GET"])
def api_get_user(user_id):
    """Get user data"""
    try:
        user = get_user(user_id)
        if user:
            return jsonify(user)
        else:
            # Create new user if doesn't exist
            new_user = {
                'id': user_id,
                'username': f'user_{user_id}',
                'bonus': 0,
                'referrals': [],
                'referralCode': f'REF{user_id:06d}',
                'isAdmin': user_id in ADMIN_IDS
            }
            saved_user = save_user(new_user)
            return jsonify(saved_user)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/users/<int:user_id>", methods=["PUT"])
def api_update_user(user_id):
    """Update user data"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        data['id'] = user_id
        user = save_user(data)
        if user:
            return jsonify({"success": True, "user": user})
        else:
            return jsonify({"error": "Failed to update user"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/promos", methods=["GET"])
def api_get_promos():
    """Get all promos"""
    try:
        promos = get_all_promos()
        return jsonify(promos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/promos", methods=["POST"])
def api_create_promo():
    """Create new promo"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        required_fields = ['code', 'discount', 'uses']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400
        
        # Check if promo already exists
        promo_key = f"{PROMOS_KEY}:{data['code']}"
        if redis_client.exists(promo_key):
            return jsonify({"error": "Promo code already exists"}), 400
        
        promo = save_promo(data)
        if promo:
            return jsonify({"success": True, "promo": promo})
        else:
            return jsonify({"error": "Failed to create promo"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/promos/<code>/apply", methods=["POST"])
def api_apply_promo(code):
    """Apply promo code"""
    try:
        data = request.json
        if not data or 'userId' not in data:
            return jsonify({"error": "User ID is required"}), 400
        
        promo_key = f"{PROMOS_KEY}:{code}"
        promo_data = redis_client.hgetall(promo_key)
        
        if not promo_data:
            return jsonify({"error": "Promo code not found"}), 404
        
        # Convert numeric fields
        promo_data['used'] = int(promo_data.get('used', 0))
        promo_data['uses'] = int(promo_data['uses'])
        promo_data['discount'] = int(promo_data['discount'])
        
        if promo_data['used'] >= promo_data['uses']:
            return jsonify({"error": "Promo code limit reached"}), 400
        
        # Update promo usage
        redis_client.hincrby(promo_key, 'used', 1)
        
        return jsonify({
            "success": True,
            "discount": promo_data['discount'],
            "message": f"Promo applied! {promo_data['discount']}% discount"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stats", methods=["GET"])
def api_get_stats():
    """Get global statistics"""
    try:
        stats = get_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/check-admin", methods=["GET"])
def api_check_admin():
    """Check if user is admin"""
    try:
        tg_id = request.args.get('tg_id')
        if not tg_id:
            return jsonify({"isAdmin": False})
        
        try:
            tg_id = int(tg_id)
            is_admin = tg_id in ADMIN_IDS
            return jsonify({"isAdmin": is_admin})
        except ValueError:
            return jsonify({"isAdmin": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/broadcast", methods=["POST"])
def api_broadcast():
    """Send broadcast message (admin only)"""
    try:
        data = request.json
        if not data or 'message' not in data:
            return jsonify({"error": "Message is required"}), 400
        
        # In production, add admin authentication here
        
        # Store broadcast in Redis for logging
        broadcast_key = f"broadcasts:{int(time.time())}"
        broadcast_data = {
            'message': data['message'],
            'sent_at': get_current_time(),
            'sent_by': data.get('admin_id', 'unknown')
        }
        redis_client.hset(broadcast_key, mapping=broadcast_data)
        
        # In real implementation, send to all users via Telegram Bot API
        # For now, just return success
        return jsonify({
            "success": True,
            "message": "Broadcast sent successfully"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def init_sample_data():
    """Initialize with sample products if none exist"""
    try:
        if not get_all_products():
            sample_products = [
                {
                    "name": "Жидкость Mango",
                    "category": "liquids",
                    "price": 450,
                    "stock": 10,
                    "description": "Вкусный манго",
                    "emoji": "🥭"
                },
                {
                    "name": "Картридж JUUL",
                    "category": "cartridges",
                    "price": 300,
                    "stock": 20,
                    "description": "Оригинальные картриджи",
                    "emoji": "💨"
                },
                {
                    "name": "Под RELX Mint",
                    "category": "pods",
                    "price": 280,
                    "stock": 12,
                    "description": "Мятный вкус",
                    "emoji": "🔥"
                },
                {
                    "name": "Vaporesso XROS 3",
                    "category": "devices",
                    "price": 2800,
                    "stock": 5,
                    "description": "Компактная POD-система",
                    "emoji": "⚡"
                }
            ]
            
            for product in sample_products:
                save_product(product)
            
            print("✅ Sample products initialized")
        
        # Initialize stats
        update_stats()
        print("✅ Stats initialized")
        
    except Exception as e:
        print(f"❌ Error initializing sample data: {e}")

if __name__ == "__main__":
    print("🚀 Starting Vape Shop Server...")
    init_sample_data()
    
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    
    print(f"🌐 Server starting on port {port}")
    print(f"🔧 Debug mode: {debug}")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    
    app.run(host="0.0.0.0", port=port, debug=debug)
