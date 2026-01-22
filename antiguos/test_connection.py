from config.db import get_db_connection

print("--- Iniciando prueba de conexión ---")

try:
    conn = get_db_connection()
    if conn:
        print("✅ ¡ÉXITO TOTAL! Python se conectó a la Base de Datos.")
        
        # Vamos a pedirle que busque a un alumno para estar 100% seguros
        cur = conn.cursor()
        cur.execute('SELECT version();')
        version = cur.fetchone()
        print(f"📡 Conectado a: {version[0]}")
        
        cur.close()
        conn.close()
    else:
        print("❌ Error: La conexión falló (retornó None).")
except Exception as e:
    print(f"❌ Error Crítico: {e}")

print("--- Fin de la prueba ---")