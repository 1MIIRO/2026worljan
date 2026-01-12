from flask import Flask, request, jsonify, render_template, render_template_string, session, redirect, url_for
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from datetime import datetime, timedelta
import random
import string

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Required for sessions

# --- CONFIG ---
ORDER_HISTORY_FILE = "order_history.json"  # store past order numbers and count

# Load or initialize
import json
try:
    with open(ORDER_HISTORY_FILE, "r") as f:
        order_history = json.load(f)
except:
    order_history = {"last_letter_index": 0, "last_letter_repeat": 1, "letter_count": 0, "used_numbers": []}

def get_letter_suffix():
    """
    Determines the current letter suffix based on letter_count.
    Every 10 orders, it moves to the next letter.
    After Z -> AA, BB, ..., then AAA, BBB, etc.
    """
    letters = string.ascii_uppercase
    count = order_history["letter_count"]
    repeat = order_history["last_letter_repeat"]
    
    # Calculate which letter
    idx = order_history["last_letter_index"]
    
    # Build suffix
    if idx < 26:
        suffix = letters[idx] * repeat
    else:
        # Once past Z, keep repeating the last letters as needed
        suffix = letters[idx % 26] * repeat

    return suffix

def increment_letter_count():
    """Increment counters after each order and update repeat if needed"""
    order_history["letter_count"] += 1
    if order_history["letter_count"] >= 10:
        order_history["letter_count"] = 0
        order_history["last_letter_index"] += 1
        if order_history["last_letter_index"] >= 26 * order_history["last_letter_repeat"]:
            order_history["last_letter_index"] = 0
            order_history["last_letter_repeat"] += 1

def generate_unique_number():
    """Generate a 6-digit number never used before"""
    while True:
        number = random.randint(100000, 999999)
        if number not in order_history["used_numbers"]:
            order_history["used_numbers"].append(number)
            return number

def generate_order_number():
    number = generate_unique_number()
    suffix = get_letter_suffix()
    increment_letter_count()

    # Save history
    with open(ORDER_HISTORY_FILE, "w") as f:
        json.dump(order_history, f)

    return f"#{number}{suffix}"

# Database connection function
def get_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='1234',
        database='bakery_busness'
    )

# --- LOGIN PAGE TEMPLATE ---
login_page_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login Page</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f5f5f5; }
        .vh-100 { height: 100vh; }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center align-items-center vh-100">
            <div class="col-md-4">
                <div class="card p-4 shadow-lg">
                    <h3 class="text-center mb-3">Login</h3>
                    <form id="loginForm" method="POST" action="/login">
                        <div class="mb-3">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-control" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-control" name="password" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Login</button>
                        <p id="errorMsg" class="text-danger mt-2" style="display:none;">Invalid username or password</p>
                    </form>
                </div>
            </div>
        </div>
    </div>

