from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
import sqlite3
import csv
import io
import os
import pandas as pd
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max file size

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize database
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    position TEXT,
                    package REAL
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    branch TEXT,
                    year INTEGER,
                    resume TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS placements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    company_id INTEGER,
                    FOREIGN KEY(student_id) REFERENCES students(id),
                    FOREIGN KEY(company_id) REFERENCES companies(id)
                )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_company', methods=['GET', 'POST'])
def add_company():
    if request.method == 'POST':
        name = request.form['name']
        position = request.form['position']
        package = request.form['package']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO companies (name, position, package) VALUES (?, ?, ?)", (name, position, package))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_company.html')

@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        branch = request.form['branch']
        year = request.form['year']
        resume_file = request.files.get('resume')

        filename = None
        if resume_file and resume_file.filename.endswith('.pdf'):
            filename = secure_filename(resume_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume_file.save(filepath)

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO students (name, branch, year, resume) VALUES (?, ?, ?, ?)", (name, branch, year, filename))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_student.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/place_student', methods=['GET', 'POST'])
def place_student():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    students = c.execute("SELECT * FROM students").fetchall()
    companies = c.execute("SELECT * FROM companies").fetchall()
    conn.close()
    if request.method == 'POST':
        student_id = request.form['student_id']
        company_id = request.form['company_id']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO placements (student_id, company_id) VALUES (?, ?)", (student_id, company_id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('place_student.html', students=students, companies=companies)

@app.route('/view_records')
def view_records():
    name = request.args.get('name', '')
    branch = request.args.get('branch', '')
    year = request.args.get('year', '')
    company = request.args.get('company', '')
    placed = request.args.get('placed', '')
    sort_by = request.args.get('sort_by', '')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    sql = '''
        SELECT students.name, students.branch, students.year,
               companies.name, companies.position, companies.package,
               students.resume
        FROM placements
        JOIN students ON placements.student_id = students.id
        JOIN companies ON placements.company_id = companies.id
        WHERE 1=1
    '''
    params = []

    if name:
        sql += " AND students.name LIKE ?"
        params.append(f'%{name}%')
    if branch:
        sql += " AND students.branch LIKE ?"
        params.append(f'%{branch}%')
    if year:
        sql += " AND students.year = ?"
        params.append(year)
    if company:
        sql += " AND companies.name LIKE ?"
        params.append(f'%{company}%')
    if sort_by == "package":
        sql += " ORDER BY companies.package DESC"
    elif sort_by == "company":
        sql += " ORDER BY companies.name ASC"

    records = c.execute(sql, params).fetchall()

    unplaced_students = []
    if placed == "unplaced":
        unplaced_students = c.execute('''
            SELECT name, branch, year FROM students
            WHERE id NOT IN (SELECT student_id FROM placements)
        ''').fetchall()

    conn.close()

    return render_template('view_records.html', records=records, unplaced=unplaced_students)

@app.route('/export_placements')
def export_placements():
    export_type = request.args.get('type', 'csv')
    name = request.args.get('name', '')
    branch = request.args.get('branch', '')
    year = request.args.get('year', '')
    company = request.args.get('company', '')
    placed = request.args.get('placed', '')
    sort_by = request.args.get('sort_by', '')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if placed == 'unplaced':
        query = '''SELECT name, branch, year FROM students
                   WHERE id NOT IN (SELECT student_id FROM placements)'''
        data = c.execute(query).fetchall()
        headers = ['Student Name', 'Branch', 'Year']
    else:
        sql = '''
            SELECT students.name, students.branch, students.year,
                   companies.name, companies.position, companies.package
            FROM placements
            JOIN students ON placements.student_id = students.id
            JOIN companies ON placements.company_id = companies.id
            WHERE 1=1
        '''
        params = []
        if name:
            sql += " AND students.name LIKE ?"
            params.append(f'%{name}%')
        if branch:
            sql += " AND students.branch LIKE ?"
            params.append(f'%{branch}%')
        if year:
            sql += " AND students.year = ?"
            params.append(year)
        if company:
            sql += " AND companies.name LIKE ?"
            params.append(f'%{company}%')
        if sort_by == "package":
            sql += " ORDER BY companies.package DESC"
        elif sort_by == "company":
            sql += " ORDER BY companies.name ASC"
        data = c.execute(sql, params).fetchall()
        headers = ['Student Name', 'Branch', 'Year', 'Company Name', 'Position', 'Package']

    conn.close()

    df = pd.DataFrame(data, columns=headers)

    if export_type == 'excel':
        raw_output = io.BytesIO()
        with pd.ExcelWriter(raw_output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Placements')
        raw_output.seek(0)
        return send_file(
            io.BytesIO(raw_output.read()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name='placement_records.xlsx',
            as_attachment=True
        )
    else:
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', download_name='placement_records.csv', as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
