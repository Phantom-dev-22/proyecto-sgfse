from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt 
from config.db import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash
import io
from flask import send_file
from reportlab.pdfgen import canvas # Para impresión en pdf - 1
from reportlab.lib.pagesizes import letter
from datetime import datetime # ¡Para el formato de fecha!
import math
from datetime import date
from xhtml2pdf import pisa # Para impresión en pdf - 2 

app = Flask(__name__)

# CONFIGURACIÓN DE SEGURIDAD
app.secret_key = "tesis_mauricio_secret_key" # Necesario para guardar la sesión
bcrypt = Bcrypt(app) # Inicializar encriptador

# --- RUTA DE INICIO ---
@app.route('/')
def home():
    # Si ya está logueado, lo mandamos a su panel correspondiente
    if 'user_id' in session:
        if session.get('id_rol') == 1:
            return redirect(url_for('dashboard'))
        elif session.get('id_rol') == 2:
            return redirect(url_for('portal_apoderado'))
            
    return render_template('home.html')

# --- RUTA DEL PANEL DE CONTROL (DASHBOARD) ---
# Aquí solo entran los que iniciaron sesión
# --- RUTA DASHBOARD (MODIFICADA PARA LEER MENSAJES) ---
@app.route('/dashboard')
def dashboard():
    # 1. Seguridad
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # 2. Contadores (Tus tarjetas de arriba)
    cur.execute('SELECT COUNT(*) FROM "Usuarios"'); total_usuarios = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM "Alumnos"'); total_alumnos = cur.fetchone()[0]

    # 3. CONSULTA DE MENSAJES (¡Esto es lo nuevo!)
    # Traemos el nombre del apoderado, el mensaje y la fecha
    query_mensajes = """
        SELECT p.nombre, p.apellido_paterno, s.mensaje, s.fecha_creacion 
        FROM "Solicitud_Ayuda" s
        JOIN "Perfiles" p ON s.id_usuario_apo = p.id_usuario
        ORDER BY s.fecha_creacion DESC LIMIT 5
    """
    cur.execute(query_mensajes)
    lista_mensajes = cur.fetchall()

    cur.close(); conn.close()

    # 4. Enviamos todo al HTML
    return render_template('dashboard.html', 
                           total_usuarios=total_usuarios, 
                           total_alumnos=total_alumnos, 
                           mensajes=lista_mensajes) # <--- Importante: enviamos la lista
  

