from flask import Flask
from flask_bcrypt import Bcrypt
from config.db import get_db_connection

# Iniciamos herramientas de seguridad
app = Flask(__name__)
bcrypt = Bcrypt(app)

def crear_admin():
    print("--- 👤 Creando Usuario Administrador ---")
    
    # DATOS DE PRUEBA
    rut_admin = "11.111.111-1"
    clave_admin = "admin123"
    id_rol_admin = 1  # Usamos el 1 porque vimos en tu imagen que 1 = Administrador
    
    # 1. ENCRIPTAR LA CLAVE
    print(f"🔑 Encriptando clave '{clave_admin}'...")
    password_hash = bcrypt.generate_password_hash(clave_admin).decode('utf-8')
    
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            # 2. INSERTAR EN LA TABLA "Usuarios" (Con comillas dobles por la mayúscula)
            # OJO: Si el RUT ya existe, actualizamos su clave para que puedas entrar
            query = """
            INSERT INTO "Usuarios" (rut, password_hash, id_rol)
            VALUES (%s, %s, %s)
            ON CONFLICT (rut) 
            DO UPDATE SET password_hash = EXCLUDED.password_hash;
            """
            
            cur.execute(query, (rut_admin, password_hash, id_rol_admin))
            conn.commit()
            
            print("\n✅ ¡ÉXITO! Usuario guardado en la Base de Datos.")
            print(f"👉 RUT: {rut_admin}")
            print(f"👉 Clave: {clave_admin}")
            print("---------------------------------------------")
            print("Ahora ve a http://127.0.0.1:5000/login e intenta entrar.")
            
            cur.close()
            conn.close()
        except Exception as e:
            print(f"❌ Error al guardar: {e}")
    else:
        print("❌ No hay conexión a la base de datos.")

if __name__ == "__main__":
    crear_admin()