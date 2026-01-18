from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, send_file
from flask_bcrypt import Bcrypt 
from config.db import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash
import io
import math
import random
import string 
import smtplib
import os
from datetime import datetime, date
from email.mime.text import MIMEText
from xhtml2pdf import pisa
from reportlab.pdfgen import canvas 
from reportlab.lib.pagesizes import letter

app = Flask(__name__)

# --- CONFIGURACIÓN DE SEGURIDAD ---
app.secret_key = "tesis_mauricio_secret_key" 
bcrypt = Bcrypt(app) 

# --- CONFIGURACIÓN DE CORREO ---
SMTP_EMAIL = "mauricio.manriquez.cordero@gmail.com"  
SMTP_PASSWORD = "bpaptrwigcdrxjye" 

# --- FUNCIONES AUXILIARES ---
def enviar_notificacion_acceso(nombre_alumno, rut_alumno, email_apoderado, tipo="Ingreso"):
    """
    Envía un correo al apoderado avisando el tipo de movimiento (Ingreso o Salida).
    """
    try:
        hora_actual = datetime.now().strftime("%d/%m/%Y a las %H:%M hrs")
        
        # 1. El Asunto cambia dinámicamente
        subject = f"🔔 SGFSE: {tipo} Registrado/a - {nombre_alumno}"
        
        # 2. Elegimos color: Verde para Entrada/Ingreso, Rojo para Salida
        color_borde = "#dc3545" if "Salida" in tipo else "#198754"
        
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="border: 1px solid #ddd; padding: 20px; border-radius: 10px; max-width: 600px;">
                    <h2 style="color: #0d6efd;">Sistema de Gestión de Flujo y Seguridad Escolar</h2>
                    <p>Estimado Apoderado,</p>
                    <p>Le informamos que el alumno <strong>{nombre_alumno}</strong> (RUT: {rut_alumno}) 
                    ha registrado su <strong>{tipo}</strong> al establecimiento.</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid {color_borde}; margin: 20px 0;">
                        <p style="margin: 0;"><strong>🕒 Hora de registro:</strong> {hora_actual}</p>
                        <p style="margin: 5px 0 0 0;"><strong>📍 Movimiento:</strong> {tipo}</p>
                    </div>
                    
                    <hr style="border: 0; border-top: 1px solid #eee;">
                    <p style="font-size: 12px; color: gray;">
                        Este es un mensaje automático generado por SGFSE. Por favor no responder a este correo.
                    </p>
                </div>
            </body>
        </html>
        """

        msg = MIMEText(body, 'html')
        msg['Subject'] = subject
        msg['From'] = f"SGFSE Notificaciones <{SMTP_EMAIL}>"
        msg['To'] = email_apoderado

        # --- CORRECCIÓN CLAVE AQUÍ ---
        # Usamos SMTP_SSL para el puerto 465
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        
        # server.starttls()  <-- ESTO SE QUEDA COMENTADO (No sirve con SSL)
        
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Correo de {tipo} enviado a {email_apoderado}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error enviando correo: {error_msg}")
        return error_msg  # Devuelve el texto del error

# --- RUTA DE INICIO ---
@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('id_rol') == 1:
            return redirect(url_for('dashboard'))
        elif session.get('id_rol') == 2:
            return redirect(url_for('portal_apoderado'))
            
    return render_template('home.html')

# --- DASHBOARD PRINCIPAL ---
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT COUNT(*) FROM "Usuarios"'); total_usuarios = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM "Alumnos"'); total_alumnos = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template('dashboard.html', 
                           total_usuarios=total_usuarios, 
                           total_alumnos=total_alumnos)

# --- RECUPERACIÓN DE CONTRASEÑA ---
@app.route('/recuperar_clave', methods=['GET', 'POST'])
def recuperar_clave():
    if request.method == 'POST':
        email_input = request.form['email']
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = """
            SELECT u.id_usuario, p.nombre 
            FROM "Usuarios" u
            JOIN "Relacion_Apoderado" ra ON u.id_usuario = ra.id_usuario
            JOIN "Perfiles" p ON u.id_usuario = p.id_usuario
            WHERE ra.email_contacto = %s
        """
        cur.execute(query, (email_input,))
        usuario = cur.fetchone()
        
        if usuario:
            id_usuario = usuario[0]
            nombre = usuario[1]
            
            # Generar nueva clave temporal
            nueva_clave = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            nuevo_hash = generate_password_hash(nueva_clave)
            
            cur.execute('UPDATE "Usuarios" SET password_hash = %s WHERE id_usuario = %s', (nuevo_hash, id_usuario))
            conn.commit()
            
            try:
                msg = MIMEText(f"""
                <h1>Restablecimiento de Clave SGFSE</h1>
                <p>Hola {nombre},</p>
                <p>Tu contraseña ha sido restablecida exitosamente.</p>
                <p><strong>Tu nueva clave temporal es: {nueva_clave}</strong></p>
                <p>Por favor, ingresa y cámbiala lo antes posible.</p>
                """, 'html')
                
                msg['Subject'] = "🔐 SGFSE: Nueva Contraseña"
                msg['From'] = f"Soporte SGFSE <{SMTP_EMAIL}>"
                msg['To'] = email_input

                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.send_message(msg)
                server.quit()
                
                flash('✅ Se ha enviado una nueva contraseña a tu correo.', 'success')
                return redirect(url_for('login'))
                
            except Exception as e:
                flash(f'Error al enviar correo: {e}', 'danger')
        else:
            flash('⚠️ No encontramos ese correo en nuestros registros.', 'warning')
            
        cur.close()
        conn.close()
        
    return render_template('recuperar.html')

# --- CAMBIAR CONTRASEÑA (AUTOGESTIÓN) ---
@app.route('/cambiar_clave', methods=['GET', 'POST'])
def cambiar_clave():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        clave_actual = request.form['clave_actual']
        nueva_clave = request.form['nueva_clave']
        confirmar_clave = request.form['confirmar_clave']
        
        id_usuario = session['user_id']
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT password_hash FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
        resultado = cur.fetchone()
        
        if resultado:
            hash_guardado = resultado[0]
            
            if check_password_hash(hash_guardado, clave_actual):
                if nueva_clave == confirmar_clave:
                    nuevo_hash = generate_password_hash(nueva_clave)
                    cur.execute('UPDATE "Usuarios" SET password_hash = %s WHERE id_usuario = %s', (nuevo_hash, id_usuario))
                    conn.commit()
                    
                    flash('✅ ¡Contraseña actualizada con éxito! Por seguridad, inicia sesión nuevamente.', 'success')
                    return redirect(url_for('logout')) 
                else:
                    flash('⚠️ Las nuevas contraseñas no coinciden.', 'warning')
            else:
                flash('⛔ La contraseña actual es incorrecta.', 'danger')
        
        cur.close()
        conn.close()
        
    return render_template('cambiar_clave.html')

# --- LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        rut = request.form['rut']
        clave = request.form['clave']
        rol_entrada = request.form.get('rol_entrada') 

        conn = get_db_connection()
        cur = conn.cursor()
        
        # Obtenemos: id, rut, hash, rol, nombre, apellido
        cur.execute('SELECT u.id_usuario, u.rut, u.password_hash, u.id_rol, p.nombre, p.apellido_paterno FROM "Usuarios" u LEFT JOIN "Perfiles" p ON u.id_usuario = p.id_usuario WHERE u.rut = %s', (rut,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user[2], clave):
            id_rol_real = user[3] 

            # Validación de portal correcto
            if str(id_rol_real) != str(rol_entrada):
                flash('⛔ Error de Seguridad: Estás intentando ingresar por el portal equivocado.', 'danger')
                return redirect(url_for('home')) 

            # Crear Sesión
            session['user_id'] = user[0]
            session['id_rol'] = id_rol_real
            session['nombre'] = f"{user[4]} {user[5]}" if user[4] else user[1]
            session['rut'] = user[1] 

            # Seguridad: Forzar cambio si clave == RUT
            if check_password_hash(user[2], user[1]):
                flash('⚠️ POR SEGURIDAD: Detectamos que sigues usando tu RUT como contraseña. Debes crear una nueva clave personalizada para continuar.', 'warning')
                return redirect(url_for('cambiar_clave'))

            # Redirección según Rol
            if id_rol_real == 1:
                return redirect(url_for('dashboard')) 
            elif id_rol_real == 2:
                return redirect(url_for('portal_apoderado')) 
            else:
                session.clear()
                flash('Tu perfil no tiene acceso.', 'info')
                return redirect(url_for('home'))
        else:
             flash('RUT o contraseña incorrectos.', 'danger')

    return redirect(url_for('home'))

# --- LOGOUT ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- TEST DB (Diagnóstico) ---
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

# --- LISTA DE USUARIOS (CRUD) ---
@app.route('/usuarios')
def usuarios():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    busqueda = request.args.get('busqueda', '')

    conn = get_db_connection()
    cur = conn.cursor()

    where_clause = ""
    params_count = []
    params_query = []

    if busqueda:
        where_clause = """
            WHERE (
                u.rut ILIKE %s OR 
                (p.nombre || ' ' || p.apellido_paterno || ' ' || COALESCE(p.apellido_materno, '')) ILIKE %s
            )
        """
        termino = f"%{busqueda}%"
        params_count = [termino, termino]
        params_query = [termino, termino]

    query_count = f"""
        SELECT COUNT(*) 
        FROM "Usuarios" u
        JOIN "Perfiles" p ON u.id_usuario = p.id_usuario
        {where_clause}
    """
    cur.execute(query_count, tuple(params_count))
    total_users = cur.fetchone()[0]
    total_pages = math.ceil(total_users / per_page)

    params_query.extend([per_page, offset])
    
    query = f"""
        SELECT 
            u.id_usuario, 
            u.rut, 
            p.nombre, 
            p.apellido_paterno,
            p.apellido_materno, 
            r.nombre_rol,
            
            COALESCE(
                (SELECT p_alum.nombre || ' ' || p_alum.apellido_paterno 
                 FROM "Relacion_Apoderado" ra
                 JOIN "Alumnos" al ON ra.id_alumno = al.id_alumno
                 JOIN "Perfiles" p_alum ON al.id_perfil = p_alum.id_perfil
                 WHERE ra.id_usuario = u.id_usuario
                 LIMIT 1),
                 
                (SELECT p_apo.nombre || ' ' || p_apo.apellido_paterno 
                 FROM "Alumnos" al2
                 JOIN "Relacion_Apoderado" ra2 ON al2.id_alumno = ra2.id_alumno
                 JOIN "Perfiles" p_apo ON ra2.id_usuario = p_apo.id_usuario
                 WHERE al2.id_perfil = p.id_perfil 
                 LIMIT 1),
                 
                '---'
            ) as familiar_asociado

        FROM "Usuarios" u
        JOIN "Perfiles" p ON u.id_usuario = p.id_usuario
        JOIN "Roles" r ON u.id_rol = r.id_rol
        {where_clause}
        ORDER BY u.id_usuario ASC
        LIMIT %s OFFSET %s
    """
    
    cur.execute(query, tuple(params_query))
    usuarios = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('usuarios.html', 
                           usuarios=usuarios, 
                           page=page, 
                           total_pages=total_pages,
                           busqueda=busqueda)

# --- CREAR USUARIO ---
@app.route('/crear_usuario', methods=['GET', 'POST'])
def crear_usuario():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            rut = request.form['rut']
            id_rol = request.form['id_rol']
            
            # Lógica de contraseña
            if id_rol == '1': 
                clave_plana = request.form.get('clave')
                if not clave_plana:
                    flash('El administrador debe tener una contraseña.', 'error')
                    return redirect(url_for('crear_usuario'))
            else:
                clave_plana = rut 
            
            password_hash = generate_password_hash(clave_plana)

            nombre = request.form['nombre']
            ape_p = request.form['apellido_paterno']
            ape_m = request.form['apellido_materno']

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute('INSERT INTO "Usuarios" (rut, password_hash, id_rol) VALUES (%s, %s, %s) RETURNING id_usuario',
                        (rut, password_hash, id_rol))
            new_id_usuario = cur.fetchone()[0]

            cur.execute('INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno) VALUES (%s, %s, %s, %s)',
                        (new_id_usuario, nombre, ape_p, ape_m))

            conn.commit()
            cur.close()
            conn.close()

            flash('Usuario creado exitosamente.', 'success')
            return redirect(url_for('usuarios'))

        except Exception as e:
            flash(f'Error al crear usuario: {e}', 'error')
            return redirect(url_for('crear_usuario'))

    return render_template('crear_usuario.html')

# --- ELIMINAR USUARIO ---
@app.route('/eliminar_usuario/<int:id_usuario>', methods=['POST'])
def eliminar_usuario(id_usuario):
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))
    
    if id_usuario == session['user_id']:
        flash('⛔ No puedes eliminar tu propia cuenta mientras estás conectado.', 'danger')
        return redirect(url_for('usuarios'))

    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT id_rol FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
        dato_rol = cur.fetchone()
        
        if dato_rol:
            rol = dato_rol[0]
            
            # Caso Alumno
            if rol == 3: 
                query_buscar_alumno = """
                    SELECT a.id_alumno 
                    FROM "Alumnos" a
                    JOIN "Perfiles" p ON a.id_perfil = p.id_perfil
                    WHERE p.id_usuario = %s
                """
                cur.execute(query_buscar_alumno, (id_usuario,))
                alumno = cur.fetchone()
                
                if alumno:
                    id_alum_int = alumno[0]

                    # Validar si tiene asistencias
                    cur.execute('SELECT COUNT(*) FROM "Asistencia" WHERE id_alumno = %s', (id_alum_int,))
                    cantidad_asistencias = cur.fetchone()[0]

                    if cantidad_asistencias > 0:
                        flash(f'⛔ ACCIÓN DENEGADA: Este alumno tiene {cantidad_asistencias} registros de asistencia. Por integridad de datos no se puede eliminar.', 'danger')
                        conn.rollback() 
                        return redirect(url_for('usuarios'))
                    
                    # Eliminar relaciones si no tiene historial
                    cur.execute('DELETE FROM "Relacion_Apoderado" WHERE id_alumno = %s', (id_alum_int,))
                    cur.execute('DELETE FROM "Alumnos" WHERE id_alumno = %s', (id_alum_int,))

            # Caso Apoderado
            elif rol == 2: 
                try:
                      cur.execute('DELETE FROM "Solicitud_Ayuda" WHERE id_usuario_apo = %s', (id_usuario,))
                except:
                      pass 
                
                cur.execute('DELETE FROM "Relacion_Apoderado" WHERE id_usuario = %s', (id_usuario,))

            # Borrado Final
            cur.execute('DELETE FROM "Perfiles" WHERE id_usuario = %s', (id_usuario,))
            cur.execute('DELETE FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
            
            conn.commit()
            flash('✅ Usuario eliminado correctamente.', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"Error detallado al eliminar: {e}") 
        flash('❌ Error crítico al intentar eliminar el usuario.', 'danger')
        
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('usuarios'))

# --- EDITAR USUARIO ---
@app.route('/editar_usuario/<int:id_usuario>', methods=['GET', 'POST'])
def editar_usuario(id_usuario):
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre = request.form['nombre']
        app_pat = request.form['apellido_paterno']
        app_mat = request.form['apellido_materno']
        rut = request.form['rut']
        id_rol = int(request.form['rol'])
        password = request.form['password']
        
        correo_input = request.form.get('correo', '') 
        telefono_input = request.form.get('telefono', '') 

        try:
            cur.execute("""
                UPDATE "Perfiles" 
                SET nombre = %s, apellido_paterno = %s, apellido_materno = %s
                WHERE id_usuario = %s
            """, (nombre, app_pat, app_mat, id_usuario))

            cur.execute('UPDATE "Usuarios" SET rut = %s, id_rol = %s WHERE id_usuario = %s',
                        (rut, id_rol, id_usuario))
            
            if password:
                pass_hash = generate_password_hash(password)
                cur.execute('UPDATE "Usuarios" SET password_hash = %s WHERE id_usuario = %s',
                            (pass_hash, id_usuario))

            if id_rol == 2:
                cur.execute('SELECT 1 FROM "Relacion_Apoderado" WHERE id_usuario = %s', (id_usuario,))
                if cur.fetchone():
                    cur.execute("""
                        UPDATE "Relacion_Apoderado" 
                        SET email_contacto = %s, telefono = %s 
                        WHERE id_usuario = %s
                    """, (correo_input, telefono_input, id_usuario))

            conn.commit()
            flash('✅ Usuario actualizado correctamente.', 'success')
            return redirect(url_for('usuarios'))
            
        except Exception as e:
            conn.rollback()
            print(f"Error SQL: {e}")
            flash(f'Error al actualizar: {e}', 'danger')
    
    query_cargar = """
        SELECT 
            u.rut, 
            u.id_rol, 
            p.nombre, 
            p.apellido_paterno, 
            p.apellido_materno, 
            ra.email_contacto, 
            ra.telefono 
        FROM "Usuarios" u
        JOIN "Perfiles" p ON u.id_usuario = p.id_usuario
        LEFT JOIN "Relacion_Apoderado" ra ON u.id_usuario = ra.id_usuario
        WHERE u.id_usuario = %s
    """
    cur.execute(query_cargar, (id_usuario,))
    user = cur.fetchone()
    
    cur.execute('SELECT * FROM "Roles"')
    roles = cur.fetchall()
    
    cur.close(); conn.close()
    return render_template('editar_usuario.html', user=user, usuario=user, roles=roles)

# --- MATRICULAR ALUMNO ---

@app.route('/matricular', methods=['GET', 'POST'])
def matricular():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        try:
            # --- 1. DATOS ALUMNO ---
            # HTML: name="rut_alumno"
            rut_alumno = request.form['rut_alumno']
            clave_alumno = generate_password_hash(rut_alumno) 
            
            cur.execute("""
                INSERT INTO "Usuarios" (rut, password_hash, id_rol)
                VALUES (%s, %s, 3) RETURNING id_usuario
            """, (rut_alumno, clave_alumno))
            id_usr_alumno = cur.fetchone()[0]

            # HTML: name="nombres_alumno", "ape_p_alumno", "ape_m_alumno"
            cur.execute("""
                INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno)
                VALUES (%s, %s, %s, %s) RETURNING id_perfil
            """, (id_usr_alumno, request.form['nombres_alumno'], request.form['ape_p_alumno'], request.form['ape_m_alumno']))
            id_perfil_alumno = cur.fetchone()[0]

            # HTML: name="curso_id", "fecha_nac", "sexo", "direccion"
            cur.execute("""
                INSERT INTO "Alumnos" (id_perfil, id_curso, fecha_nacimiento, sexo, direccion)
                VALUES (%s, %s, %s, %s, %s) RETURNING id_alumno
            """, (id_perfil_alumno, request.form['curso_id'], request.form['fecha_nac'], request.form['sexo'], request.form['direccion']))
            
            id_alumno_matriculado = cur.fetchone()[0]

            # --- 2. DATOS APODERADO ---
            # HTML: name="rut_apoderado"
            rut_apo = request.form['rut_apoderado']
            
            cur.execute('SELECT id_usuario FROM "Usuarios" WHERE rut = %s', (rut_apo,))
            apoderado_existente = cur.fetchone()

            if apoderado_existente:
                id_usr_apo = apoderado_existente[0]
            else:
                clave_apo = generate_password_hash(rut_apo) 
                
                cur.execute("""
                    INSERT INTO "Usuarios" (rut, password_hash, id_rol)
                    VALUES (%s, %s, 2) RETURNING id_usuario
                """, (rut_apo, clave_apo))
                id_usr_apo = cur.fetchone()[0]

                # HTML: name="nombres_apo", "ape_p_apo", "ape_m_apo"
                cur.execute("""
                    INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno)
                    VALUES (%s, %s, %s, %s)
                """, (id_usr_apo, request.form['nombres_apo'], request.form['ape_p_apo'], request.form['ape_m_apo']))

            # --- 3. VINCULAR ---
            # HTML: name="parentesco", "telefono", "email"
            cur.execute("""
                INSERT INTO "Relacion_Apoderado" (id_usuario, id_alumno, parentesco, telefono, email_contacto)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_usr_apo, id_alumno_matriculado, request.form['parentesco'], request.form['telefono'], request.form['email']))

            conn.commit()
            flash('¡Matrícula exitosa! Alumno y Apoderado vinculados.', 'success')
            return redirect(url_for('gestion_usuarios'))

        except Exception as e:
            conn.rollback()
            flash(f'Error grave al matricular: {str(e)}', 'danger')
            return redirect(url_for('matricular')) 
        
        finally:
            cur.close()
            conn.close()

    # --- GET ---
    cur = conn.cursor() 
    cur.execute('SELECT id_curso, nombre_curso FROM "Cursos" ORDER BY id_curso ASC')
    lista_cursos = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('matricular.html', cursos=lista_cursos)