# --- RUTA DE LOGIN (LA LÓGICA REAL) ---
# --- RUTA DE INICIO / LOGIN ---
# Agregamos ambas líneas para que entre por cualquiera de las dos
# --- RUTA DE LOGIN ACTUALIZADA ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        rut = request.form['rut']
        clave = request.form['clave']
        
        # Recibimos el "Sello de Entrada" del HTML (puede ser "1" o "2")
        rol_entrada = request.form.get('rol_entrada') 

        conn = get_db_connection()
        cur = conn.cursor()
        
        # Traemos al usuario de la BD
        cur.execute('SELECT u.id_usuario, u.rut, u.password_hash, u.id_rol, p.nombre, p.apellido_paterno FROM "Usuarios" u LEFT JOIN "Perfiles" p ON u.id_usuario = p.id_usuario WHERE u.rut = %s', (rut,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user[2], clave):
            id_rol_real = user[3] # Rol real de la BD (1=Admin, 2=Apo)

            # --- VALIDACIÓN ESTRICTA (CORREGIDA) ---
            # Si los roles no coinciden...
            if str(id_rol_real) != str(rol_entrada):
                
                # 1. CASO ESPECIAL: ¿El Admin puede entrar donde quiera?
                # Si tú quieres que el Admin sea una "Llave Maestra", descomenta estas 2 lineas:
                # if id_rol_real == 1:
                #     pass # El admin pasa aunque se equivoque de puerta
                # else:
                
                # 2. COMPORTAMIENTO NORMAL (ESTRICTO)
                flash('⛔ Error de Seguridad: Estás intentando ingresar por el portal equivocado.', 'danger')
                return redirect(url_for('home')) # <--- ¡ESTA LÍNEA ES EL FRENO!
                                                 # Debe estar alineada con el flash

            # --- SI PASA EL FRENO, RECIÉN ASIGNAMOS SESIÓN ---
            session['user_id'] = user[0]
            session['id_rol'] = id_rol_real
            session['nombre'] = f"{user[4]} {user[5]}" if user[4] else user[1]

            # --- REDIRECCIÓN FINAL (CONFIRMADA) ---
            # Aquí nos aseguramos de enviarte a TU sitio, no por donde entraste.
            if id_rol_real == 1:
                return redirect(url_for('dashboard')) # Admin -> Siempre al Azul
            elif id_rol_real == 2:
                return redirect(url_for('portal_apoderado')) # Apo -> Siempre al Verde
            else:
                session.clear()
                flash('Tu perfil no tiene acceso.', 'info')
                return redirect(url_for('home'))

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

# --- RUTA: LISTA DE USUARIOS (CON PAGINACIÓN Y ORDEN MEJORADO) ---
@app.route('/usuarios')
def usuarios():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    # 1. Configuración de Paginación
    page = request.args.get('page', 1, type=int) # Página actual (por defecto 1)
    per_page = 10 # Cuántos usuarios ver por página
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cur = conn.cursor()

    # 2. Contar total de usuarios (Para saber cuántas páginas hay)
    cur.execute('SELECT COUNT(*) FROM "Usuarios"')
    total_users = cur.fetchone()[0]
    total_pages = math.ceil(total_users / per_page)

    # 3. CONSULTA MAESTRA (Con límite y nombres completos)
    query = """
        SELECT 
            u.id_usuario, 
            u.rut, 
            p.nombre, 
            p.apellido_paterno,
            p.apellido_materno, -- Traemos el materno para el usuario principal
            r.nombre_rol,
            
            COALESCE(
                -- CASO 1: Si soy Apoderado, busco al ALUMNO (Con 2 apellidos)
                (SELECT p_alum.nombre || ' ' || p_alum.apellido_paterno || ' ' || COALESCE(p_alum.apellido_materno, '')
                 FROM "Relacion_Apoderado" ra
                 JOIN "Alumnos" al ON ra.id_alumno = al.id_alumno
                 JOIN "Perfiles" p_alum ON al.id_perfil = p_alum.id_perfil
                 WHERE ra.id_usuario = u.id_usuario
                 LIMIT 1),
                 
                -- CASO 2: Si soy Alumno, busco al APODERADO (Con 2 apellidos)
                (SELECT p_apo.nombre || ' ' || p_apo.apellido_paterno || ' ' || COALESCE(p_apo.apellido_materno, '')
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
        ORDER BY u.id_usuario ASC
        LIMIT %s OFFSET %s
    """
    
    cur.execute(query, (per_page, offset))
    usuarios = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('usuarios.html', 
                           usuarios=usuarios, 
                           page=page, 
                           total_pages=total_pages)

@app.route('/crear_usuario', methods=['GET', 'POST'])
def crear_usuario():
    if request.method == 'POST':
        # 1. Recibir datos
        rut = request.form['rut']
        clave_plana = request.form['clave']
        id_rol = request.form['id_rol']
        
        nombre = request.form['nombre']
        app_paterno = request.form['app_paterno']
        app_materno = request.form['app_materno']

        # Encriptar clave
        clave_encriptada = generate_password_hash(clave_plana)

        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # --- CORRECCIÓN AQUÍ: Usamos 'password_hash' ---
            cur.execute("""
                INSERT INTO "Usuarios" (rut, password_hash, id_rol)
                VALUES (%s, %s, %s)
                RETURNING id_usuario;
            """, (rut, clave_encriptada, id_rol))
            
            nuevo_id_usuario = cur.fetchone()[0]

            # Insertar en Perfiles (Esto estaba bien)
            cur.execute("""
                INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno)
                VALUES (%s, %s, %s, %s)
            """, (nuevo_id_usuario, nombre, app_paterno, app_materno))

            conn.commit()
            flash('¡Usuario y Perfil creados correctamente!', 'success')
            return redirect(url_for('usuarios'))

        except Exception as e:
            conn.rollback()
            flash(f'Error al crear ficha: {e}', 'danger')
            return redirect(url_for('crear_usuario'))
        finally:
            cur.close()
            conn.close()

    return render_template('crear_usuario.html')

# --- RUTA: ELIMINAR USUARIO (CORREGIDA V2) ---
@app.route('/eliminar_usuario/<int:id_usuario>', methods=['POST'])
def eliminar_usuario(id_usuario):
    # 1. Seguridad: Solo admin puede borrar
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))
    
    # Protección: No te puedes borrar a ti mismo
    if id_usuario == session['user_id']:
        flash('⛔ No puedes eliminar tu propia cuenta mientras estás conectado.', 'danger')
        return redirect(url_for('usuarios'))

    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 2. Averiguar qué Rol tiene
        cur.execute('SELECT id_rol FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
        dato_rol = cur.fetchone()
        
        if dato_rol:
            rol = dato_rol[0]
            
            # --- LIMPIEZA SI ES ALUMNO (Rol 3) ---
            if rol == 3:
                # CORRECCIÓN: Buscamos el ID Alumno a través de la tabla Perfiles
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
                    # 1. Borrar su Asistencia
                    cur.execute('DELETE FROM "Asistencia" WHERE id_alumno = %s', (id_alum_int,))
                    # 2. Borrar su relación con Apoderados
                    cur.execute('DELETE FROM "Relacion_Apoderado" WHERE id_alumno = %s', (id_alum_int,))
                    # 3. Borrar de la tabla Alumnos
                    cur.execute('DELETE FROM "Alumnos" WHERE id_alumno = %s', (id_alum_int,))

            # --- LIMPIEZA SI ES APODERADO (Rol 2) ---
            elif rol == 2:
                # 1. Borrar sus Solicitudes de Ayuda
                cur.execute('DELETE FROM "Solicitud_Ayuda" WHERE id_usuario_apo = %s', (id_usuario,))
                # 2. Borrar su relación con Alumnos
                cur.execute('DELETE FROM "Relacion_Apoderado" WHERE id_usuario = %s', (id_usuario,))

            # --- LIMPIEZA FINAL (PARA TODOS) ---
            # Borrar Perfil y Usuario
            cur.execute('DELETE FROM "Perfiles" WHERE id_usuario = %s', (id_usuario,))
            cur.execute('DELETE FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
            
            conn.commit()
            flash('✅ Usuario eliminado correctamente.', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"Error detallado al eliminar: {e}") # Mira la consola negra si vuelve a fallar
        flash('❌ Error al eliminar el usuario.', 'danger')
        
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('usuarios'))

# --- RUTA: EDITAR USUARIO (CORREGIDA CON NOMBRE REAL DE COLUMNA) ---
@app.route('/editar_usuario/<int:id_usuario>', methods=['GET', 'POST'])
def editar_usuario(id_usuario):
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        # 1. Datos Generales
        nombre = request.form['nombre']
        app_pat = request.form['apellido_paterno']
        app_mat = request.form['apellido_materno']
        rut = request.form['rut']
        id_rol = int(request.form['rol'])
        password = request.form['password']
        
        # Datos del Formulario
        correo_input = request.form.get('correo', '')   # Lo que viene del HTML
        telefono_input = request.form.get('telefono', '') # Lo que viene del HTML

        try:
            # A. Actualizar Perfil
            cur.execute("""
                UPDATE "Perfiles" 
                SET nombre = %s, apellido_paterno = %s, apellido_materno = %s
                WHERE id_usuario = %s
            """, (nombre, app_pat, app_mat, id_usuario))

            # B. Actualizar Usuario
            cur.execute('UPDATE "Usuarios" SET rut = %s, id_rol = %s WHERE id_usuario = %s',
                        (rut, id_rol, id_usuario))
            
            if password:
                cur.execute('UPDATE "Usuarios" SET password = %s WHERE id_usuario = %s',
                            (password, id_usuario))

            # C. LÓGICA APODERADO (Usando el nombre correcto de columna)
            if id_rol == 2:
                cur.execute('SELECT 1 FROM "Relacion_Apoderado" WHERE id_usuario = %s', (id_usuario,))
                if cur.fetchone():
                    # AQUÍ ESTÁ EL CAMBIO: email_contacto
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
    
    # --- GET: CARGAR DATOS ---
    # AQUÍ TAMBIÉN CAMBIAMOS EL NOMBRE
    query_cargar = """
        SELECT 
            u.rut, 
            u.id_rol, 
            p.nombre, 
            p.apellido_paterno, 
            p.apellido_materno, 
            ra.email_contacto,   -- Nombre correcto en la BD
            ra.telefono          -- ¿Este nombre es correcto o se llama 'fono'?
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

# --- RUTA: MATRICULAR (Lógica Completa: Alumno + Apoderado) ---
@app.route('/matricular', methods=['GET', 'POST'])
def matricular():
    # 1. Seguridad: Solo Admin
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        try:
            # --- PARTE A: DATOS DEL ALUMNO ---
            rut_alumno = request.form['rut_alumno']
            # Clave alumno = su RUT encriptado
            clave_alumno = generate_password_hash(rut_alumno) 
            
            # Crear Usuario Alumno (Rol 3)
            cur.execute("""
                INSERT INTO "Usuarios" (rut, password_hash, id_rol)
                VALUES (%s, %s, 3) RETURNING id_usuario
            """, (rut_alumno, clave_alumno))
            id_usr_alumno = cur.fetchone()[0]

            # Crear Perfil Alumno
            cur.execute("""
                INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno)
                VALUES (%s, %s, %s, %s) RETURNING id_perfil
            """, (id_usr_alumno, request.form['nombre_alumno'], request.form['app_p_alumno'], request.form['app_m_alumno']))
            id_perfil_alumno = cur.fetchone()[0]

            # Crear Ficha Académica (Tabla Alumnos)
            cur.execute("""
                INSERT INTO "Alumnos" (id_perfil, id_curso, fecha_nacimiento, sexo, direccion)
                VALUES (%s, %s, %s, %s, %s) RETURNING id_alumno
            """, (id_perfil_alumno, request.form['id_curso'], request.form['fecha_nac'], request.form['sexo'], request.form['direccion']))
            
            # ¡DATO CLAVE! Guardamos el ID del alumno recién creado
            id_alumno_matriculado = cur.fetchone()[0]


            # --- PARTE B: DATOS DEL APODERADO ---
            rut_apo = request.form['rut_apo']
            
            # Revisar si ya existe este apoderado
            cur.execute('SELECT id_usuario FROM "Usuarios" WHERE rut = %s', (rut_apo,))
            apoderado_existente = cur.fetchone()

            if apoderado_existente:
                # Si existe, usamos su ID antiguo
                id_usr_apo = apoderado_existente[0]
            else:
                # Si no existe, lo creamos
                clave_apo = generate_password_hash(rut_apo) # Clave = RUT
                
                # Usuario Apo (Rol 2)
                cur.execute("""
                    INSERT INTO "Usuarios" (rut, password_hash, id_rol)
                    VALUES (%s, %s, 2) RETURNING id_usuario
                """, (rut_apo, clave_apo))
                id_usr_apo = cur.fetchone()[0]

                # Perfil Apo
                cur.execute("""
                    INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno)
                    VALUES (%s, %s, %s, %s)
                """, (id_usr_apo, request.form['nombre_apo'], request.form['app_p_apo'], request.form['app_m_apo']))

            # --- PARTE C: EL VÍNCULO (Relacion_Apoderado) ---
            cur.execute("""
                INSERT INTO "Relacion_Apoderado" (id_usuario, id_alumno, parentesco, telefono, email_contacto)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_usr_apo, id_alumno_matriculado, request.form['parentesco'], request.form['telefono_apo'], request.form['email_apo']))

            conn.commit()
            flash('¡Matrícula exitosa! Alumno y Apoderado vinculados.', 'success')
            
            # Volvemos al menú de gestión
            return redirect(url_for('gestion_usuarios'))

        except Exception as e:
            conn.rollback()
            flash(f'Error grave al matricular: {str(e)}', 'danger')
            return redirect(url_for('matricular')) # Volvemos al formulario si falla
        
        finally:
            cur.close()
            conn.close()

    # --- MÉTODO GET (Mostrar Formulario) ---
    # Cargamos los cursos para el selector
    cur = conn.cursor() 
    cur.execute('SELECT id_curso, nombre_curso FROM "Cursos" ORDER BY id_curso ASC')
    lista_cursos = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('matricular.html', cursos=lista_cursos)

