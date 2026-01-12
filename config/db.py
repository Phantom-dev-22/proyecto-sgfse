import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def get_db_connection():
    try:
        # Obtenemos el esquema del .env (si no existe, usa 'public' por defecto)
        schema = os.getenv('DB_SCHEMA', 'public')
        
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            port=os.getenv('DB_PORT'),
            # ESTA LINEA ES CLAVE: Le dice a PostgreSQL dónde buscar tus tablas
            options=f"-c search_path={schema},public"
        )
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        return None