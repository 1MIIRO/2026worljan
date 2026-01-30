from flask import Flask, request, jsonify, render_template, render_template_string, session, redirect, url_for
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from datetime import datetime, timedelta
import random
import string

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Required for sessions
# ---------------- ORDER NUMBER LOGIC ----------------

def index_to_suffix(index: int) -> str:
    letters = string.ascii_uppercase
    index += 1
    suffix = ""

    while index > 0:
        index -= 1
        suffix = letters[index % 26] + suffix
        index //= 26

    return suffix

def generate_unique_6_digit(cursor):
    while True:
        number = random.randint(100000, 999999)
        cursor.execute("""
            SELECT 1 FROM orders_improved_table
            WHERE order_identification_number LIKE %s
            LIMIT 1
        """, (f"#{number}%",))
        if cursor.fetchone() is None:
            return number

def generate_next_order_number():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM orders_improved_table")
    total_orders = cursor.fetchone()[0]

    suffix = index_to_suffix(total_orders // 10)
    random_number = generate_unique_6_digit(cursor)

    cursor.close()
    conn.close()

    return f"#{random_number}{suffix}"

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

@app.route('/get_reservation_statuses')
def get_reservation_statuses():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT reservation_status_id, status_name FROM reservation_status")
    reservationstatuses = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(reservationstatuses )

@app.route('/')
def login_page():
    return render_template_string(login_page_html)

@app.route('/login', methods=['POST'])
def login():
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 1️⃣ Check user credentials
        cursor.execute("SELECT * FROM `user` WHERE user_name=%s AND user_password=%s", (username, password))
        user = cursor.fetchone()

        if user:
            # 2️⃣ Save user session
            session['user_id'] = user['user_id']
            session['user_name'] = user['user_name']
            session['personal_name'] = user['personal_name']
            session['job_desc'] = user['job_desc']

            # 3️⃣ Get Description_audit_id for "LOG-IN"
            cursor.execute("SELECT description_audit_id FROM Description_audit WHERE Description_Title = %s", ("LOG-IN",))
            desc_row = cursor.fetchone()
            if not desc_row:
                cursor.close()
                conn.close()
                return jsonify({"success": False, "error": "LOG-IN description not found"})

            description_audit_id = desc_row['description_audit_id']

            # 4️⃣ Get current date and time
            now = datetime.now()
            audit_date = now.date()
            audit_time = now.time().replace(microsecond=0)

            # 5️⃣ Insert into Audit_Logs (temporary reference number first)
            cursor.execute("""
                INSERT INTO Audit_Logs (audit_reference_number, action, audit_date, audit_time, done_by)
                VALUES (%s, %s, %s, %s, %s)
            """, ("TEMP", "", audit_date, audit_time, f"{session['user_id']}---{session['personal_name']}---{session['user_name']}"))
            conn.commit()
            audit_ID = cursor.lastrowid

            # 6️⃣ Generate audit_reference_number as "#audit_ID.user_id.activity_number"
            audit_reference_number = f"#{audit_ID}.{session['user_id']}.{description_audit_id}"

            # 7️⃣ Update Audit_Logs with actual reference number and action
            action_text = f"Login into the system successful done by {session['user_id']}, {session['job_desc']}"
            cursor.execute("""
                UPDATE Audit_Logs
                SET audit_reference_number=%s, action=%s
                WHERE audit_ID=%s
            """, (audit_reference_number, action_text, audit_ID))
            conn.commit()

            # 8️⃣ Insert into audit_desc table
            cursor.execute("""
                INSERT INTO audit_desc (audit_ID, description_audit_id)
                VALUES (%s, %s)
            """, (audit_ID, description_audit_id))
            conn.commit()

            cursor.close()
            conn.close()

            return jsonify({"success": True})

        cursor.close()
        conn.close()
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

    # Pass the tables to the template
    return render_template('activity_billing_queue.html', user=user_info)

@app.route('/activity_Tables', methods=["GET", "POST"])
def activity_Tables():
    # --- SESSION CHECK ---
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    # --- USER INFO ---
    user_info = {
        "user_name": session.get('user_name'),
        "personal_name": session.get('personal_name'),
        "job_desc": session.get('job_desc')
    }

    error_msg = None
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # --- HANDLE NEW RESERVATION SUBMISSION ---
    if request.method == "POST":
        table_id = int(request.form["table_id"])
        number_of_people = int(request.form["number_of_people"])
        reservation_notes = request.form["reservation_notes"]
        customer_name = request.form["customer_name"]
        resservation_date = request.form["resservation_date"]
        reservation_time = request.form["reservation_time"]
        reservation_status_id = int(request.form["reservation_status"])
        user_id = session['user_id']
        now = datetime.now()

        # ---- CONFLICT CHECK ----
        cursor.execute("""
            SELECT tr.reservation_time
            FROM table_reservations tr
            JOIN table_reservation_link trl
              ON tr.reservation_id = trl.reservation_id
            WHERE trl.table_id = %s
              AND tr.resservation_date = %s
        """, (table_id, resservation_date))

        existing = cursor.fetchall()
        new_time = datetime.strptime(reservation_time, "%H:%M")

        for r in existing:
            existing_time = datetime.strptime(str(r["reservation_time"]), "%H:%M:%S")
            if existing_time - timedelta(hours=1) <= new_time <= existing_time + timedelta(hours=2):
                error_msg = (
                    "Reservation time conflicts with an existing reservation "
                    "(1 hour before or 2 hours after)."
                )
                break

        if not error_msg:
            # ---- INSERT reservation ----
            cursor.execute("""
                INSERT INTO table_reservations
                (number_of_people, reservation_notes, resservation_date, reservation_time, Datetime_reservation_was_made)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                number_of_people,
                reservation_notes,
                resservation_date,
                reservation_time,
                now
            ))
            conn.commit()

            reservation_id = cursor.lastrowid

            # ---- INSERT reservation status ----
            cursor.execute("""
                INSERT INTO table_reservation_status
                (reservation_id, reservation_status_id, datetime_of_status)
                VALUES (%s, %s, %s)
            """, (reservation_id, reservation_status_id, now))
            conn.commit()

            cursor.execute("""
                INSERT INTO customer_table_reservations
                (reservation_id,customer_name)
                VALUES (%s, %s)
            """, (reservation_id, customer_name))
            conn.commit()

            cursor.execute("""
                INSERT INTO user_reservations
                (user_id,reservation_id)
                VALUES (%s, %s)
            """, (user_id, reservation_id))
            conn.commit()

            # ---- LINK reservation to table ----
            cursor.execute("""
                INSERT INTO table_reservation_link
                (table_id, reservation_id)
                VALUES (%s, %s)
            """, (table_id, reservation_id))
            conn.commit()

            return redirect(url_for('activity_Tables'))

    # --- FETCH ALL TABLES AND FLOOR INFO ---
    cursor.execute("""
        SELECT t.Table_db_id, t.Table_number, t.table_capacity, tf.floor_name
        FROM tables t
        LEFT JOIN table_floor tf
        ON t.Table_db_id = tf.Table_db_id
        ORDER BY tf.floor_name, t.table_capacity, t.Table_number
    """)
    all_tables = cursor.fetchall()

    # --- FETCH STATUSES ---
    cursor.execute("SELECT * FROM reservation_status")
    statuses = cursor.fetchall()

    # --- FETCH ALL RESERVATIONS ---
    cursor.execute("""
        SELECT
            trl.table_id,
            tr.reservation_id,
            tr.number_of_people,
            tr.reservation_notes,
            tr.resservation_date,
            tr.reservation_time,
            trs.reservation_status_id,
            tr.Datetime_reservation_was_made
        FROM table_reservations tr
        JOIN table_reservation_link trl
          ON tr.reservation_id = trl.reservation_id
        JOIN table_reservation_status trs
          ON tr.reservation_id = trs.reservation_id
        ORDER BY tr.resservation_date, tr.reservation_time
    """)
    rows = cursor.fetchall()

    # --- GROUP RESERVATIONS BY TABLE ---
    reservation_dict = {}
    for r in rows:
        table_id = r["table_id"]
        if table_id not in reservation_dict:
            reservation_dict[table_id] = []
        reservation_dict[table_id].append(r)

    cursor.close()
    conn.close()

    # --- GROUP TABLES BY FLOOR AND CAPACITY ---
    tables_by_floor = {}
    for table in all_tables:
        floor = table['floor_name'] or 'Unassigned'
        if floor not in tables_by_floor:
            tables_by_floor[floor] = {}
        capacity = table['table_capacity']
        if capacity not in tables_by_floor[floor]:
            tables_by_floor[floor][capacity] = []
        tables_by_floor[floor][capacity].append(table)

    return render_template(
        'activity_Tables.html',
        user=user_info,
        tables_by_floor=tables_by_floor,
        tables=all_tables,
        floor_dict={t['Table_db_id']: t['floor_name'] for t in all_tables},
        statuses=statuses,
        reservation_dict=reservation_dict,
        datetime_now=datetime.now(),
        error_msg=error_msg
    )

@app.route('/audit_logs')
def audit_logs():
    # Fetch logs or render template
    return render_template('audit_logs.html')

@app.route('/get_audit_logs')
def get_audit_logs():
    # Connect to database
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # SQL query to join Audit_Logs -> audit_desc -> Description_audit
    query = """
    SELECT 
        a.audit_reference_number,
        d.Description_Title AS description,
        a.action,
        a.audit_date,
        a.audit_time,
        a.done_by
    FROM Audit_Logs a
    LEFT JOIN audit_desc ad ON a.audit_ID = ad.audit_ID
    LEFT JOIN Description_audit d ON ad.description_audit_id = d.description_audit_id
    ORDER BY a.audit_ID ASC
    """
    
    cursor.execute(query)
    result = cursor.fetchall()
    
    cursor.close()
    conn.close()

    # Convert date and time objects to strings properly
    for row in result:
        if isinstance(row['audit_date'], (datetime,)):
            row['audit_date'] = row['audit_date'].strftime('%Y-%m-%d')
        if isinstance(row['audit_time'], (datetime,)):
            row['audit_time'] = row['audit_time'].strftime('%H:%M:%S')
        elif isinstance(row['audit_time'], timedelta):
            total_seconds = int(row['audit_time'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            row['audit_time'] = f"{hours:02}:{minutes:02}:{seconds:02}"

    # Now jsonify will work because all datetime/timedelta objects are converted to strings
    return jsonify(result)

@app.route('/get_tables_display', methods=['GET'])
def get_tables_display():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all tables with their floor info
    cursor.execute("""
        SELECT 
            t.Table_db_id,
            t.Table_number,
            t.table_capacity,
            tf.floor_name
        FROM tables t
        LEFT JOIN table_floor tf ON t.Table_db_id = tf.Table_db_id
        ORDER BY t.Table_number ASC
    """)

    tables = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(tables)

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
    customer_name = data.get('customer_name')
    table_id = data.get('table_id')
    order_items = data.get('order_items')
    order_desc = data.get('order_desc')
    unique_goods_count = data.get('unique_goods_count', len(order_items))  # fallback to total items if missing
   
    # Validate required fields
    if not  order_type_val or not customer_name or not table_id or not order_items:
        return jsonify({"success": False, "error": "Missing required fields"})

    user_id = session['user_id']
    user_name= session['user_name']
    personal_name= session['personal_name']
    job_desc= session['job_desc']

    now = datetime.now()
    current_date = now.date()
    current_time = now.time()

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 1️⃣ Insert into orders_improved_table
        items_count = sum(item['quantity'] for item in order_items)
        total_amount = sum(item['quantity'] * item['price_at_order'] for item in order_items)
        
        order_number = generate_next_order_number()


        cursor.execute("""
            INSERT INTO orders_improved_table (
                order_identification_number,
                items_count,
                order_desc,
                user_id,
                Total_ammount,
                DATE,
                TIME,
                LAST_UPDATE
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            order_number,
            unique_goods_count,
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
        """, (order_type_val,))  # <-- make sure order_type_val is the name sent from JS
        category_row = cursor.fetchone()
        if not category_row:
            raise ValueError(f"Invalid order category selected: {order_type_val}")

        order_categories_ID = category_row['order_categories_ID']

                   
        # 3️⃣ Insert into order_with_categories
        cursor.execute("""
            INSERT INTO order_with_categories (order_ID, order_categories_ID)
            VALUES (%s, %s)
        """, (order_id, order_categories_ID))

         # 4️⃣ Insert into customer_order
        cursor.execute("""
            INSERT INTO customer_order (order_ID, customer_name,Table_db_id)
            VALUES (%s, %s, %s)
        """, (order_id, customer_name,table_id))


        order_type_val = data.get('order_type')

        for item in order_items:
            good_name = item['good_name']
            quantity = item['quantity']
            price_at_order = item['price_at_order']  # already price * quantity

            # Get product number
            cursor.execute("SELECT good_number FROM products WHERE good_name = %s", (good_name,))
            product_row = cursor.fetchone()
            if not product_row:
                continue  # skip missing products

            good_number = product_row['good_number']

            # Optional: validate category exists
            cursor.execute("""
                SELECT order_categories_ID 
                FROM order_categories 
                WHERE order_categories_name = %s
            """, (order_type_val,))
            category_row = cursor.fetchone()
            if not category_row:
                raise ValueError(f"Invalid order category selected: {order_type_val}")

            # Insert into order_detials
            cursor.execute("""
                INSERT INTO order_detials 
                (order_refrence_number, product_purchased, item_quantities, order_detials, Total)
                VALUES (%s, %s, %s, %s, %s)
            """, (order_id, good_number, quantity, order_type_val, price_at_order))
            
        cursor.execute("""
            INSERT INTO order_with_state 
            (order_ID, order_status_id, LAST_UPDATE)
            VALUES (%s, %s, %s)
            """, (order_id, 1, now))
        
        # 🔐 AUDIT LOG FOR ORDER PLACEMENT

        # Get description_audit_id for ORDER
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT description_audit_id FROM Description_audit WHERE Description_Title = %s",
            ("ORDER",)
        )
        desc = cursor.fetchone()

        if desc:
            description_audit_id = desc['description_audit_id']

            audit_now = datetime.now()
            audit_date = audit_now.date()
            audit_time = audit_now.time().replace(microsecond=0)

            # Insert temporary audit log
            cursor.execute("""
                INSERT INTO Audit_Logs (
                    audit_reference_number,
                    action,
                    audit_date,
                    audit_time,
                    done_by
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                "TEMP",
                "",
                audit_date,
                audit_time,
                f"{user_id}---{personal_name}---{user_name}"
            ))
            conn.commit()

            audit_ID = cursor.lastrowid

            # Generate reference number
            audit_reference_number = f"#{audit_ID}.{user_id}.{description_audit_id}"

            action_text = (
                f"Order #{order_number} placed by {user_name} ({job_desc}). "
                f"Customer: {customer_name}, "
                f"Order Type: {order_type_val}, "
                f"Items Count: {unique_goods_count}, "
                f"Total Amount: {total_amount:.2f}, "
                f"Table ID: {table_id}"
            )

            # Update audit log
            cursor.execute("""
                UPDATE Audit_Logs
                SET audit_reference_number=%s,
                    action=%s
                WHERE audit_ID=%s
            """, (audit_reference_number, action_text, audit_ID))

            # Link audit to description
            cursor.execute("""
                INSERT INTO audit_desc (audit_ID, description_audit_id)
                VALUES (%s, %s)
            """, (audit_ID, description_audit_id))

            conn.commit()

        # Commit all inserts
        conn.commit()
        cursor.close()
        conn.close()
        
        # ✅ Generate a new order number for the next order
        # this updates order_history.json

        return jsonify({"success": True, "order_id": order_id})

    except Exception as e:
        print("Database Error:", e)
        return jsonify({"success": False, "error": str(e)})

@app.route('/get_today_orders_display', methods=['GET'])
def get_today_orders_display():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.order_ID,
            o.order_identification_number,
            c.customer_name,
            o.TIME,
            o.items_count,
            o.Total_ammount,
            o.LAST_UPDATE AS order_last_update,
            (SELECT GROUP_CONCAT(oc.order_categories_name)
             FROM order_with_categories owc
             JOIN order_categories oc 
               ON owc.order_categories_ID = oc.order_categories_ID
             WHERE owc.order_ID = o.order_ID
            ) AS order_categories_name,
            (SELECT os.order_status
             FROM order_with_state ow
             JOIN order_status os 
               ON ow.order_status_id = os.order_status_id
             WHERE ow.order_ID = o.order_ID
             ORDER BY ow.LAST_UPDATE DESC
             LIMIT 1
            ) AS order_status,
            (SELECT ow.LAST_UPDATE
             FROM order_with_state ow
             WHERE ow.order_ID = o.order_ID
             ORDER BY ow.LAST_UPDATE DESC
             LIMIT 1
            ) AS order_state_last_update
        FROM orders_improved_table o
        JOIN customer_order c 
          ON o.order_ID = c.order_ID
        WHERE DATE(o.DATE) = CURDATE()
        ORDER BY o.TIME ASC
    """)

    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    # Ensure TIME is string
    for row in orders:
        if isinstance(row['TIME'], datetime):
            row['TIME'] = row['TIME'].strftime("%H:%M:%S")
        elif isinstance(row['TIME'], timedelta):
            total_seconds = int(row['TIME'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            row['TIME'] = f"{hours:02}:{minutes:02}:{seconds:02}"

    return jsonify(orders)

@app.route('/get_next_order_number')
def get_next_order_number_route():
    try:
        order_number = generate_next_order_number()
        return jsonify({"order_number": order_number})
    except Exception as e:
        return jsonify({"error": str(e)})

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

@app.route('/get_all_order_status')
def get_all_order_status():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)  # dictionary so keys are column names
    cursor.execute("SELECT order_status_id, order_status FROM order_status")
    statuses = cursor.fetchall()  # This is a list of dicts: [{'order_status_id':1,'order_status':'Pending'}, ...]
    cursor.close()
    conn.close()
    return jsonify(statuses)

from flask import Flask, jsonify, session
from datetime import datetime, timedelta
from flask import jsonify
from datetime import datetime, timedelta

@app.route('/order_display_cards')
def order_display_cards():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            o.order_ID,
            co.customer_name,
            t.Table_number,
            oc.order_categories_name,
            o.TIME,
            p.good_name,
            od.item_quantities,
            o.items_count,

            (
                SELECT os.order_status
                FROM order_with_state ow
                JOIN order_status os
                  ON ow.order_status_id = os.order_status_id
                WHERE ow.order_ID = o.order_ID
                ORDER BY ow.LAST_UPDATE DESC
                LIMIT 1
            ) AS order_status,

            (
                SELECT ow.LAST_UPDATE
                FROM order_with_state ow
                WHERE ow.order_ID = o.order_ID
                ORDER BY ow.LAST_UPDATE DESC
                LIMIT 1
            ) AS order_status_time

        FROM orders_improved_table o
        LEFT JOIN customer_order co ON o.order_ID = co.order_ID
        LEFT JOIN tables t ON co.Table_db_id = t.Table_db_id
        LEFT JOIN order_with_categories owc ON o.order_ID = owc.order_ID
        LEFT JOIN order_categories oc ON owc.order_categories_ID = oc.order_categories_ID
        LEFT JOIN order_detials od ON o.order_ID = od.order_refrence_number
        LEFT JOIN products p ON od.product_purchased = p.good_number
        ORDER BY o.TIME DESC
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    orders = {}

    for row in rows:
        order_id = row['order_ID']

        # TIME conversion
        time_value = row['TIME']
        if isinstance(time_value, datetime):
            time_value = time_value.strftime("%H:%M:%S")
        elif isinstance(time_value, timedelta):
            total = int(time_value.total_seconds())
            time_value = f"{total//3600:02}:{(total%3600)//60:02}:{total%60:02}"

        if order_id not in orders:
            orders[order_id] = {
                'order_ID': order_id,
                'customer_name': row['customer_name'] or "",
                'table_number': row['Table_number'] or "",
                'category': row['order_categories_name'] or "",
                'time': time_value,
                'items_count': row['items_count'] or 0,
                'order_status': row['order_status'] or "pending",
                'order_status_time': (
                    row['order_status_time'].strftime("%Y-%m-%d %H:%M:%S")
                    if row['order_status_time'] else ""
                ),
                'items': []
            }

        if row['good_name']:
            orders[order_id]['items'].append({
                'good_name': row['good_name'],
                'quantity': row['item_quantities']
            })

    return jsonify(list(orders.values()))

@app.route('/billing_queue_display')
def billing_queue_display():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            o.order_ID,
            o.order_identification_number,
            o.Total_ammount,
            o.DATE,
            co.customer_name,
            t.Table_number,

            (
                SELECT os.order_status
                FROM order_with_state ow
                JOIN order_status os
                  ON ow.order_status_id = os.order_status_id
                WHERE ow.order_ID = o.order_ID
                ORDER BY ow.LAST_UPDATE DESC
                LIMIT 1
            ) AS latest_status,

            (
                SELECT ow.LAST_UPDATE
                FROM order_with_state ow
                WHERE ow.order_ID = o.order_ID
                ORDER BY ow.LAST_UPDATE DESC
                LIMIT 1
            ) AS status_time

        FROM orders_improved_table o
        LEFT JOIN customer_order co
            ON o.order_ID = co.order_ID
        LEFT JOIN tables t
            ON co.Table_db_id = t.Table_db_id
        ORDER BY o.DATE DESC
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in rows:
        # format date
        if isinstance(row['DATE'], datetime):
            row['DATE'] = row['DATE'].strftime("%Y-%m-%d %H:%M:%S")

        # pill logic
        if row['latest_status'] in ('pending', 'in_progress'):
            row['pill_text'] = 'ACTIVE'
            row['pill_class'] = 'pill-active'
        else:
            row['pill_text'] = 'CLOSED'
            row['pill_class'] = 'pill-closed'

    return jsonify(rows)

@app.route('/update_order_status', methods=['POST'])
def update_order_status():
    data = request.json
    order_ident_number = data.get('order_identification_number')
    new_status_id = data.get('order_status_id')

    if not order_ident_number or not new_status_id:
        return jsonify({'success': False, 'message': 'Missing order_identification_number or order_status_id'}), 400

    conn = get_connection()
    cursor = conn.cursor()

    # Get order_ID from orders_improved_table
    cursor.execute("""
        SELECT order_ID FROM orders_improved_table
        WHERE order_identification_number = %s
    """, (order_ident_number,))
    result = cursor.fetchone()

    if not result:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Order not found'}), 404

    order_id = result[0]

    # Insert new status into order_with_state
    cursor.execute("""
        INSERT INTO order_with_state (order_ID, order_status_id, LAST_UPDATE)
        VALUES (%s, %s, %s)
    """, (order_id, new_status_id, datetime.now()))

    # Update orders_improved_table.LAST_UPDATE
    cursor.execute("""
        UPDATE orders_improved_table
        SET LAST_UPDATE = %s
        WHERE order_ID = %s
    """, (datetime.now(), order_id))

     # Get description_audit_id for ORDER
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
            "SELECT description_audit_id FROM Description_audit WHERE Description_Title = %s",
            ("ORDER",)
        )
    desc = cursor.fetchone()
    
    if desc:
            description_audit_id = desc['description_audit_id']
            user_id = session['user_id']
            user_name= session['user_name']
            personal_name= session['personal_name']
            job_desc= session['job_desc']
            audit_now = datetime.now()
            audit_date = audit_now.date()
            audit_time = audit_now.time().replace(microsecond=0)

            # Insert temporary audit log
            cursor.execute("""
                INSERT INTO Audit_Logs (
                    audit_reference_number,
                    action,
                    audit_date,
                    audit_time,
                    done_by
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                "TEMP",
                "",
                audit_date,
                audit_time,
                f"{user_id}---{personal_name}---{user_name}"
            ))
           
    
            audit_ID = cursor.lastrowid

            # Generate reference number
            audit_reference_number = f"#{audit_ID}.{user_id}.{description_audit_id}"

            action_text = (
                f"Order #{order_ident_number} status ID Changed by {user_name} ({job_desc}). "
                f"Status new ID: {new_status_id} "
            )       
             # Update audit log
            cursor.execute("""
                UPDATE Audit_Logs
                SET audit_reference_number=%s,
                    action=%s
                WHERE audit_ID=%s
            """, (audit_reference_number, action_text, audit_ID))

            # Link audit to description
            cursor.execute("""
                INSERT INTO audit_desc (audit_ID, description_audit_id)
                VALUES (%s, %s)
            """, (audit_ID, description_audit_id))

            conn.commit()
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/save_table_reservation', methods=['POST'])
def save_table_reservation():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    data = request.json
    user_id = session['user_id']

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1️⃣ Insert into table_reservations
        cursor.execute("""
            INSERT INTO table_reservations
            (number_of_people, reservation_notes, resservation_date, reservation_time, Datetime_reservation_was_made)
            VALUES (%s, %s, %s, %s, NOW())
        """, (
            data['number_of_people'],
            data['reservation_notes'],
            data['reservation_date'],  # frontend key matches, DB column = resservation_date
            data['reservation_time']
        ))

        reservation_id = cursor.lastrowid

        # 2️⃣ Insert into table_reservation_status
        cursor.execute("""
            INSERT INTO table_reservation_status
            (reservation_id, reservation_status_id, datetime_of_status)
            VALUES (%s, %s, NOW())
        """, (
            reservation_id,
            2
        ))

        # 3️⃣ Insert into customer_table_reservations
        cursor.execute("""
            INSERT INTO customer_table_reservations
            (reservation_id, customer_name)
            VALUES (%s, %s)
        """, (
            reservation_id,
            data['customer_name']
        ))

        # 4️⃣ Insert into user_reservations
        cursor.execute("""
            INSERT INTO user_reservations
            (user_id, reservation_id)
            VALUES (%s, %s)
        """, (
            user_id,
            reservation_id
        ))

        cursor.execute("""
            INSERT INTO table_reservation_link
            (table_id, reservation_id)
            VALUES (%s, %s)
        """, (
            data['table_id'],  # table selected from frontend
            reservation_id
        ))

        conn.commit()
        return jsonify({'success': True, 'reservation_id': reservation_id})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})

    finally:
        cursor.close()
        conn.close()