<script>
const loginForm = document.getElementById('loginForm');
const errorMsg = document.getElementById('errorMsg');

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(loginForm);
    const response = await fetch('/login', { method: 'POST', body: formData });
    const result = await response.json();
    if (result.success) {
        window.location.href = '/dashboard';
    } else {
        errorMsg.style.display = 'block';
    }
});
</script>
</body>
</html>
"""

def insert_into_order_table(order_number):
    """
    Inserts a new record into order_table
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO order_table (order_number, Dateandtime_ordered)
        VALUES (%s, %s)
    """, (order_number, datetime.now()))

    conn.commit()

    cursor.close()
    conn.close()

@app.route('/')
def login_page():
    return render_template_string(login_page_html)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM `user` WHERE user_name=%s AND user_password=%s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        # Save user session
        session['user_id'] = user['user_id']
        session['user_name'] = user['user_name']
        session['personal_name'] = user['personal_name']
        session['job_desc'] = user['job_desc']
        return jsonify({"success": True})

    return jsonify({"success": False})

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    # Get user info from session
    user_info = {
        "user_name": session.get('user_name'),
        "personal_name": session.get('personal_name'),
        "job_desc": session.get('job_desc')
    }
    
        # Fetch order categories (Order Type dropdown)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT order_categories_ID, order_categories_name
        FROM order_categories
        ORDER BY order_categories_name
    """)
    order_categories = cursor.fetchall()
    cursor.close()
    conn.close()


   # Fetch products with their categories
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            p.good_number,
            p.good_name,
            c.product_category_name AS good_category
        FROM products p
        LEFT JOIN products_category_table pct
            ON p.good_number = pct.product_number
        LEFT JOIN product_categories c
            ON pct.product_category_number = c.product_category_number
        ORDER BY p.good_number
    """)
    product_categories = cursor.fetchall()  # This will be a list of dicts with good_number, good_name, good_category
    cursor.close()
    conn.close()
    
    product_category_map = {p['good_number']: p['good_category'] for p in product_categories}

    # Fetch products
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.close()
    conn.close()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT Table_db_id,  Table_number FROM tables ORDER BY  Table_number")
    tables = cursor.fetchall()
    cursor.close()
    conn.close()
    order_description = session.get("order_description", "")
    return render_template('dashboard.html', user=user_info, products=products,tables=tables,order_categories=order_categories, product_categories=product_categories,product_category_map=product_category_map,order_description=order_description)

@app.route('/description', methods=['GET', 'POST'])
def description_page():
    if request.method == 'POST':
        # Save description in session
        session["order_description"] = request.form.get("description_text")
        return redirect(url_for('dashboard'))
    
    # On GET, load existing description
    description_text = session.get("order_description", "")
    return render_template('description.html', description=description_text)

@app.route('/activity_billing_queue')
def activity_billing_queue():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    user_info = {
        "user_name": session.get('user_name'),
        "personal_name": session.get('personal_name'),
        "job_desc": session.get('job_desc')
    }

    # Fetch all tables for the dropdown
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT Table_db_id,  Table_number FROM tables ORDER BY  Table_number")
    tables = cursor.fetchall()
    cursor.close()
    conn.close()

    # Pass the tables to the template
    return render_template('activity_billing_queue.html', user=user_info, tables=tables)

@app.route('/activity_Tables')
def activity_Tables():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    user_info = {
        "user_name": session.get('user_name'),
        "personal_name": session.get('personal_name'),
        "job_desc": session.get('job_desc')
    }

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            t.Table_db_id,
            t.Table_number,
            tf.floor_name AS table_floor,

            COALESCE(tr.table_status, 'available') AS table_status,
            tr.Date_reserved,
            tr.number_of_people

        FROM tables t

        LEFT JOIN table_floor tf
            ON t.Table_db_id = tf.Table_db_id

        LEFT JOIN (
            SELECT r1.*
            FROM table_reservations r1
            INNER JOIN (
                SELECT Table_db_id, MAX(Date_reserved) AS max_date
                FROM table_reservations
                GROUP BY Table_db_id
            ) r2
            ON r1.Table_db_id = r2.Table_db_id
            AND r1.Date_reserved = r2.max_date
        ) tr
            ON t.Table_db_id = tr.Table_db_id

        ORDER BY tf.floor_name, t.Table_number
    """

    cursor.execute(query)
    all_tables = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'activity_Tables.html',
        user=user_info,
        tables=all_tables
    )

@app.route('/activity_Order_history')
def activity_Order_history():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    user_info = {
        "user_name": session.get('user_name'),
        "personal_name": session.get('personal_name'),
        "job_desc": session.get('job_desc')
    }
    
    # Fetch all tables for the dropdown
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT Table_db_id,  Table_number FROM tables ORDER BY  Table_number")
    tables = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('activity_Order_history.html',user=user_info,tables=tables)