# --- GESTIÓN DE ASISTENCIA ---
@app.route('/seleccionar_asistencia')
def seleccionar_asistencia():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id_curso, nombre_curso FROM "Cursos" ORDER BY nombre_curso ASC')
    cursos = cur.fetchall()
    cur.close()
    conn.close()
    
    hoy = date.today()
    return render_template('asistencia_selector.html', cursos=cursos, fecha_hoy=hoy)

# --- RUTA ASISTENCIA (ACTUALIZADA CON HORARIOS) ---
@app.route('/asistencia', methods=['GET', 'POST'])
def asistencia():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT * FROM "Cursos"')
    cursos = cur.fetchall()

    curso_seleccionado = request.args.get('curso_id', type=int)
    fecha_seleccionada = request.args.get('fecha', str(date.today())) 
    
    alumnos = []

    if request.method == 'POST':
        try:
            curso_form = request.form.get('curso_id_hidden')
            fecha_form = request.form.get('fecha_hidden')
            
            for key, value in request.form.items():
                if key.startswith('estado_'):
                    id_alumno = key.split('_')[1]
                    id_estado = int(value) 
                    
                    # Verificamos si existe para decidir UPDATE o INSERT
                    cur.execute("""
                        SELECT 1 FROM "Asistencia" 
                        WHERE id_alumno = %s AND fecha = %s
                    """, (id_alumno, fecha_form))
                    
                    if cur.fetchone():
                        # Si ya existe (ej: por el simulador), solo actualizamos el ESTADO
                        # Esto es genial porque NO borra la hora de entrada si ya estaba
                        cur.execute("""
                            UPDATE "Asistencia" SET id_estado = %s 
                            WHERE id_alumno = %s AND fecha = %s
                        """, (id_estado, id_alumno, fecha_form))
                    else:
                        # Si no existe, creamos el registro (sin hora, porque es manual)
                        cur.execute("""
                            INSERT INTO "Asistencia" (id_alumno, fecha, id_estado)
                            VALUES (%s, %s, %s)
                        """, (id_alumno, fecha_form, id_estado))
            
            conn.commit()
            flash('✅ Asistencia guardada correctamente.', 'success')
            return redirect(url_for('asistencia', curso_id=curso_form, fecha=fecha_form))

        except Exception as e:
            conn.rollback()
            flash(f'❌ Error al guardar: {e}', 'danger')

    if curso_seleccionado:
        # === AQUÍ ESTÁ EL CAMBIO CLAVE ===
        # Agregamos hora_entrada y hora_salida al SELECT
        query = """
            SELECT 
                a.id_alumno,
                u.rut, 
                p.nombre,
                p.apellido_paterno,
                p.apellido_materno,
                COALESCE(asi.id_estado, 1) as id_estado_actual,
                asi.hora_entrada,
                asi.hora_salida
            FROM "Alumnos" a
            JOIN "Perfiles" p ON a.id_perfil = p.id_perfil
            JOIN "Usuarios" u ON p.id_usuario = u.id_usuario 
            LEFT JOIN "Asistencia" asi ON a.id_alumno = asi.id_alumno AND asi.fecha = %s
            WHERE a.id_curso = %s
            ORDER BY p.apellido_paterno ASC
        """
        cur.execute(query, (fecha_seleccionada, curso_seleccionado))
        alumnos = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('asistencia.html', 
                           cursos=cursos, 
                           alumnos=alumnos,
                           curso_act=curso_seleccionado,
                           fecha_act=fecha_seleccionada)