# --- RUTA: SELECTOR DE ASISTENCIA (PASO 1) ---
@app.route('/seleccionar_asistencia')
def seleccionar_asistencia():
    # Seguridad: Solo Admin
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Traemos los cursos para el menú desplegable
    cur.execute('SELECT id_curso, nombre_curso FROM "Cursos" ORDER BY nombre_curso ASC')
    cursos = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Usamos la fecha de hoy por defecto
    from datetime import date
    hoy = date.today()

    return render_template('asistencia_selector.html', cursos=cursos, fecha_hoy=hoy)

# --- RUTA UNIFICADA: CONTROL DE ASISTENCIA (CORREGIDA id_estado) ---
@app.route('/asistencia', methods=['GET', 'POST'])
def asistencia():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Listas para selectores
    cur.execute('SELECT * FROM "Cursos"')
    cursos = cur.fetchall()

    # 2. Capturar Filtros
    curso_seleccionado = request.args.get('curso_id', type=int)
    fecha_seleccionada = request.args.get('fecha', str(date.today())) 
    
    alumnos = []

    # 3. GUARDADO (POST)
    if request.method == 'POST':
        try:
            curso_form = request.form.get('curso_id_hidden')
            fecha_form = request.form.get('fecha_hidden')
            
            for key, value in request.form.items():
                if key.startswith('estado_'):
                    id_alumno = key.split('_')[1]
                    id_estado = int(value) # Convertimos a número (1, 2, 3...)
                    
                    # Verificamos si existe registro
                    cur.execute("""
                        SELECT 1 FROM "Asistencia" 
                        WHERE id_alumno = %s AND fecha = %s
                    """, (id_alumno, fecha_form))
                    
                    if cur.fetchone():
                        # ACTUALIZAR: Usamos la columna id_estado
                        cur.execute("""
                            UPDATE "Asistencia" SET id_estado = %s 
                            WHERE id_alumno = %s AND fecha = %s
                        """, (id_estado, id_alumno, fecha_form))
                    else:
                        # INSERTAR: Usamos la columna id_estado
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

   # 4. VISUALIZACIÓN (GET)
    if curso_seleccionado:
        # CORRECCIÓN: Hacemos JOIN con "Usuarios" (u) para sacar el RUT real
        query = """
            SELECT 
                a.id_alumno,
                u.rut,  -- <--- Ahora sacamos el RUT de la tabla Usuarios
                p.nombre,
                p.apellido_paterno,
                p.apellido_materno,
                COALESCE(asi.id_estado, 1) as id_estado_actual 
            FROM "Alumnos" a
            JOIN "Perfiles" p ON a.id_perfil = p.id_perfil
            JOIN "Usuarios" u ON p.id_usuario = u.id_usuario -- Nuevo JOIN vital
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

# --- RUTA: GUARDAR LOS DATOS (PASO 3) ---
@app.route('/guardar_asistencia', methods=['POST'])
def guardar_asistencia():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    # 1. Recibimos los datos generales
    id_curso = request.form['id_curso']
    fecha = request.form['fecha']

    conn = get_db_connection()
    cur = conn.cursor()

    # 2. Recorremos todo el formulario para encontrar a los alumnos
    # El formulario envía claves como: "estado_5", "entrada_5", etc. (donde 5 es el ID)
    for key in request.form:
        if key.startswith('estado_'):
            # Extraemos el ID del alumno del nombre del campo (ej: 'estado_5' -> 5)
            id_alumno = key.split('_')[1]
            
            # Obtenemos los valores para este alumno
            id_estado = request.form.get(f'estado_{id_alumno}')
            hora_entrada = request.form.get(f'entrada_{id_alumno}')
            hora_salida = request.form.get(f'salida_{id_alumno}')

            # Limpiamos datos vacíos (si borraron la hora, enviamos NULL a la BD)
            if hora_entrada == '': hora_entrada = None
            if hora_salida == '': hora_salida = None

            # 3. LÓGICA DE "UPSERT" (Actualizar o Insertar)
            # Primero borramos si ya existe algo ese día para ese alumno (para no duplicar)
            cur.execute("""
                DELETE FROM "Asistencia" 
                WHERE id_alumno = %s AND fecha = %s
            """, (id_alumno, fecha))

            # Luego insertamos el dato nuevo
            cur.execute("""
                INSERT INTO "Asistencia" (id_alumno, fecha, id_estado, hora_entrada, hora_salida)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_alumno, fecha, id_estado, hora_entrada, hora_salida))

    conn.commit()
    cur.close()
    conn.close()

    flash('¡Asistencia guardada correctamente!', 'success')
    # Volvemos a la planilla para ver que quedó grabado
    return redirect(url_for('tomar_asistencia', id_curso=id_curso, fecha=fecha))



