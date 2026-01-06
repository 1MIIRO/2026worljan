from flask import Flask, request, jsonify, render_template, render_template_string, session, redirect, url_for
import mysql.connector
from mysql.connector import Error
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Required for sessions

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

    return render_template('dashboard.html', user=user_info, products=products,tables=tables)

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
    data = request.get_json()
    order_number = data.get('order_number')
    order_type = data.get('order_type')  # dine_in / takeaway
    customer_name = data.get('customer_name')  # from <div id="customerName">
    table_id = data.get('table_id')  # from dropdown

    if not order_number or not order_type:
        return jsonify({"success": False, "error": "Missing required fields"})

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1️⃣ Insert into order_table
        cursor.execute("""
            INSERT INTO order_table (order_number, Dateandtime_ordered)
            VALUES (%s, %s)
        """, (order_number, datetime.now()))
        order_db_id = cursor.lastrowid

        # 2️⃣ Insert into order_types
        cursor.execute("""
            INSERT INTO order_types (order_db_id, order_type)
            VALUES (%s, %s)
        """, (order_db_id, order_type))

        # 3️⃣ Insert into customer_ORDER_STATUS
        # Default order_status = 'All done'
        cursor.execute("""
            INSERT INTO customer_ORDER_STATUS (customer_name, customer_table,  order_db_id,order_status )
            VALUES (%s, %s, %s)
        """, (customer_name, table_id,order_db_id, 'All done'))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True})

    except Error as e:
        print("Database Error:", e)
        return jsonify({"success": False, "error": str(e)})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == "__main__":
 app.run(debug=True)
 