@app.route('/guardar_asistencia', methods=['POST'])
def guardar_asistencia():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    id_curso = request.form['id_curso']
    fecha = request.form['fecha']

    conn = get_db_connection()
    cur = conn.cursor()

    for key in request.form:
        if key.startswith('estado_'):
            id_alumno = key.split('_')[1]
            
            id_estado = request.form.get(f'estado_{id_alumno}')
            hora_entrada = request.form.get(f'entrada_{id_alumno}')
            hora_salida = request.form.get(f'salida_{id_alumno}')

            if hora_entrada == '': hora_entrada = None
            if hora_salida == '': hora_salida = None

            cur.execute("""
                DELETE FROM "Asistencia" 
                WHERE id_alumno = %s AND fecha = %s
            """, (id_alumno, fecha))

            cur.execute("""
                INSERT INTO "Asistencia" (id_alumno, fecha, id_estado, hora_entrada, hora_salida)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_alumno, fecha, id_estado, hora_entrada, hora_salida))

    conn.commit()
    cur.close()
    conn.close()

    flash('¡Asistencia guardada correctamente!', 'success')
    return redirect(url_for('tomar_asistencia', id_curso=id_curso, fecha=fecha))

@app.route('/gestion_usuarios')
def gestion_usuarios():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))
    return render_template('gestion_usuarios.html')

# --- PORTAL APODERADO ---
@app.route('/portal_apoderado')
def portal_apoderado():
    if 'user_id' not in session or session.get('id_rol') != 2:
        return redirect(url_for('login'))
    
    id_apoderado = session['user_id']
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    query_alumno = 'SELECT id_alumno FROM "Relacion_Apoderado" WHERE id_usuario = %s'
    cur.execute(query_alumno, (id_apoderado,))
    alumno_data = cur.fetchone()
    
    movimientos_reales = [] 
    
    if alumno_data:
        id_alumno = alumno_data[0]
        query_asistencia = """
            SELECT fecha, hora_entrada, hora_salida 
            FROM "Asistencia" 
            WHERE id_alumno = %s 
            ORDER BY fecha DESC 
            LIMIT 30
        """
        cur.execute(query_asistencia, (id_alumno,))
        registros = cur.fetchall()
        
        for reg in registros:
            fecha_fmt = reg[0].strftime('%d/%m/%Y') if reg[0] else "Fecha desc."
            ent_fmt = str(reg[1])[:5] if reg[1] else "--:--"
            if reg[2]:
                sal_fmt = str(reg[2])[:5]
            else:
                sal_fmt = "PENDIENTE"
            
            movimientos_reales.append({
                "fecha": fecha_fmt,
                "entrada": ent_fmt,
                "salida": sal_fmt
            })
            
    cur.close(); conn.close()
    return render_template('portal_apoderado.html', movimientos=movimientos_reales)

# --- PDF GENERADOR (Apoderado) ---
@app.route('/generar_reporte', methods=['POST'])
def generar_reporte():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    fecha_inicio = request.form['fecha_inicio']
    fecha_fin = request.form['fecha_fin']
    id_apoderado = session['user_id']
    nombre_apoderado = session.get('nombre', 'Apoderado')

    def formatear(f):
        try:
            return datetime.strptime(f, '%Y-%m-%d').strftime('%d/%m/%Y')
        except:
            return f

    fecha_inicio_fmt = formatear(fecha_inicio)
    fecha_fin_fmt = formatear(fecha_fin)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query_alumno = """
            SELECT A.id_alumno, P.nombre, P.apellido_paterno, C.nombre_curso, u.rut
            FROM "Relacion_Apoderado" R
            JOIN "Alumnos" A ON R.id_alumno = A.id_alumno
            JOIN "Perfiles" P ON A.id_perfil = P.id_perfil
            JOIN "Cursos" C ON A.id_curso = C.id_curso
            JOIN "Usuarios" u ON P.id_usuario = u.id_usuario
            WHERE R.id_usuario = %s 
            LIMIT 1
        """
        cur.execute(query_alumno, (id_apoderado,))
        datos_alumno = cur.fetchone()

        if datos_alumno:
            id_alumno_real = datos_alumno[0]
            alumno = {
                'nombre': f"{datos_alumno[1]} {datos_alumno[2]}",
                'curso': datos_alumno[3],
                'rut': datos_alumno[4]
            }
        else:
            flash("No tienes alumnos asociados.", "warning")
            return redirect(url_for('portal_apoderado'))

        query_asistencia = """
            SELECT fecha, hora_entrada, hora_salida
            FROM "Asistencia"
            WHERE id_alumno = %s 
            AND fecha >= %s AND fecha <= %s
            ORDER BY fecha DESC
        """
        cur.execute(query_asistencia, (id_alumno_real, fecha_inicio, fecha_fin))
        registros = cur.fetchall()

    except Exception as e:
        print(f"Error: {e}")
        return "Error generando el reporte", 500
    finally:
        cur.close()
        conn.close()

    html = render_template('reporte_apoderado_pdf.html', 
                           alumno=alumno,
                           apoderado=nombre_apoderado,
                           desde=fecha_inicio_fmt,
                           hasta=fecha_fin_fmt,
                           registros=registros,
                           fecha_actual=datetime.now().strftime('%d/%m/%Y %H:%M'))

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html), dest=pdf_buffer)

    if pisa_status.err:
        return "Hubo un error al crear el PDF", 500
    
    pdf_buffer.seek(0)
    
    return send_file(pdf_buffer, 
                     as_attachment=True, 
                     download_name=f"Reporte_Asistencia_{fecha_inicio}.pdf", 
                     mimetype='application/pdf')


# --- PDF GENERADOR (Admin) ---
@app.route('/descargar_reporte')
def descargar_reporte():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    curso_id = request.args.get('curso_id', type=int)
    fecha = request.args.get('fecha')
    
    if not curso_id or not fecha:
        flash('❌ Faltan datos para generar el reporte.', 'danger')
        return redirect(url_for('asistencia'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT nombre_curso FROM "Cursos" WHERE id_curso = %s', (curso_id,))
    nombre_curso = cur.fetchone()[0]

    query = """
        SELECT 
            p.nombre,
            p.apellido_paterno,
            p.apellido_materno,
            u.rut,
            COALESCE(asi.id_estado, 1) as id_estado 
        FROM "Alumnos" a
        JOIN "Perfiles" p ON a.id_perfil = p.id_perfil
        JOIN "Usuarios" u ON p.id_usuario = u.id_usuario
        LEFT JOIN "Asistencia" asi ON a.id_alumno = asi.id_alumno AND asi.fecha = %s
        WHERE a.id_curso = %s
        ORDER BY p.apellido_paterno ASC
    """
    cur.execute(query, (fecha, curso_id))
    alumnos = cur.fetchall()
    
    cur.close()
    conn.close()

    html = render_template('reporte_pdf.html', 
                           alumnos=alumnos, 
                           curso=nombre_curso, 
                           fecha=fecha)

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html), dest=pdf_buffer)

    if pisa_status.err:
        return "Hubo un error al generar el PDF", 500

    pdf_buffer.seek(0)
    return send_file(pdf_buffer, 
                     as_attachment=True, 
                     download_name=f"Asistencia_{nombre_curso}_{fecha}.pdf", 
                     mimetype='application/pdf')


# --- SIMULADOR DE TORNIQUETE (FINAL CON CORREO DINÁMICO) ---
@app.route('/simular_acceso', methods=['GET', 'POST'])
def simular_acceso():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    if request.method == 'POST':
        rut_alumno_input = request.form['rut_alumno']

        conn = get_db_connection()
        cur = conn.cursor()

        query = """
            SELECT 
                p_alum.nombre || ' ' || p_alum.apellido_paterno as nombre_alumno,
                ra.email_contacto,
                p_apo.nombre || ' ' || p_apo.apellido_paterno as nombre_apoderado,
                a.id_alumno
            FROM "Usuarios" u_alum
            JOIN "Perfiles" p_alum ON u_alum.id_usuario = p_alum.id_usuario
            JOIN "Alumnos" a ON p_alum.id_perfil = a.id_perfil
            JOIN "Relacion_Apoderado" ra ON a.id_alumno = ra.id_alumno
            JOIN "Perfiles" p_apo ON ra.id_usuario = p_apo.id_usuario 
            WHERE u_alum.rut = %s
            LIMIT 1
        """
        cur.execute(query, (rut_alumno_input,))
        resultado = cur.fetchone()

        if resultado:
            nombre_alum = resultado[0]
            email_apo = resultado[1]
            nombre_apo_str = resultado[2]
            id_alumno_real = resultado[3]

            fecha_hoy = date.today()
            hora_actual = datetime.now().strftime("%H:%M:%S")

            cur.execute("""
                SELECT id_asistencia, hora_salida 
                FROM "Asistencia" 
                WHERE id_alumno = %s AND fecha = %s
            """, (id_alumno_real, fecha_hoy))
            
            registro = cur.fetchone()
            
            tipo_movimiento = "" 
            msg_db = ""
            proceder_con_correo = False

            if not registro:
                # MARCAR ENTRADA
                cur.execute("""
                    INSERT INTO "Asistencia" (id_alumno, fecha, id_estado, hora_entrada)
                    VALUES (%s, %s, 1, %s)
                """, (id_alumno_real, fecha_hoy, hora_actual))
                conn.commit()
                
                tipo_movimiento = "Entrada"
                msg_db = f"✅ Entrada registrada a las {hora_actual}."
                proceder_con_correo = True

            elif registro[1] is None:
                # MARCAR SALIDA
                cur.execute("""
                    UPDATE "Asistencia" 
                    SET hora_salida = %s 
                    WHERE id_alumno = %s AND fecha = %s
                """, (hora_actual, id_alumno_real, fecha_hoy))
                conn.commit()
                
                tipo_movimiento = "Salida"
                msg_db = f"👋 Salida registrada a las {hora_actual}."
                proceder_con_correo = True
                
            else:
                msg_db = "⚠️ El alumno ya cerró su jornada (tiene entrada y salida)."
                proceder_con_correo = False

            # --- AQUI ESTA EL CAMBIO IMPORTANTE ---
            if proceder_con_correo:
                if email_apo:
                    # Guardamos el resultado en una variable
                    resultado_envio = enviar_notificacion_acceso(nombre_alum, rut_alumno_input, email_apo, tipo_movimiento)
                    
                    # Si devuelve True, todo salió bien
                    if resultado_envio is True:
                        flash(f"<b>{tipo_movimiento}:</b> {msg_db} (Notificación enviada a {nombre_apo_str})", "success")
                    else:
                        # Si devuelve otra cosa, es el TEXTO DEL ERROR. Lo mostramos en pantalla.
                        flash(f"<b>{tipo_movimiento}:</b> {msg_db} (ERROR CORREO: {resultado_envio})", "warning")
                else:
                    flash(f"<b>{tipo_movimiento}:</b> {msg_db} (Apoderado sin correo)", "warning")
            else:
                flash(msg_db, "info")

        else:
            flash(f"❌ RUT <b>{rut_alumno_input}</b> no encontrado.", "danger")

        cur.close()
        conn.close()
        return redirect(url_for('simular_acceso'))

    return render_template('simulador.html')


# ==========================================================
# RUTAS DE INSTALACIÓN Y CONFIGURACIÓN INICIAL
# (Desactivadas tras el despliegue)
# ==========================================================

'''
# --- INSTALADOR DE BASE DE DATOS ---
@app.route('/crear-base-de-datos-nube')
def crear_base_de_datos_nube():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. Crear Esquema
        cur.execute("CREATE SCHEMA IF NOT EXISTS asistencia_sgfse;")
        
        # [CÓDIGO DE CREACIÓN DE TABLAS OMITIDO POR LIMPIEZA]
        # Consultar documentación de base de datos para estructura completa.

        conn.commit()
        cur.close()
        conn.close()
        
        return "Base de datos creada exitosamente."

    except Exception as e:
        return f"Error: {str(e)}"

# --- POBLADOR DE DATOS INICIALES (CURSOS) ---
@app.route('/poblar-datos-iniciales')
def poblar_datos_iniciales():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Cargar Estados y Cursos
        # [CÓDIGO OMITIDO]

        conn.commit()
        cur.close()
        conn.close()

        return "Datos cargados."

    except Exception as e:
        return f"Error: {str(e)}"
'''

# --- RUTA DE REPARACIÓN DE ROLES (SOLO EJECUTAR UNA VEZ) ---
@app.route('/crear_roles_faltantes')
def crear_roles_faltantes():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Intentamos insertar los 3 roles básicos.
        # El "ON CONFLICT DO NOTHING" evita error si ya existen.
        roles_sql = """
            INSERT INTO "Roles" (id_rol, nombre_rol) 
            VALUES 
                (1, 'Administrador'),
                (2, 'Apoderado'),
                (3, 'Alumno')
            ON CONFLICT (id_rol) DO NOTHING;
        """
        
        cur.execute(roles_sql)
        conn.commit()
        cur.close()
        conn.close()
        return "<h1>✅ ¡Roles creados con éxito!</h1><p>Ahora existen: Admin(1), Apoderado(2) y Alumno(3). <br>Ya puedes volver atrás e intentar Matricular.</p>"
        
    except Exception as e:
        return f"<h1>❌ Error:</h1> <p>{str(e)}</p>"


if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)