# --- RUTA NUEVA: MENÚ DE USUARIOS ---
@app.route('/gestion_usuarios')
def gestion_usuarios():
    # Solo dejamos pasar al Admin (Rol 1)
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))
        
    # Mostramos el archivo HTML del menú (que crearemos o revisaremos luego)
    return render_template('gestion_usuarios.html')


# --- RUTA: PORTAL APODERADO (CONECTADO A BD REAL) ---
@app.route('/portal_apoderado')
def portal_apoderado():
    # 1. Seguridad
    if 'user_id' not in session or session.get('id_rol') != 2:
        return redirect(url_for('login'))
    
    id_apoderado = session['user_id']
    nombre_apoderado = session.get('nombre', 'Apoderado')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 2. Buscar al Alumno del Apoderado
    query_alumno = 'SELECT id_alumno FROM "Relacion_Apoderado" WHERE id_usuario = %s'
    cur.execute(query_alumno, (id_apoderado,))
    alumno_data = cur.fetchone()
    
    movimientos_reales = [] # Lista vacía por si no hay alumno
    
    if alumno_data:
        id_alumno = alumno_data[0]
        
        # 3. Buscar Asistencia (Últimos 30 días)
        query_asistencia = """
            SELECT fecha, hora_entrada, hora_salida 
            FROM "Asistencia" 
            WHERE id_alumno = %s 
            ORDER BY fecha DESC 
            LIMIT 30
        """
        cur.execute(query_asistencia, (id_alumno,))
        registros = cur.fetchall()
        
        # 4. Formatear datos para que se vean bonitos en la web
        for reg in registros:
            # Fecha: De 2026-01-13 a 13/01/2026
            fecha_fmt = reg[0].strftime('%d/%m/%Y') if reg[0] else "Fecha desc."
            
            # Entrada: De 08:00:00 a 08:00
            ent_fmt = str(reg[1])[:5] if reg[1] else "--:--"
            
            # Salida: Si es None, ponemos "PENDIENTE"
            if reg[2]:
                sal_fmt = str(reg[2])[:5] # Cortamos los segundos
            else:
                sal_fmt = "PENDIENTE"
            
            # Guardamos en la lista
            movimientos_reales.append({
                "fecha": fecha_fmt,
                "entrada": ent_fmt,
                "salida": sal_fmt
            })
            
    cur.close(); conn.close()

    # 5. Enviamos la lista REAL al HTML
    return render_template('portal_apoderado.html', movimientos=movimientos_reales)


 # Asegúrate de tener esto arriba en los imports:
