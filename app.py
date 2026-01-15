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

app = Flask(__name__)

# CONFIGURACIÓN DE SEGURIDAD
app.secret_key = "tesis_mauricio_secret_key" 
bcrypt = Bcrypt(app) 

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


# --- RUTA DE LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        rut = request.form['rut']
        clave = request.form['clave']
        
        rol_entrada = request.form.get('rol_entrada') 

        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT u.id_usuario, u.rut, u.password_hash, u.id_rol, p.nombre, p.apellido_paterno FROM "Usuarios" u LEFT JOIN "Perfiles" p ON u.id_usuario = p.id_usuario WHERE u.rut = %s', (rut,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user[2], clave):
            id_rol_real = user[3] 

            # Validación estricta
            if str(id_rol_real) != str(rol_entrada):
                flash('⛔ Error de Seguridad: Estás intentando ingresar por el portal equivocado.', 'danger')
                return redirect(url_for('home')) 

            session['user_id'] = user[0]
            session['id_rol'] = id_rol_real
            session['nombre'] = f"{user[4]} {user[5]}" if user[4] else user[1]

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
        where_clause = """
            WHERE (u.rut ILIKE %s OR 
                   p.nombre ILIKE %s OR 
                   p.apellido_paterno ILIKE %s OR 
                   p.apellido_materno ILIKE %s)
        """
        # El símbolo % es el comodín para buscar "que contenga el texto"
        termino = f"%{busqueda}%"
        params_count = [termino, termino, termino, termino]
        params_query = [termino, termino, termino, termino]

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

@app.route('/crear_usuario', methods=['GET', 'POST'])
def crear_usuario():
    if request.method == 'POST':
        rut = request.form['rut']
        clave_plana = request.form['clave']
        id_rol = request.form['id_rol']
        
        nombre = request.form['nombre']
        app_paterno = request.form['app_paterno']
        app_materno = request.form['app_materno']

        clave_encriptada = generate_password_hash(clave_plana)

        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO "Usuarios" (rut, password_hash, id_rol)
                VALUES (%s, %s, %s)
                RETURNING id_usuario;
            """, (rut, clave_encriptada, id_rol))
            
            nuevo_id_usuario = cur.fetchone()[0]

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

# --- RUTA: ELIMINAR USUARIO ---
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
            
            if rol == 3: # Alumno
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
                    cur.execute('DELETE FROM "Asistencia" WHERE id_alumno = %s', (id_alum_int,))
                    cur.execute('DELETE FROM "Relacion_Apoderado" WHERE id_alumno = %s', (id_alum_int,))
                    cur.execute('DELETE FROM "Alumnos" WHERE id_alumno = %s', (id_alum_int,))

            elif rol == 2: # Apoderado
                # Si la tabla Solicitud_Ayuda aún existe, borramos los registros, si no, ignora esto
                try:
                     cur.execute('DELETE FROM "Solicitud_Ayuda" WHERE id_usuario_apo = %s', (id_usuario,))
                except:
                     pass # Si la tabla no existe, no pasa nada
                     
                cur.execute('DELETE FROM "Relacion_Apoderado" WHERE id_usuario = %s', (id_usuario,))

            cur.execute('DELETE FROM "Perfiles" WHERE id_usuario = %s', (id_usuario,))
            cur.execute('DELETE FROM "Usuarios" WHERE id_usuario = %s', (id_usuario,))
            
            conn.commit()
            flash('✅ Usuario eliminado correctamente.', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"Error detallado al eliminar: {e}") 
        flash('❌ Error al eliminar el usuario.', 'danger')
        
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

# --- RUTAS ELIMINADAS (COMENTADAS O BORRADAS) ---
# @app.route('/enviar_ayuda')...
# @app.route('/resolver_solicitud')...

if __name__ == '__main__':
    app.run(debug=True, port=5000)