from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt 
from config.db import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash

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
@app.route('/dashboard')
def dashboard():
    # 1. ¿Está logueado?
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 2. ¿Es Administrador? (Doble chequeo de seguridad)
    if session.get('id_rol') != 1:
        flash('Acceso denegado: No tienes permisos de Administrador.', 'danger')
        return redirect(url_for('login'))

    # ... (Aquí sigue el resto de tu código de contadores que hicimos recién) ...
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM "Usuarios"')
    total_usuarios = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM "Alumnos"')
    total_alumnos = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', total_usuarios=total_usuarios, total_alumnos=total_alumnos)
  

# --- RUTA DE LOGIN (LA LÓGICA REAL) ---
# --- RUTA DE INICIO / LOGIN ---
# Agregamos ambas líneas para que entre por cualquiera de las dos
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        rut = request.form['rut']
        clave = request.form['clave']
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Validamos usuario y traemos su ROL (columna 3)
        cur.execute('SELECT id_usuario, rut, password_hash, id_rol FROM "Usuarios" WHERE rut = %s', (rut,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        # COMENTARIO PARA DEBUG DE LA CLAVE 
        #if user:
        #    print("--- INICIO DEBUG ---")
        #    print(f"1. RUT en BD:   '{user[1]}'") # user[1] es el RUT
        #   print(f"2. RUT tipeado: '{rut}'")
        #    print(f"3. Hash en BD:  '{user[2]}'") # user[2] es el Hash
        #    print(f"4. Clave tipeada: '{clave}'")
        #    es_valido = check_password_hash(user[2], clave)
        #    print(f"5. ¿Coinciden?: {es_valido}")
        #    print("--- FIN DEBUG ---")
        #else:
        #    print("--- DEBUG: NO SE ENCONTRÓ EL USUARIO EN LA BD ---")
        
        if user and check_password_hash(user[2], clave):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['id_rol'] = user[3] # Guardamos el Rol (1, 2 o 3)
            
            # --- SEMÁFORO DE SEGURIDAD (ACTUALIZADO) ---
            if session['id_rol'] == 1:
                # Si es Admin (1) -> Va al Dashboard Azul
                return redirect(url_for('dashboard'))
            
            elif session['id_rol'] == 2:
                # ¡NUEVO! Si es Apoderado (2) -> Va a su Portal Verde
                return redirect(url_for('portal_apoderado'))
                
            else:
                # Si es Alumno (3) -> Sigue en construcción
                session.clear()
                flash('Tu portal de Alumno está en construcción.', 'info')
                return redirect(url_for('login'))
            
        else:
            flash('RUT o contraseña incorrectos', 'danger')
            
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

# --- RUTA PARA VER USUARIOS (GESTIÓN) ---
@app.route('/usuarios')
def usuarios():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        
        # --- AQUÍ ESTÁ LA MAGIA DEL SQL ---
        # Usamos LEFT JOIN en Perfiles por si acaso hay algún usuario antiguo
        # que no tenga perfil (como el admin original), para que no desaparezca.
        query = """
        SELECT 
            u.id_usuario, 
            u.rut, 
            r.nombre_rol, 
            p.nombre, 
            p.apellido_paterno,
            p.apellido_materno
        FROM "Usuarios" u
        JOIN "Roles" r ON u.id_rol = r.id_rol
        LEFT JOIN "Perfiles" p ON u.id_usuario = p.id_usuario
        ORDER BY u.id_usuario ASC;
        """
        cur.execute(query)
        lista_usuarios = cur.fetchall()
        cur.close()
        conn.close()
        
        return render_template('usuarios.html', usuarios=lista_usuarios)

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

# --- RUTA PARA ELIMINAR USUARIO ---
@app.route('/eliminar_usuario/<int:id_usuario>')
def eliminar_usuario(id_usuario):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Protección: No dejar que el admin se borre a sí mismo
    if id_usuario == session['user_id']:
        flash('¡No puedes eliminar tu propia cuenta mientras estás conectado!', 'danger')
        return redirect(url_for('usuarios'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. Borramos primero el Perfil asociado (si existe)
        cur.execute('DELETE FROM "Perfiles" WHERE id_usuario = %s', (id_usuario,))
        
        # 2. Ahora sí borramos el Usuario
        cur.execute('DELETE FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
        
        conn.commit()
        flash('Usuario eliminado correctamente.', 'success')
    except Exception as e:
        conn.rollback()
        # Este mensaje saldrá si intentas borrar a un alumno que ya tiene notas o asistencia
        # (La base de datos protege la integridad de los datos)
        flash(f'No se pudo eliminar: El usuario tiene datos relacionados (Asistencia/Cursos).', 'danger')
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('usuarios'))

# --- RUTA PARA EDITAR USUARIO (VERSIÓN CORREGIDA) ---
@app.route('/editar_usuario/<int:id_usuario>', methods=['GET', 'POST'])
def editar_usuario(id_usuario):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # BLOQUE 1: PROCESAR EL GUARDADO (POST)
    if request.method == 'POST':
        rut = request.form['rut']
        id_rol = request.form['id_rol']
        nombre = request.form['nombre']
        app_paterno = request.form['app_paterno']
        app_materno = request.form['app_materno']
        nueva_clave = request.form['clave']

        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # 1. Actualizar Tabla USUARIOS (Credenciales)
            if nueva_clave:
                clave_hash = generate_password_hash(nueva_clave)
                cur.execute("""
                    UPDATE "Usuarios"
                    SET rut = %s, id_rol = %s, password_hash = %s
                    WHERE id_usuario = %s
                """, (rut, id_rol, clave_hash, id_usuario))
            else:
                cur.execute("""
                    UPDATE "Usuarios"
                    SET rut = %s, id_rol = %s
                    WHERE id_usuario = %s
                """, (rut, id_rol, id_usuario))

            # 2. Lógica Inteligente para Perfiles (Upsert)
            cur.execute('SELECT 1 FROM "Perfiles" WHERE id_usuario = %s', (id_usuario,))
            existe_perfil = cur.fetchone()

            if existe_perfil:
                # Si existe, actualizamos
                cur.execute("""
                    UPDATE "Perfiles"
                    SET nombre = %s, apellido_paterno = %s, apellido_materno = %s
                    WHERE id_usuario = %s
                """, (nombre, app_paterno, app_materno, id_usuario))
            else:
                # Si no existe (usuarios antiguos), creamos
                cur.execute("""
                    INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno)
                    VALUES (%s, %s, %s, %s)
                """, (id_usuario, nombre, app_paterno, app_materno))

            conn.commit()
            flash('Usuario actualizado correctamente.', 'success')
            return redirect(url_for('usuarios'))

        except Exception as e:
            conn.rollback()
            flash(f'Error al actualizar: {e}', 'danger')
            return redirect(url_for('usuarios')) # En caso de error, volvemos a la lista
        
        finally:
            cur.close()
            conn.close()

    # BLOQUE 2: MOSTRAR EL FORMULARIO (GET)
    # Solo llegamos aquí si NO es un POST (es decir, cuando entras a ver la página)
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT u.rut, u.id_rol, p.nombre, p.apellido_paterno, p.apellido_materno
        FROM "Usuarios" u
        LEFT JOIN "Perfiles" p ON u.id_usuario = p.id_usuario
        WHERE u.id_usuario = %s
    """, (id_usuario,))
    usuario_data = cur.fetchone()
    
    cur.close()
    conn.close()

    if usuario_data:
        return render_template('editar_usuario.html', usuario=usuario_data, id_usuario=id_usuario)
    else:
        return redirect(url_for('usuarios'))

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

# --- RUTA: MOSTRAR LA PLANILLA (PASO 2) ---
@app.route('/tomar_asistencia', methods=['GET'])
def tomar_asistencia():
    if 'user_id' not in session or session.get('id_rol') != 1:
        return redirect(url_for('login'))

    # Recibimos los datos del selector
    id_curso = request.args.get('id_curso')
    fecha = request.args.get('fecha')

    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Obtener nombre del curso (para el título)
    cur.execute('SELECT nombre_curso FROM "Cursos" WHERE id_curso = %s', (id_curso,))
    datos_curso = cur.fetchone()
    nombre_curso = datos_curso[0] if datos_curso else "Curso Desconocido"

    # 2. TRAER ALUMNOS + SU ASISTENCIA (Si existe)
    # Esta es la consulta "inteligente" (LEFT JOIN)
    query = """
        SELECT 
            A.id_alumno, 
            U.rut, 
            P.nombre, 
            P.apellido_paterno,
            Asis.id_estado,     -- Si ya se tomó, vendrá el estado (1, 2, etc.)
            Asis.hora_entrada,  -- Si ya se tomó, vendrá la hora
            Asis.hora_salida    -- Si ya se tomó, vendrá la hora
        FROM "Alumnos" A
        JOIN "Perfiles" P ON A.id_perfil = P.id_perfil
        JOIN "Usuarios" U ON P.id_usuario = U.id_usuario
        LEFT JOIN "Asistencia" Asis ON A.id_alumno = Asis.id_alumno AND Asis.fecha = %s
        WHERE A.id_curso = %s
        ORDER BY P.apellido_paterno ASC
    """
    cur.execute(query, (fecha, id_curso))
    lista_alumnos = cur.fetchall()

    # 3. Traer los estados posibles (Presente, Ausente...) para el menú desplegable
    cur.execute('SELECT id_estado, nombre_estado FROM "Estados_Asistencia" ORDER BY id_estado ASC')
    lista_estados = cur.fetchall()

    cur.close()
    conn.close()

# TRANSFORMACIÓN DE FECHA
    from datetime import datetime
    fecha_dt = datetime.strptime(fecha, '%Y-%m-%d') # Convertimos texto a Objeto Fecha
    fecha_bonita = fecha_dt.strftime('%d-%m-%Y')    # Convertimos Objeto a Texto "12-01-2026"

    return render_template('tomar_asistencia.html', 
                           alumnos=lista_alumnos, 
                           estados=lista_estados, 
                           curso=nombre_curso, 
                           fecha=fecha,
                           fecha_bonita=fecha_bonita,
                           id_curso=id_curso)

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


# --- RUTA: PORTAL APODERADO ---
@app.route('/portal_apoderado')
def portal_apoderado():
    # 1. Seguridad básica
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 2. Datos simulados (Esto alimenta la tabla de Entradas/Salidas del HTML)
    # En el futuro, esto vendrá de una consulta SQL a la tabla "Asistencia"
    datos_movimientos = [
        {"fecha": "13/01/2026", "entrada": "07:58 AM", "salida": "PENDIENTE"},
        {"fecha": "12/01/2026", "entrada": "08:05 AM", "salida": "16:15 PM"},
        {"fecha": "11/01/2026", "entrada": "08:00 AM", "salida": "16:00 PM"},
    ]

    # 3. Renderizamos tu archivo HTML
    return render_template('portal_apoderado.html', movimientos=datos_movimientos)

# --- RUTA: RECIBIR AYUDA (Botón Verde) ---
@app.route('/enviar_ayuda', methods=['POST'])
def enviar_ayuda():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    mensaje = request.form['mensaje_ayuda']
    # Aquí iría el INSERT a la base de datos "Solicitud_Ayuda"
    # Por ahora solo simulamos que funciona:
    
    flash('✅ Tu solicitud de ayuda ha sido enviada correctamente.', 'success')
    return redirect(url_for('portal_apoderado'))


 # --- RUTA: GENERAR PDF (Botón Azul) ---
@app.route('/generar_reporte', methods=['POST'])
def generar_reporte():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Recogemos las fechas del modal
    f_inicio = request.form['fecha_inicio']
    f_fin = request.form['fecha_fin']
    
    # (Aquí va tu código de ReportLab que genera el PDF)
    # Si quieres probar rápido sin PDF real, usa esto temporalmente:
    flash(f'Generando reporte desde {f_inicio} hasta {f_fin}... (Simulado)', 'info')
    return redirect(url_for('portal_apoderado'))   



if __name__ == '__main__':
    app.run(debug=True, port=5000)