# from datetime import datetime 

@app.route('/generar_reporte', methods=['POST'])
def generar_reporte():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    # 1. Recibir datos del formulario (Vienen como YYYY-MM-DD)
    fecha_inicio = request.form['fecha_inicio']
    fecha_fin = request.form['fecha_fin']
    id_apoderado = session['user_id']
    nombre_apoderado = session.get('nombre', 'Apoderado')

    # 🔴 NUEVO: Función para formatear fecha (de "2026-01-14" a "14/01/2026")
    def formatear(f):
        try:
            return datetime.strptime(f, '%Y-%m-%d').strftime('%d/%m/%Y')
        except:
            return f # Si falla, devuelve la original

    # 🔴 NUEVO: Creamos las variables "bonitas" para el PDF
    fecha_inicio_fmt = formatear(fecha_inicio)
    fecha_fin_fmt = formatear(fecha_fin)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 2. BUSCAR ALUMNO ASOCIADO
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

        # 3. BUSCAR ASISTENCIA (Usamos las fechas ORIGINALES para SQL)
        query_asistencia = """
            SELECT fecha, hora_entrada, hora_salida
            FROM "Asistencia"
            WHERE id_alumno = %s 
            AND fecha >= %s AND fecha <= %s
            ORDER BY fecha DESC
        """
        # Aquí usamos fecha_inicio (la cruda) porque la Base de Datos entiende YYYY-MM-DD
        cur.execute(query_asistencia, (id_alumno_real, fecha_inicio, fecha_fin))
        registros = cur.fetchall()

    except Exception as e:
        print(f"Error: {e}")
        return "Error generando el reporte", 500
    finally:
        cur.close()
        conn.close()

    # 4. RENDERIZAR HTML
    # 🔴 NUEVO: Aquí pasamos las fechas FORMATEDAS (fmt) y la fecha actual
    html = render_template('reporte_apoderado_pdf.html', 
                           alumno=alumno,
                           apoderado=nombre_apoderado,
                           desde=fecha_inicio_fmt,    # <--- La bonita
                           hasta=fecha_fin_fmt,       # <--- La bonita
                           registros=registros,
                           fecha_actual=datetime.now().strftime('%d/%m/%Y %H:%M')) # <--- Pie de página

    # 5. GENERAR PDF
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html), dest=pdf_buffer)

    if pisa_status.err:
        return "Hubo un error al crear el PDF", 500
    
    pdf_buffer.seek(0)
    
    return send_file(pdf_buffer, 
                     as_attachment=True, 
                     download_name=f"Reporte_Asistencia_{fecha_inicio}.pdf", 
                     mimetype='application/pdf')

