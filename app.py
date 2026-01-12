from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from flask_bcrypt import Bcrypt 
from config.db import get_db_connection

app = Flask(__name__)

# CONFIGURACIÓN DE SEGURIDAD
app.secret_key = "tesis_mauricio_secret_key" # Necesario para guardar la sesión
bcrypt = Bcrypt(app) # Inicializar encriptador

# --- RUTA DE INICIO ---
@app.route('/')
def home():
    return render_template('home.html')

# --- RUTA DEL PANEL DE CONTROL (DASHBOARD) ---
# Aquí solo entran los que iniciaron sesión
@app.route('/dashboard')
def dashboard():
    # 1. Protección: Solo entra si está logueado
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', 
                           rut_usuario=session['user_rut'], 
                           id_rol=session['user_role'])
  

# --- RUTA DE LOGIN (LA LÓGICA REAL) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        rut_form = request.form['rut']
        clave_form = request.form['password']
        
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            
            # 1. BUSCAR USUARIO EN LA BD
            # Usamos comillas en "Usuarios" porque tu tabla tiene mayúscula
            query = 'SELECT id_usuario, rut, password_hash, id_rol FROM "Usuarios" WHERE rut = %s'
            cur.execute(query, (rut_form,))
            usuario = cur.fetchone()
            
            cur.close()
            conn.close()
            
            if usuario:
                # Desempaquetamos los datos que encontramos
                id_bd, rut_bd, hash_bd, rol_bd = usuario
                
                # 2. COMPARAR LA CLAVE ESCRITA CON LA ENCRIPTADA
                if bcrypt.check_password_hash(hash_bd, clave_form):
                    # ¡Login Exitoso! Guardamos datos en sesión
                    session['user_id'] = id_bd
                    session['user_rut'] = rut_bd
                    session['user_role'] = rol_bd
                    return redirect(url_for('dashboard'))
                else:
                    return "<h3>❌ Error: Contraseña incorrecta</h3><a href='/login'>Intentar de nuevo</a>"
            else:
                return "<h3>❌ Error: Usuario no encontrado</h3><a href='/login'>Intentar de nuevo</a>"
        
    return render_template('login.html')

# --- CERRAR SESIÓN ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- TEST DE CONEXIÓN ---
@app.route('/test-db')
def test_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        conn.close()
        return jsonify({"status": "success", "version": db_version[0]})
    else:
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)