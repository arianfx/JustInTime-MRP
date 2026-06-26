from __future__ import annotations

import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    g,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'app.db'

USER_CREDENTIALS = {
    'admin': 'admin123',
    'manager': 'manager123',
    'stamper': 'stamper123',
}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'justintimerp-secret-key')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query: str, args=(), one=False):
    cur = get_db().execute(query, args)
    result = cur.fetchall()
    cur.close()
    return (result[0] if result else None) if one else result


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            capacity TEXT NOT NULL
        );
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS operators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            certification TEXT NOT NULL,
            shift TEXT NOT NULL
        );
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material TEXT NOT NULL,
            quantity TEXT NOT NULL,
            supplier TEXT NOT NULL,
            stock_status TEXT NOT NULL
        );
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT NOT NULL,
            machine TEXT NOT NULL,
            operator TEXT NOT NULL,
            material TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL
        );
        '''
    )

    if cur.execute('SELECT COUNT(1) FROM machines').fetchone()[0] == 0:
        cur.executemany(
            'INSERT INTO machines (name, type, status, capacity) VALUES (?, ?, ?, ?)',
            [
                ('Laser Cutter', 'Cutting', 'Online', '8 units/hr'),
                ('Press Brake', 'Forming', 'Maintenance', '12 tons'),
                ('Injection Molder', 'Molding', 'Online', '140 cycles/day'),
                ('Assembly Robot', 'Assembly', 'Online', '20 tasks/hr'),
            ],
        )

    if cur.execute('SELECT COUNT(1) FROM operators').fetchone()[0] == 0:
        cur.executemany(
            'INSERT INTO operators (name, certification, shift) VALUES (?, ?, ?)',
            [
                ('Alice Johnson', 'Welding', 'Day'),
                ('Diego Ramirez', 'CNC', 'Night'),
                ('Mina Patel', 'Assembly', 'Swing'),
                ('Samuel Grant', 'Quality', 'Day'),
            ],
        )

    if cur.execute('SELECT COUNT(1) FROM materials').fetchone()[0] == 0:
        cur.executemany(
            'INSERT INTO materials (material, quantity, supplier, stock_status) VALUES (?, ?, ?, ?)',
            [
                ('Steel Sheet', '320 kg', 'Titan Metals', 'In Stock'),
                ('ABS Resin', '150 kg', 'PetroCore', 'Low Stock'),
                ('Copper Wire', '60 kg', 'ElectroSupply', 'In Stock'),
                ('Fasteners', '2000 pcs', 'BoltWorks', 'In Stock'),
            ],
        )

    if cur.execute('SELECT COUNT(1) FROM jobs').fetchone()[0] == 0:
        cur.executemany(
            'INSERT INTO jobs (product, machine, operator, material, due_date, status) VALUES (?, ?, ?, ?, ?, ?)',
            [
                ('FloatFry Housing', 'Injection Molder', 'Mina Patel', 'ABS Resin', '2026-07-05', 'Planned'),
                ('Control Panel', 'Assembly Robot', 'Samuel Grant', 'Copper Wire', '2026-07-08', 'In Progress'),
                ('Brake Frame', 'Press Brake', 'Diego Ramirez', 'Steel Sheet', '2026-07-10', 'Scheduled'),
            ],
        )

    db.commit()
    cur.close()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('login'))
        return view(*args, **kwargs)

    return wrapped_view


@app.route('/')
def home():
    if session.get('user'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if USER_CREDENTIALS.get(username) == password:
            session['user'] = username
            session['role'] = username.capitalize()
            flash('Welcome back, %s!' % username.title(), 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    machines = query_db('SELECT COUNT(1) AS count FROM machines', one=True)['count']
    operators = query_db('SELECT COUNT(1) AS count FROM operators', one=True)['count']
    materials = query_db('SELECT COUNT(1) AS count FROM materials', one=True)['count']
    jobs = query_db('SELECT COUNT(1) AS count FROM jobs', one=True)['count']

    return render_template(
        'dashboard.html',
        machines=machines,
        operators=operators,
        materials=materials,
        jobs=jobs,
    )


@app.route('/machines', methods=['GET', 'POST'])
@login_required
def machines():
    db = get_db()

    if request.method == 'POST':
        machine_id = request.form.get('id')
        name = request.form.get('name', '').strip()
        type_ = request.form.get('type', '').strip()
        status = request.form.get('status', '').strip()
        capacity = request.form.get('capacity', '').strip()

        if machine_id:
            db.execute(
                'UPDATE machines SET name = ?, type = ?, status = ?, capacity = ? WHERE id = ?',
                (name, type_, status, capacity, machine_id),
            )
            flash('Machine updated successfully.', 'success')
        else:
            db.execute(
                'INSERT INTO machines (name, type, status, capacity) VALUES (?, ?, ?, ?)',
                (name, type_, status, capacity),
            )
            flash('Machine added successfully.', 'success')

        db.commit()
        return redirect(url_for('machines'))

    delete_id = request.args.get('delete')
    if delete_id:
        db.execute('DELETE FROM machines WHERE id = ?', (delete_id,))
        db.commit()
        flash('Machine deleted successfully.', 'warning')
        return redirect(url_for('machines'))

    edit_id = request.args.get('edit')
    machine = query_db('SELECT * FROM machines WHERE id = ?', (edit_id,), one=True) if edit_id else None
    items = query_db('SELECT * FROM machines ORDER BY name')
    return render_template('machines.html', machines=items, machine=machine)


@app.route('/operators', methods=['GET', 'POST'])
@login_required
def operators():
    db = get_db()

    if request.method == 'POST':
        operator_id = request.form.get('id')
        name = request.form.get('name', '').strip()
        certification = request.form.get('certification', '').strip()
        shift = request.form.get('shift', '').strip()

        if operator_id:
            db.execute(
                'UPDATE operators SET name = ?, certification = ?, shift = ? WHERE id = ?',
                (name, certification, shift, operator_id),
            )
            flash('Operator updated successfully.', 'success')
        else:
            db.execute(
                'INSERT INTO operators (name, certification, shift) VALUES (?, ?, ?)',
                (name, certification, shift),
            )
            flash('Operator added successfully.', 'success')

        db.commit()
        return redirect(url_for('operators'))

    delete_id = request.args.get('delete')
    if delete_id:
        db.execute('DELETE FROM operators WHERE id = ?', (delete_id,))
        db.commit()
        flash('Operator deleted successfully.', 'warning')
        return redirect(url_for('operators'))

    edit_id = request.args.get('edit')
    operator = query_db('SELECT * FROM operators WHERE id = ?', (edit_id,), one=True) if edit_id else None
    items = query_db('SELECT * FROM operators ORDER BY name')
    return render_template('operators.html', operators=items, operator=operator)


@app.route('/materials', methods=['GET', 'POST'])
@login_required
def materials():
    db = get_db()

    if request.method == 'POST':
        material_id = request.form.get('id')
        material = request.form.get('material', '').strip()
        quantity = request.form.get('quantity', '').strip()
        supplier = request.form.get('supplier', '').strip()
        stock_status = request.form.get('stock_status', '').strip()

        if material_id:
            db.execute(
                'UPDATE materials SET material = ?, quantity = ?, supplier = ?, stock_status = ? WHERE id = ?',
                (material, quantity, supplier, stock_status, material_id),
            )
            flash('Material updated successfully.', 'success')
        else:
            db.execute(
                'INSERT INTO materials (material, quantity, supplier, stock_status) VALUES (?, ?, ?, ?)',
                (material, quantity, supplier, stock_status),
            )
            flash('Material added successfully.', 'success')

        db.commit()
        return redirect(url_for('materials'))

    delete_id = request.args.get('delete')
    if delete_id:
        db.execute('DELETE FROM materials WHERE id = ?', (delete_id,))
        db.commit()
        flash('Material deleted successfully.', 'warning')
        return redirect(url_for('materials'))

    edit_id = request.args.get('edit')
    material = query_db('SELECT * FROM materials WHERE id = ?', (edit_id,), one=True) if edit_id else None
    items = query_db('SELECT * FROM materials ORDER BY material')
    return render_template('materials.html', materials=items, material=material)


@app.route('/jobs', methods=['GET', 'POST'])
@login_required
def jobs():
    db = get_db()

    machines_list = query_db('SELECT name FROM machines ORDER BY name')
    operators_list = query_db('SELECT name FROM operators ORDER BY name')
    materials_list = query_db('SELECT material FROM materials ORDER BY material')

    if request.method == 'POST':
        job_id = request.form.get('id')
        product = request.form.get('product', '').strip()
        machine = request.form.get('machine', '').strip()
        operator = request.form.get('operator', '').strip()
        material = request.form.get('material', '').strip()
        due_date = request.form.get('due_date', '').strip()
        status = request.form.get('status', '').strip()

        if job_id:
            db.execute(
                'UPDATE jobs SET product = ?, machine = ?, operator = ?, material = ?, due_date = ?, status = ? WHERE id = ?',
                (product, machine, operator, material, due_date, status, job_id),
            )
            flash('Production job updated successfully.', 'success')
        else:
            db.execute(
                'INSERT INTO jobs (product, machine, operator, material, due_date, status) VALUES (?, ?, ?, ?, ?, ?)',
                (product, machine, operator, material, due_date, status),
            )
            flash('Production job added successfully.', 'success')

        db.commit()
        return redirect(url_for('jobs'))

    delete_id = request.args.get('delete')
    if delete_id:
        db.execute('DELETE FROM jobs WHERE id = ?', (delete_id,))
        db.commit()
        flash('Production job deleted successfully.', 'warning')
        return redirect(url_for('jobs'))

    edit_id = request.args.get('edit')
    job = query_db('SELECT * FROM jobs WHERE id = ?', (edit_id,), one=True) if edit_id else None
    items = query_db('SELECT * FROM jobs ORDER BY due_date')
    return render_template(
        'jobs.html',
        jobs=items,
        job=job,
        machines=machines_list,
        operators=operators_list,
        materials=materials_list,
    )


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
