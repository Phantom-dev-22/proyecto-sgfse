from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt 
from config.db import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash
import io
from flask import send_file
from reportlab.pdfgen import canvas 
from reportlab.lib.pagesizes import letter
from datetime import datetime 
import math
from datetime import date
from xhtml2pdf import pisa
import random
import string 

# 👇 1. AGREGA ESTAS LIBRERÍAS DE CORREO AQUÍ 👇
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

# CONFIGURACIÓN DE SEGURIDAD
app.secret_key = "tesis_mauricio_secret_key" 
bcrypt = Bcrypt(app) 


# 👇 2. PEGA LA CONFIGURACIÓN DEL CORREO AQUÍ (ANTES DE LAS RUTAS) 👇

# --- CONFIGURACIÓN DE CORREO ---
# Reemplaza con tus datos reales
SMTP_EMAIL = "mauricio.manriquez.cordero@gmail.com"  
SMTP_PASSWORD = "bpaptrwigcdrxjye" 

def enviar_notificacion_acceso(nombre_alumno, rut_alumno, email_apoderado):
    """
    Envía un correo al apoderado avisando que el alumno llegó.
    """
    try:
        # 1. Capturamos la hora exacta AHORA
        hora_actual = datetime.now().strftime("%d/%m/%Y a las %H:%M hrs")
        
        subject = f"🔔 SGFSE: Ingreso Registrado - {nombre_alumno}"
        
        # 2. Insertamos la variable {hora_actual} en el HTML
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="border: 1px solid #ddd; padding: 20px; border-radius: 10px; max-width: 600px;">
                    <h2 style="color: #0d6efd;">Sistema de Gestión de Flujo y Seguridad Escolar</h2>
                    <p>Estimado Apoderado,</p>
                    <p>Le informamos que el alumno <strong>{nombre_alumno}</strong> (RUT: {rut_alumno}) 
                    ha registrado su ingreso al establecimiento correctamente.</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #198754; margin: 20px 0;">
                        <p style="margin: 0;"><strong>🕒 Hora de registro:</strong> {hora_actual}</p>
                        <p style="margin: 5px 0 0 0;"><strong>📍 Estado:</strong> Presente</p>
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

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Correo enviado a {email_apoderado}")
        return True
        
    except Exception as e:
        print(f"❌ Error enviando correo: {e}")
        return False

# --- RUTA DE INICIO ---
@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('id_rol') == 1:
            return redirect(url_for('dashboard'))
        elif session.get('id_rol') == 2:
            return redirect(url_for('portal_apoderado'))
            
    return render_template('home.html')

# --- RUTA DASHBOARD (CORREGIDA) ---
@app.route('/dashboard')
def dashboard():
    # 1. Seguridad
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # 2. Contadores
    cur.execute('SELECT COUNT(*) FROM "Usuarios"'); total_usuarios = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM "Alumnos"'); total_alumnos = cur.fetchone()[0]

    # 3. CONSULTA DE MENSAJES (ELIMINADA COMO PEDISTE)
    # Ya no consultamos la tabla de ayuda porque ahora usas el Modal Informativo.
    
    # IMPORTANTE: Descomentamos el cierre de conexión para no dejarla abierta
    cur.close()
    conn.close()

    # 4. Enviamos todo al HTML (SIN lista_mensajes)
    return render_template('dashboard.html', 
                           total_usuarios=total_usuarios, 
                           total_alumnos=total_alumnos)

# --- RUTA: RECUPERAR CONTRASEÑA ---
@app.route('/recuperar_clave', methods=['GET', 'POST'])
def recuperar_clave():
    if request.method == 'POST':
        email_input = request.form['email']
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Buscar si existe un usuario con ese correo (en Perfiles o Relacion_Apoderado)
        # Nota: Buscamos en 'Relacion_Apoderado' porque ahí guardaste los emails de los apoderados.
        # Si tienes emails de admin en otra parte, habría que ajustar, pero asumamos apoderados por ahora.
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
            
            # 2. Generar nueva clave temporal (6 caracteres)
            nueva_clave = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            nuevo_hash = generate_password_hash(nueva_clave)
            
            # 3. Actualizar en BD
            cur.execute('UPDATE "Usuarios" SET password_hash = %s WHERE id_usuario = %s', (nuevo_hash, id_usuario))
            conn.commit()
            
            # 4. Enviar Correo
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