# --- RUTA: ENVIAR AYUDA (SOLO UNA VEZ) ---
@app.route('/enviar_ayuda', methods=['POST'])
def enviar_ayuda():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    mensaje = request.form['mensaje_ayuda']
    id_usuario = session['user_id']
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Asegúrate de que la tabla "Solicitud_Ayuda" exista en tu BD
        query = 'INSERT INTO "Solicitud_Ayuda" (id_usuario_apo, mensaje) VALUES (%s, %s)'
        cur.execute(query, (id_usuario, mensaje))
        conn.commit()
        flash('✅ Tu mensaje ha sido enviado correctamente.', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error BD: {e}")
        flash('❌ Error al enviar el mensaje.', 'danger')
        
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('portal_apoderado'))

# --- GENERADOR DE REPORTES PDF - General ---
@app.route('/descargar_reporte')
def descargar_reporte():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 1. Capturar filtros de la URL
    curso_id = request.args.get('curso_id', type=int)
    fecha = request.args.get('fecha')
    
    if not curso_id or not fecha:
        flash('❌ Faltan datos para generar el reporte.', 'danger')
        return redirect(url_for('asistencia'))

    conn = get_db_connection()
    cur = conn.cursor()

    # 2. Obtener datos del Curso (para el título del reporte)
    cur.execute('SELECT nombre_curso FROM "Cursos" WHERE id_curso = %s', (curso_id,))
    nombre_curso = cur.fetchone()[0]

    # 3. Obtener la lista de asistencia (Misma lógica que la vista de asistencia)
    query = """
        SELECT 
            p.nombre,
            p.apellido_paterno,
            p.apellido_materno,
            u.rut,
            COALESCE(asi.id_estado, 1) as id_estado -- 1=Presente por defecto
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

    # 4. Renderizar el HTML del reporte (usaremos un template especial limpio)
    html = render_template('reporte_pdf.html', 
                           alumnos=alumnos, 
                           curso=nombre_curso, 
                           fecha=fecha)

    # 5. Convertir HTML a PDF en memoria
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html), dest=pdf_buffer)

    if pisa_status.err:
        return "Hubo un error al generar el PDF", 500

    pdf_buffer.seek(0)

    # 6. Enviar el archivo al navegador
    from flask import send_file
    return send_file(pdf_buffer, 
                     as_attachment=True, 
                     download_name=f"Asistencia_{nombre_curso}_{fecha}.pdf", 
                     mimetype='application/pdf')


if __name__ == '__main__':
    app.run(debug=True, port=5000)