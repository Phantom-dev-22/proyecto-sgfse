import random
from werkzeug.security import generate_password_hash
from config.db import get_db_connection

# --- DATOS PARA GENERAR ---
nombres_h = ["Agustín", "Vicente", "Martín", "Matías", "Benjamín", "Tomás", "Alonso", "Maxi", "Joaquín", "Cristóbal"]
nombres_m = ["Sofía", "Emilia", "Isidora", "Trinidad", "Florencia", "Maite", "Josefa", "Amanda", "Antonella", "Catalina"]
apellidos = ["Tapia", "Reyes", "Fuentes", "Castillo", "Espinoza", "Lagos", "Pizarro", "Saavedra", "Carrasco", "Barraza"]

def poblar():
    conn = get_db_connection()
    if conn is None:
        return

    cur = conn.cursor()
    print("🚀 Iniciando carga de alumnos para 1° BÁSICO (A y B)...")

    # Generamos 12 alumnos nuevos
    for i in range(1, 13): 
        try:
            # --- 1. CREAR ALUMNO ---
            # Usamos 24.000... para que sean nuevos y no choquen con los anteriores
            rut_alum = f"24.000.{i:03d}-K"
            nombre_alum = random.choice(nombres_h + nombres_m)
            ape_alum = random.choice(apellidos)
            
            cur.execute('INSERT INTO "Usuarios" (rut, password_hash, id_rol) VALUES (%s, %s, 3) RETURNING id_usuario', 
                        (rut_alum, generate_password_hash(rut_alum)))
            id_usr_alum = cur.fetchone()[0]

            cur.execute('INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno) VALUES (%s, %s, %s, %s) RETURNING id_perfil',
                        (id_usr_alum, nombre_alum, ape_alum, "Vargas"))
            id_perfil_alum = cur.fetchone()[0]

            # --- LA CORRECCIÓN CLAVE ---
            # Si es par va al ID 4 (1° B), si es impar va al ID 3 (1° A)
            id_curso = 4 if i % 2 == 0 else 3
            nombre_curso = "1° Básico B" if id_curso == 4 else "1° Básico A"
            
            cur.execute('INSERT INTO "Alumnos" (id_perfil, id_curso, fecha_nacimiento, sexo, direccion) VALUES (%s, %s, %s, %s, %s) RETURNING id_alumno',
                        (id_perfil_alum, id_curso, '2016-06-20', 'M', 'Calle Nueva 456'))
            id_alumno_real = cur.fetchone()[0]


            # --- 2. CREAR APODERADO ---
            rut_apo = f"14.000.{i:03d}-K" 
            nombre_apo = random.choice(nombres_h + nombres_m)
            
            cur.execute('INSERT INTO "Usuarios" (rut, password_hash, id_rol) VALUES (%s, %s, 2) RETURNING id_usuario', 
                        (rut_apo, generate_password_hash(rut_apo)))
            id_usr_apo = cur.fetchone()[0]

            cur.execute('INSERT INTO "Perfiles" (id_usuario, nombre, apellido_paterno, apellido_materno) VALUES (%s, %s, %s, %s)',
                        (id_usr_apo, nombre_apo, ape_alum, "Cortés"))

            # --- 3. VINCULAR ---
            cur.execute('INSERT INTO "Relacion_Apoderado" (id_usuario, id_alumno, parentesco, telefono, email_contacto) VALUES (%s, %s, %s, %s, %s)',
                        (id_usr_apo, id_alumno_real, "Padre/Madre", "+56987654321", "nuevo@test.com"))

            print(f"✅ Alumno {nombre_alum} matriculado en -> {nombre_curso}")

        except Exception as e:
            print(f"⚠️ Error: {e}")
            conn.rollback()

    conn.commit()
    cur.close()
    conn.close()
    print("\n✨ ¡Listo! Ahora revisa los cursos de 1° Básico.")

if __name__ == "__main__":
    poblar()