# --- RUTA: CAMBIAR CONTRASEÑA (AUTOGESTIÓN) ---
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
        
        # 1. Obtener la contraseña actual de la BD para compararla
        cur.execute('SELECT password_hash FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
        resultado = cur.fetchone()
        
        if resultado:
            hash_guardado = resultado[0]
            
            # 2. Verificar si la clave actual que escribió es correcta
            if check_password_hash(hash_guardado, clave_actual):
                
                # 3. Verificar que la nueva clave coincida con la confirmación
                if nueva_clave == confirmar_clave:
                    # 4. Encriptar y Guardar
                    nuevo_hash = generate_password_hash(nueva_clave)
                    cur.execute('UPDATE "Usuarios" SET password_hash = %s WHERE id_usuario = %s', (nuevo_hash, id_usuario))
                    conn.commit()
                    
                    flash('✅ ¡Contraseña actualizada con éxito! Por seguridad, inicia sesión nuevamente.', 'success')
                    return redirect(url_for('logout')) # Lo sacamos para que pruebe su nueva clave
                else:
                    flash('⚠️ Las nuevas contraseñas no coinciden.', 'warning')
            else:
                flash('⛔ La contraseña actual es incorrecta.', 'danger')
        
        cur.close()
        conn.close()
        
    return render_template('cambiar_clave.html')

# --- RUTA DE LOGIN ---
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

        # user[0]=id, user[1]=rut, user[2]=hash, user[3]=rol
        if user and check_password_hash(user[2], clave):
            id_rol_real = user[3] 

            # Validación estricta de portal
            if str(id_rol_real) != str(rol_entrada):
                flash('⛔ Error de Seguridad: Estás intentando ingresar por el portal equivocado.', 'danger')
                return redirect(url_for('home')) 

            # CREAMOS LA SESIÓN (Importante hacerlo antes de redirigir)
            session['user_id'] = user[0]
            session['id_rol'] = id_rol_real
            session['nombre'] = f"{user[4]} {user[5]}" if user[4] else user[1]
            # Guardamos el RUT en sesión por si acaso
            session['rut'] = user[1] 

            # ==================================================================
            # 🛡️ NUEVO BLOQUE DE SEGURIDAD: FORZAR CAMBIO SI CLAVE == RUT
            # ==================================================================
            # Preguntamos: ¿La contraseña guardada en la BD corresponde al RUT del usuario?
            # user[2] es el Hash guardado, user[1] es el RUT real
            if check_password_hash(user[2], user[1]):
                flash('⚠️ POR SEGURIDAD: Detectamos que sigues usando tu RUT como contraseña. Debes crear una nueva clave personalizada para continuar.', 'warning')
                return redirect(url_for('cambiar_clave'))
            # ==================================================================

            # Si la clave NO es el RUT, entra normal
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

    return redirect(url_for('home')) # Si es GET o falla login

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

# --- RUTA: LISTA DE USUARIOS (CON BUSCADOR Y PAGINACIÓN) ---
@app.route('/usuarios')
def usuarios():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    # 1. Configuración de Paginación y Búsqueda
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    
    # Capturamos lo que el usuario escribió (si escribió algo)
    busqueda = request.args.get('busqueda', '')

    conn = get_db_connection()
    cur = conn.cursor()

    # 2. Construcción Dinámica del WHERE
    # Si hay búsqueda, filtramos por RUT, Nombre o Apellidos
    where_clause = ""
    params_count = []
    params_query = []

    if busqueda:
        # CORRECCIÓN: Concatenamos (p.nombre + espacio + paterno + espacio + materno)
        # Usamos COALESCE(..., '') para que si no tiene apellido materno no se rompa la búsqueda.
        where_clause = """
            WHERE (
                u.rut ILIKE %s OR 
                (p.nombre || ' ' || p.apellido_paterno || ' ' || COALESCE(p.apellido_materno, '')) ILIKE %s
            )
        """
        
        termino = f"%{busqueda}%"
        
        # IMPORTANTE: Ahora solo hay 2 signos %s en el SQL (RUT y NombreCompleto),
        # así que la lista solo debe tener 2 elementos.
        params_count = [termino, termino]
        params_query = [termino, termino]

    # 3. Contar total (Aplicando el filtro si existe)
    query_count = f"""
        SELECT COUNT(*) 
        FROM "Usuarios" u
        JOIN "Perfiles" p ON u.id_usuario = p.id_usuario
        {where_clause}
    """
    cur.execute(query_count, tuple(params_count))
    total_users = cur.fetchone()[0]
    total_pages = math.ceil(total_users / per_page)

    # 4. CONSULTA MAESTRA (Con filtro + paginación)
    # Agregamos los parámetros de límite y offset al final
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
                           busqueda=busqueda) # Devolvemos la búsqueda para mantenerla en el input

