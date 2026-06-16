import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CREDENTIALS

def consultar_base_datos_real(query_generada_por_llm):
    """
    Ejecuta consultas nativas generadas o requeridas en TimescaleDB.
    Retorna listas de diccionarios limpios utilizando RealDictCursor.
    """
    try:
        conexion = psycopg2.connect(**DB_CREDENTIALS)
        cursor = conexion.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(query_generada_por_llm)
        resultados = cursor.fetchall()
        
        cursor.close()
        conexion.close()
        
        if not resultados:
            return "No se encontraron datos para esa consulta."
            
        return [dict(fila) for fila in resultados]
        
    except psycopg2.Error as e:
        return f"Error de sintaxis en PostgreSQL: {e}"