@app.route('/update_reservation_status', methods=['POST'])
def update_reservation_status():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    data = request.json
    reservation_id = data.get('reservation_id')
    new_status_id = data.get('reservation_status_id')

    if not reservation_id or not new_status_id:
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO table_reservation_status (reservation_id, reservation_status_id, datetime_of_status)
            VALUES (%s, %s, NOW())
        """, (reservation_id, new_status_id))

        conn.commit()
        return jsonify({'success': True})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})

    finally:
        cursor.close()
        conn.close()

@app.route('/newUpdateTable_reservation_display')
def newUpdateTable_reservation_display():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
         
                SELECT
    tr.reservation_id,
    ur.user_id,
    u.user_name AS entered_by,
    ctr.customer_name,
    t.Table_number,
    tf.floor_name,
    tr.number_of_people,
    tr.reservation_notes,
    tr.resservation_date,
    tr.reservation_time,
    tr.Datetime_reservation_was_made,

    -- 👇 now both ID + NAME
    latest_status.reservation_status_id,
    latest_status.status_name

FROM table_reservations tr

LEFT JOIN table_reservation_link trl
    ON tr.reservation_id = trl.reservation_id
LEFT JOIN tables t
    ON trl.table_id = t.Table_db_id
LEFT JOIN table_floor tf
    ON trl.table_id = tf.Table_db_id
LEFT JOIN user_reservations ur
    ON tr.reservation_id = ur.reservation_id
LEFT JOIN user u
    ON ur.user_id = u.user_id
LEFT JOIN customer_table_reservations ctr
    ON tr.reservation_id = ctr.reservation_id

LEFT JOIN (
    SELECT
        trs1.reservation_id,
        trs1.reservation_status_id,
        rs.status_name
    FROM table_reservation_status trs1
    JOIN reservation_status rs
        ON rs.reservation_status_id = trs1.reservation_status_id
    JOIN (
        SELECT reservation_id, MAX(datetime_of_status) AS max_date
        FROM table_reservation_status
        GROUP BY reservation_id
    ) trs2
        ON trs1.reservation_id = trs2.reservation_id
       AND trs1.datetime_of_status = trs2.max_date
) latest_status
    ON tr.reservation_id = latest_status.reservation_id;


        """)


        rows = cursor.fetchall()
        reservations = []

        for row in rows:
            # ---- DATE stringify
            date_value = row['resservation_date']
            if isinstance(date_value, datetime):
                date_value = date_value.strftime("%Y-%m-%d")
            else:
                date_value = str(date_value) if date_value else ""

            # ---- TIME stringify
            time_value = row['reservation_time']
            if isinstance(time_value, datetime):
                time_value = time_value.strftime("%H:%M:%S")
            elif isinstance(time_value, timedelta):
                total = int(time_value.total_seconds())
                time_value = f"{total//3600:02}:{(total%3600)//60:02}:{total%60:02}"
            else:
                time_value = str(time_value) if time_value else ""

            # ---- DATETIME stringify
            completed_value = row['Datetime_reservation_was_made']
            if isinstance(completed_value, datetime):
                completed_value = completed_value.strftime("%Y-%m-%d %H:%M:%S")
            else:
                completed_value = str(completed_value) if completed_value else ""

            reservations.append({
                "reservation_id": row['reservation_id'],
                "user_id": row['user_id'],
                "customer_name": row['customer_name'] or "",
                "Table_number": row['Table_number'] or "",
                "floor_name": row['floor_name'] or "",
                "entered_by": row['entered_by'] or "",
                "number_of_people": row['number_of_people'] or 0,
                "reservation_notes": row['reservation_notes'] or "",
                "resservation_date": date_value,
                "reservation_time": time_value,
                "Datetime_reservation_was_made": completed_value,
                "reservation_status_id": row['reservation_status_id'],
                "reservation_status_name": row['status_name'] or ""
               
            })

        return jsonify(reservations)

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == "__main__":
 app.run(debug=True)
 





