# --- RUTA: CREAR USUARIO (CON LÓGICA DE CONTRASEÑA DIFERENCIADA) ---
@app.route('/crear_usuario', methods=['GET', 'POST'])
def crear_usuario():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            rut = request.form['rut']
            id_rol = request.form['id_rol']
            
            # --- LÓGICA DE CONTRASEÑA ---
            if id_rol == '1': 
                # Si es ADMIN, la clave viene del formulario
                clave_plana = request.form.get('clave')
                if not clave_plana:
                    flash('El administrador debe tener una contraseña.', 'error')
                    return redirect(url_for('crear_usuario'))
            else:
                # Si es APODERADO o ALUMNO, la clave es el RUT
                clave_plana = rut 
            
            # Encriptamos la clave elegida
            password_hash = generate_password_hash(clave_plana)

            # Datos del Perfil
            nombre = request.form['nombre']
            ape_p = request.form['apellido_paterno']
            ape_m = request.form['apellido_materno']

            conn = get_db_connection()
            cur = conn.cursor()

            # Insertar Usuario
            cur.execute('INSERT INTO "Usuarios" (rut, password_hash, id_rol) VALUES (%s, %s, %s) RETURNING id_usuario',
                        (rut, password_hash, id_rol))
            new_id_usuario = cur.fetchone()[0]

            # Insertar Perfil
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