@app.route('/place_order_table', methods=['POST'])
def place_order_table():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "User not logged in"})

    data = request.get_json()
    order_type_val = data.get('order_type')        # 'Dine_in', 'Take_away', 'Delivery'
    order_number = data.get('order_number')
    customer_name = data.get('customer_name')
    table_id = data.get('table_id')
    order_items = data.get('order_items')
    order_desc = data.get('order_desc')         

    # Validate required fields
    if not order_number or not order_type_val or not customer_name or not table_id or not order_items:
        return jsonify({"success": False, "error": "Missing required fields"})

    user_id = session['user_id']
    now = datetime.now()
    current_date = now.date()
    current_time = now.time()

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 1️⃣ Insert into orders_improved_table
        items_count = sum(item['quantity'] for item in order_items)
        total_amount = sum(item['quantity'] * item['price_at_order'] for item in order_items)
        order_state = "pending"

        cursor.execute("""
            INSERT INTO orders_improved_table (
                order_identification_number,
                items_count,
                order_state,
                order_desc,       
                user_id,
                Total_ammount,
                DATE,
                TIME,
                LAST_UPDATE
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            order_number,
            items_count,
            order_state,
            order_desc,
            user_id,
            total_amount,
            current_date,
            current_time,
            now
        ))

        # Get the primary key of the new order
        order_id = cursor.lastrowid

        # 2️⃣ Get order_categories_ID from order_categories table
        cursor.execute("""
            SELECT order_categories_ID 
            FROM order_categories 
            WHERE order_categories_name = %s
        """, (order_type_val,))
        category_row = cursor.fetchone()
        if not category_row:
            raise ValueError("Invalid order category selected")

        order_categories_ID = category_row['order_categories_ID']

        # 3️⃣ Insert into order_with_categories
        cursor.execute("""
            INSERT INTO order_with_categories (order_ID, order_categories_ID)
            VALUES (%s, %s)
        """, (order_id, order_categories_ID))

        # 4️⃣ Insert into customer_order
        cursor.execute("""
            INSERT INTO customer_order (order_id, customer_name)
            VALUES (%s, %s)
        """, (order_id, customer_name))

        # 5️⃣ Insert each item into order_items
        for item in order_items:
            good_name = item['good_name']
            quantity = item['quantity']
            price_at_order = item['price_at_order']

            cursor.execute("SELECT good_number FROM products WHERE good_name = %s", (good_name,))
            product_row = cursor.fetchone()
            if not product_row:
                continue  # skip missing products

            good_number = product_row['good_number']

            cursor.execute("""
                INSERT INTO order_items (order_id, good_number, quantity, price_at_order)
                VALUES (%s, %s, %s, %s)
            """, (order_id, good_number, quantity, price_at_order))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "order_id": order_id})

    except Exception as e:
        print("Database Error:", e)
        return jsonify({"success": False, "error": str(e)})

@app.route('/trackhome_orders')
def trackhome_orders():
    if 'user_id' not in session:
        return jsonify([])  # empty if not logged in

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Your original query with joins
    query = """
        SELECT 
            co.customer_name,
            t.Table_number,
            ot.order_type,
            o.order_time
        FROM orders o
        LEFT JOIN customer_order co ON o.order_id = co.order_id
        LEFT JOIN order_type ot ON o.order_id = ot.order_id
        LEFT JOIN tables t ON ot.table_id = t.Table_db_id
        ORDER BY o.order_time DESC
    """

    cursor.execute(query)
    orders_raw = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert datetime/timedelta to string to be JSON serializable
    orders = []
    for order in orders_raw:
        converted_order = {}
        for key, value in order.items():
            if isinstance(value, datetime):
                value = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, timedelta):
                total_seconds = int(value.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                value = f"{hours:02}:{minutes:02}:{seconds:02}"
            converted_order[key] = value
        orders.append(converted_order)

    return jsonify(orders)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == "__main__":
 app.run(debug=True)
 









