# --- RUTA: ELIMINAR USUARIO (PROTEGIDA) ---
@app.route('/eliminar_usuario/<int:id_usuario>', methods=['POST'])
def eliminar_usuario(id_usuario):
    # 1. Validaciones de Sesión
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))
    
    if id_usuario == session['user_id']:
        flash('⛔ No puedes eliminar tu propia cuenta mientras estás conectado.', 'danger')
        return redirect(url_for('usuarios'))

    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 2. Averiguar qué Rol tiene el usuario que queremos borrar
        cur.execute('SELECT id_rol FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
        dato_rol = cur.fetchone()
        
        if dato_rol:
            rol = dato_rol[0]
            
            # --- CASO ALUMNO (ROL 3) ---
            if rol == 3: 
                # Buscamos su ID de Alumno interno
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

                    # === AQUÍ ESTÁ EL CAMBIO CLAVE ===
                    # Antes de borrar, PREGUNTAMOS si tiene asistencias
                    cur.execute('SELECT COUNT(*) FROM "Asistencia" WHERE id_alumno = %s', (id_alum_int,))
                    cantidad_asistencias = cur.fetchone()[0]

                    if cantidad_asistencias > 0:
                        # ¡TIENE HISTORIAL! -> ACTIVAMOS EL FRENO DE MANO
                        flash(f'⛔ ACCIÓN DENEGADA: Este alumno tiene {cantidad_asistencias} registros de asistencia. Por integridad de datos y seguridad no se puede eliminar.', 'danger')
                        conn.rollback() # Cancelamos todo
                        return redirect(url_for('usuarios'))
                    
                    # Si la cantidad es 0, procedemos a borrar sus relaciones (Apoderados y Tabla Alumnos)
                    cur.execute('DELETE FROM "Relacion_Apoderado" WHERE id_alumno = %s', (id_alum_int,))
                    cur.execute('DELETE FROM "Alumnos" WHERE id_alumno = %s', (id_alum_int,))
                    # NOTA: YA NO EJECUTAMOS 'DELETE FROM Asistencia', porque ya sabemos que está vacía.

            # --- CASO APODERADO (ROL 2) ---
            elif rol == 2: 
                # Borramos solicitud de ayuda si existe (opcional)
                try:
                     cur.execute('DELETE FROM "Solicitud_Ayuda" WHERE id_usuario_apo = %s', (id_usuario,))
                except:
                     pass 
                
                # Borramos la relación con sus pupilos
                cur.execute('DELETE FROM "Relacion_Apoderado" WHERE id_usuario = %s', (id_usuario,))

            # --- BORRADO FINAL (COMÚN PARA TODOS) ---
            # Borramos Perfil y Usuario base
            cur.execute('DELETE FROM "Perfiles" WHERE id_usuario = %s', (id_usuario,))
            cur.execute('DELETE FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
            
            conn.commit()
            flash('✅ Usuario eliminado correctamente (No tenía registros vinculantes).', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"Error detallado al eliminar: {e}") 
        flash('❌ Error crítico al intentar eliminar el usuario.', 'danger')
        
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('usuarios'))

# --- RUTA: EDITAR USUARIO ---
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
                # OJO: Aquí faltaba encriptar la contraseña si se cambia
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

# --- RUTA: MATRICULAR ---
@app.route('/matricular', methods=['GET', 'POST'])
def matricular():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        try:
            # --- PARTE A: DATOS DEL ALUMNO ---
            rut_alumno = request.form['rut_alumno']
            clave_alumno = generate_password_hash(rut_alumno) 
            
            cur.execute("""
                INSERT INTO "Usuarios" (rut, password_hash, id_rol)
                VALUES (%s, %s, 3) RETURNING id_usuario
            """, (rut_alumno, clave_alumno))
            id_usr_alumno = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno)
                VALUES (%s, %s, %s, %s) RETURNING id_perfil
            """, (id_usr_alumno, request.form['nombre_alumno'], request.form['app_p_alumno'], request.form['app_m_alumno']))
            id_perfil_alumno = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO "Alumnos" (id_perfil, id_curso, fecha_nacimiento, sexo, direccion)
                VALUES (%s, %s, %s, %s, %s) RETURNING id_alumno
            """, (id_perfil_alumno, request.form['id_curso'], request.form['fecha_nac'], request.form['sexo'], request.form['direccion']))
            
            id_alumno_matriculado = cur.fetchone()[0]


            # --- PARTE B: DATOS DEL APODERADO ---
            rut_apo = request.form['rut_apo']
            
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

                cur.execute("""
                    INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno)
                    VALUES (%s, %s, %s, %s)
                """, (id_usr_apo, request.form['nombre_apo'], request.form['app_p_apo'], request.form['app_m_apo']))

            # --- PARTE C: EL VÍNCULO ---
            cur.execute("""
                INSERT INTO "Relacion_Apoderado" (id_usuario, id_alumno, parentesco, telefono, email_contacto)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_usr_apo, id_alumno_matriculado, request.form['parentesco'], request.form['telefono_apo'], request.form['email_apo']))

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

# --- RUTAS DE ASISTENCIA ---
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
                    
                    cur.execute("""
                        SELECT 1 FROM "Asistencia" 
                        WHERE id_alumno = %s AND fecha = %s
                    """, (id_alumno, fecha_form))
                    
                    if cur.fetchone():
                        cur.execute("""
                            UPDATE "Asistencia" SET id_estado = %s 
                            WHERE id_alumno = %s AND fecha = %s
                        """, (id_estado, id_alumno, fecha_form))
                    else:
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
        query = """
            SELECT 
                a.id_alumno,
                u.rut, 
                p.nombre,
                p.apellido_paterno,
                p.apellido_materno,
                COALESCE(asi.id_estado, 1) as id_estado_actual 
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


# --- PDF GENERADOR (General Admin) ---
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


# --- SIMULADOR DE TORNIQUETE (CORREGIDO: Nombre Apoderado + PRG) ---
@app.route('/simular_acceso', methods=['GET', 'POST'])
def simular_acceso():
    # Solo admin puede ver el simulador
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    if request.method == 'POST':
        rut_alumno_input = request.form['rut_alumno']

        conn = get_db_connection()
        cur = conn.cursor()

        # CONSULTA ACTUALIZADA: Ahora traemos también el nombre del apoderado (p_apo)
        query = """
            SELECT 
                p_alum.nombre || ' ' || p_alum.apellido_paterno as nombre_alumno,
                ra.email_contacto,
                p_apo.nombre || ' ' || p_apo.apellido_paterno as nombre_apoderado
            FROM "Usuarios" u_alum
            JOIN "Perfiles" p_alum ON u_alum.id_usuario = p_alum.id_usuario
            JOIN "Alumnos" a ON p_alum.id_perfil = a.id_perfil
            JOIN "Relacion_Apoderado" ra ON a.id_alumno = ra.id_alumno
            JOIN "Perfiles" p_apo ON ra.id_usuario = p_apo.id_usuario  -- Unión extra para nombre del apoderado
            WHERE u_alum.rut = %s
            LIMIT 1
        """
        cur.execute(query, (rut_alumno_input,))
        resultado = cur.fetchone()
        cur.close()
        conn.close()

        if resultado:
            nombre_alum = resultado[0]
            email_apo = resultado[1]
            nombre_apo_str = resultado[2]

            if email_apo:
                exito = enviar_notificacion_acceso(nombre_alum, rut_alumno_input, email_apo)
                
                if exito:
                    # NUEVO MENSAJE CORTO (Solo con nombre)
                    flash(f"Se ha notificado a: <b>{nombre_apo_str}</b>", "success")
                else:
                    flash("⚠️ Falló el envío del correo (Revisar credenciales SMTP).", "warning")
            else:
                flash(f"⚠️ El alumno existe, pero su apoderado NO tiene correo.", "warning")
        else:
            flash(f"❌ RUT <b>{rut_alumno_input}</b> no encontrado.", "danger")

        return redirect(url_for('simular_acceso'))

    return render_template('simulador.html')






# --- RUTAS ELIMINADAS (COMENTADAS O BORRADAS) ---
# @app.route('/enviar_ayuda')...
# @app.route('/resolver_solicitud')...




# ==========================================
# ZONA DE HERRAMIENTAS (Desactivado para producción)
# ==========================================

# --- RUTA TEMPORAL: POBLAR BASE DE DATOS  ---
#@app.route('/poblar_automatico')
#def poblar_automatico():
#    # 1. Seguridad básica
#    if 'user_id' not in session or session.get('id_rol') != 1:
#        return "⛔ Debes ser administrador para ejecutar esto."

#    import random
#    from werkzeug.security import generate_password_hash
#    from datetime import date

#    conn = get_db_connection()
#    cur = conn.cursor()

#    # Datos falsos para generar
#    nombres = ["Agustín", "Vicente", "Martín", "Matías", "Benjamín", "Sofía", "Emilia", "Isidora", "Trinidad", "Florencia", "Lucas", "Mateo", "Gaspar"]
#    apellidos = ["Tapia", "Reyes", "Fuentes", "Castillo", "Espinoza", "Lagos", "Pizarro", "Saavedra", "Carrasco", "Barraza", "Soto", "Muñoz", "Rojas", "Díaz"]
    
#    reporte = ["<h1>🚀 Reporte de Poblado Masivo</h1><ul>"]
    
#    try:
#        # 1. Obtener cursos
#        cur.execute('SELECT id_curso, nombre_curso FROM "Cursos" ORDER BY id_curso')
#        cursos = cur.fetchall()
        
#        # Empezamos el contador en 100 para que al sumar 25 millones quede 25.000.100 (8 dígitos base)
#        contador_global = 100 
        
#        for curso in cursos:
#            id_c = curso[0]
#            nom_c = curso[1]
            
#            # Revisar si ya tiene alumnos
#            cur.execute('SELECT COUNT(*) FROM "Alumnos" WHERE id_curso = %s', (id_c,))
#            cantidad = cur.fetchone()[0]
            
#            if cantidad > 0:
#                reporte.append(f"<li style='color:gray'>El curso <b>{nom_c}</b> ya tiene {cantidad} alumnos. (Omitido)</li>")
#                continue
            
#            # Si está vacío, creamos 8 alumnos
#            reporte.append(f"<li>🟢 Poblando <b>{nom_c}</b> con 8 alumnos nuevos...</li>")
            
#            for _ in range(8):
#                contador_global += 1
                
#                # --- CORRECCIÓN RUT ALUMNO (Max 12 caracteres) ---
#                # Generamos base 25.000.XXX
#                # Formato final: 25.000.101-K (12 chars exactos)
#                rut_base_alum = 25000000 + contador_global
#                # Truco para poner puntos automáticamente
#                rut_str_alum = f"{rut_base_alum:,.0f}".replace(",", ".") 
#                rut_alum = f"{rut_str_alum}-K"
                
#                pass_alum = generate_password_hash(rut_alum)
#                nom_alum = random.choice(nombres)
#                ape_alum = random.choice(apellidos)
                
#                # Usuario
#                cur.execute('INSERT INTO "Usuarios" (rut, password_hash, id_rol) VALUES (%s, %s, 3) RETURNING id_usuario', (rut_alum, pass_alum))
#                id_usr_alum = cur.fetchone()[0]
                
#                # Perfil
#                cur.execute('INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno) VALUES (%s, %s, %s, %s) RETURNING id_perfil',
#                            (id_usr_alum, nom_alum, ape_alum, random.choice(apellidos)))
#                id_perf_alum = cur.fetchone()[0]
                
#                # Ficha Alumno
#                cur.execute('INSERT INTO "Alumnos" (id_perfil, id_curso, fecha_nacimiento, sexo, direccion) VALUES (%s, %s, %s, %s, %s) RETURNING id_alumno',
#                            (id_perf_alum, id_c, '2015-01-01', 'M', 'Calle Falsa 123'))
#                id_alum_real = cur.fetchone()[0]
                
#                # --- CORRECCIÓN RUT APODERADO (Max 12 caracteres) ---
#                rut_base_apo = 15000000 + contador_global
#                rut_str_apo = f"{rut_base_apo:,.0f}".replace(",", ".")
#                rut_apo = f"{rut_str_apo}-K"
                
#                pass_apo = generate_password_hash(rut_apo)
                
#                # Usuario Apo
#                cur.execute('INSERT INTO "Usuarios" (rut, password_hash, id_rol) VALUES (%s, %s, 2) RETURNING id_usuario', (rut_apo, pass_apo))
#                id_usr_apo = cur.fetchone()[0]
                
#                # Perfil Apo
#               cur.execute('INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno) VALUES (%s, %s, %s, %s)',
#                            (id_usr_apo, random.choice(nombres), ape_alum, "Apoderado"))
                
#                # Vínculo
#                cur.execute('INSERT INTO "Relacion_Apoderado" (id_usuario, id_alumno, parentesco, telefono, email_contacto) VALUES (%s, %s, %s, %s, %s)',
#                            (id_usr_apo, id_alum_real, "Apoderado", "+56911111111", "test@prueba.cl"))

#        conn.commit()
#        reporte.append("</ul><h3 style='color:green'>✅ ¡Proceso terminado con éxito!</h3>")
#        reporte.append(f"<a href='{url_for('dashboard')}'>Volver al Dashboard</a>")

#    except Exception as e:
#        conn.rollback()
#        reporte.append(f"</ul><h3 style='color:red'>❌ Error Fatal: {e}</h3>")
    
#    finally:
#        cur.close()
#        conn.close()

#    return "".join(reporte)

# --- INICIO BLOQUE INSTALACION AUTOMATICA (VERSIÓN FINAL COMPLETA) ---
@app.route('/crear-base-de-datos-nube')
def crear_base_de_datos_nube():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. Crear Esquema
        cur.execute("CREATE SCHEMA IF NOT EXISTS asistencia_sgfse;")
        
        # ---------------------------------------------------------
        # NIVEL 1: TABLAS INDEPENDIENTES (No dependen de nadie)
        # ---------------------------------------------------------
        
        # Tabla ROLES
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Roles" (
                id_rol integer NOT NULL GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                nombre_rol character varying(50) NOT NULL
            );
        """)

        # Tabla CURSOS
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Cursos" (
                id_curso integer NOT NULL GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                nombre_curso character varying(100) NOT NULL
            );
        """)

        # Tabla ESTADOS_ASISTENCIA
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Estados_Asistencia" (
                id_estado integer NOT NULL GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                nombre_estado character varying(50) NOT NULL
            );
        """)

        # ---------------------------------------------------------
        # NIVEL 2: PRIMERAS DEPENDENCIAS
        # ---------------------------------------------------------

        # Tabla USUARIOS (Depende de Roles)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Usuarios" (
                id_usuario integer NOT NULL GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                rut character varying(12) NOT NULL UNIQUE,
                password_hash character varying(255) NOT NULL,
                id_rol integer,
                CONSTRAINT fk_id_rol FOREIGN KEY (id_rol) 
                    REFERENCES asistencia_sgfse."Roles" (id_rol)
            );
        """)

        # ---------------------------------------------------------
        # NIVEL 3: SEGUNDAS DEPENDENCIAS
        # ---------------------------------------------------------

        # Tabla PERFILES (Depende de Usuarios)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Perfiles" (
                id_perfil integer NOT NULL GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                id_usuario integer,
                nombre character varying(100) NOT NULL,
                apellido_paterno character varying(100) NOT NULL,
                apellido_materno character varying(100) NOT NULL,
                CONSTRAINT fk_id_usuario FOREIGN KEY (id_usuario) 
                    REFERENCES asistencia_sgfse."Usuarios" (id_usuario)
            );
        """)

        # Tabla SOLICITUD_AYUDA (Depende de Usuarios)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Solicitud_Ayuda" (
                id_solicitud integer NOT NULL GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                id_usuario_apo integer,
                mensaje text,
                fecha_creacion date DEFAULT now(),
                estado character varying(20),
                CONSTRAINT fk_solicitud_usuario FOREIGN KEY (id_usuario_apo) 
                    REFERENCES asistencia_sgfse."Usuarios" (id_usuario)
            );
        """)

        # ---------------------------------------------------------
        # NIVEL 4: DEPENDENCIAS COMPLEJAS
        # ---------------------------------------------------------

        # Tabla ALUMNOS (Depende de Perfiles y Cursos)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Alumnos" (
                id_alumno integer NOT NULL GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                id_perfil integer,
                id_curso integer,
                fecha_nacimiento date NOT NULL,
                sexo character varying(10),
                direccion character varying(255),
                rut character varying(12) UNIQUE,
                CONSTRAINT fk_id_curso FOREIGN KEY (id_curso) 
                    REFERENCES asistencia_sgfse."Cursos" (id_curso),
                CONSTRAINT fk_id_perfil FOREIGN KEY (id_perfil) 
                    REFERENCES asistencia_sgfse."Perfiles" (id_perfil)
            );
        """)

        # Tabla RELACION_APODERADO (Depende de Usuarios y Alumnos)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Relacion_Apoderado" (
                id_relacion integer NOT NULL GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                id_usuario integer NOT NULL,
                id_alumno integer NOT NULL,
                parentesco character varying(50),
                telefono character varying(20),
                email_contacto character varying(100),
                CONSTRAINT fk_alumno_relacion FOREIGN KEY (id_alumno) 
                    REFERENCES asistencia_sgfse."Alumnos" (id_alumno),
                CONSTRAINT fk_usuario_relacion FOREIGN KEY (id_usuario) 
                    REFERENCES asistencia_sgfse."Usuarios" (id_usuario)
            );
        """)

        # Tabla ASISTENCIA (Depende de Alumnos y Estados)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Asistencia" (
                id_asistencia integer NOT NULL GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                id_alumno integer NOT NULL,
                fecha date NOT NULL DEFAULT CURRENT_DATE,
                id_estado integer NOT NULL,
                observacion text,
                hora_entrada time without time zone,
                hora_salida time without time zone,
                CONSTRAINT fk_alumno_asistencia FOREIGN KEY (id_alumno) 
                    REFERENCES asistencia_sgfse."Alumnos" (id_alumno),
                CONSTRAINT fk_estado_asistencia FOREIGN KEY (id_estado) 
                    REFERENCES asistencia_sgfse."Estados_Asistencia" (id_estado)
            );
        """)

        # Tabla EVENTOS_FLUJO (Particionada, depende de Alumnos)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse."Eventos_Flujo" (
                id_evento numeric(50,0) NOT NULL,
                id_alumno integer,
                tipo_evento character varying(100),
                fecha_hora timestamp with time zone NOT NULL DEFAULT now(),
                CONSTRAINT fk_id_alumno FOREIGN KEY (id_alumno) 
                    REFERENCES asistencia_sgfse."Alumnos" (id_alumno)
            ) PARTITION BY RANGE (fecha_hora);
        """)

        # Partición Enero 2026 (Tal como estaba en tu archivo)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS asistencia_sgfse.eventos_flujo_enero_2026 
            PARTITION OF asistencia_sgfse."Eventos_Flujo"
            FOR VALUES FROM ('2026-01-01 00:00:00-03') TO ('2026-02-01 00:00:00-03');
        """)

        # ---------------------------------------------------------
        # CREACIÓN DE DATOS INICIALES (ADMIN)
        # ---------------------------------------------------------
        
        # 1. Crear Rol Admin
        cur.execute("SELECT id_rol FROM asistencia_sgfse.\"Roles\" WHERE nombre_rol = 'Administrador';")
        rol = cur.fetchone()
        if not rol:
            cur.execute("INSERT INTO asistencia_sgfse.\"Roles\" (nombre_rol) VALUES ('Administrador') RETURNING id_rol;")
            id_rol_admin = cur.fetchone()[0]
        else:
            id_rol_admin = rol[0]

        # 2. Crear Usuario Admin (RUT: 1-9, Clave: admin123)
        clave_secreta = generate_password_hash('admin123')
        cur.execute("SELECT id_usuario FROM asistencia_sgfse.\"Usuarios\" WHERE rut = '1-9';")
        user = cur.fetchone()
        
        msg = ""
        if not user:
            cur.execute("""
                INSERT INTO asistencia_sgfse."Usuarios" (rut, password_hash, id_rol) 
                VALUES (%s, %s, %s) RETURNING id_usuario;
            """, ('1-9', clave_secreta, id_rol_admin))
            
            
            id_new_user = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO asistencia_sgfse."Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno)
                VALUES (%s, 'Administrador', 'Sistema', 'SGFSE');
            """, (id_new_user,))
            
            msg = "✅ Usuario Admin y Perfil creados."
        else:
            msg = "⚠️ El usuario Admin ya existía."

        conn.commit()
        cur.close()
        conn.close()
        
        return f"""
        <div style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>¡BASE DE DATOS COMPLETA CREADA! 🏗️🎉</h1>
            <p>Se han creado las 10 tablas correctamente.</p>
            <p>{msg}</p>
            <hr>
            <h3>Credenciales:</h3>
            <p><strong>RUT:</strong> 1-9</p>
            <p><strong>Clave:</strong> admin123</p>
            <br>
            <a href="/" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">IR AL LOGIN</a>
        </div>
        """

    except Exception as e:
        return f"<h1>❌ ERROR FATAL:</h1> <p>{str(e)}</p>"
# --- FIN BLOQUE INSTALACION AUTOMATICA ---



if __name__ == '__main__':
    import os
    # El puerto lo asigna la nube (Render) o usa 5000 en tu PC
    port = int(os.environ.get("PORT", 5000))
    # host='0.0.0.0' es OBLIGATORIO para Docker
    app.run(host='0.0.0.0', port=port, debug=True)