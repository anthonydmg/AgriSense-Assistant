from database import consultar_base_datos_real
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CREDENTIALS
import re

def obtener_lectura_actual(sensor):
    """Obtiene el valor más reciente de un sensor específico en la tabla de mediciones."""
    query = f"SELECT time, value FROM mediciones WHERE sensor = '{sensor}' ORDER BY time DESC LIMIT 1;"
    print(f"   [⚙️ Ejecutando SQL Real en TimescaleDB para {sensor} - Lectura Actual]")
    
    # NOTA: Descomentar las siguientes 3 líneas para pasar a producción con datos reales:
    # res = consultar_base_datos_real(query)
    # if isinstance(res, str): return {"error": res}
    # return {"sensor": sensor, "valor": res[0]['value']}
    
    unidades = {
        "temp_ambiente": "°C", "hum_ambiente": "%", "presion": "hPa",
        "temp_suelo": "°C", "hum_suelo": "%", "ph_suelo": "pH"
    }
    valores_mock = {
        "temp_ambiente": 24.5, "hum_ambiente": 65.2, "presion": 1013.2,
        "temp_suelo": 18.4, "hum_suelo": 45.1, "ph_suelo": 6.2
    }
    return {
        "sensor": sensor, 
        "valor": valores_mock.get(sensor, 0.0), 
        "unidad": unidades.get(sensor, "")
    }

def obtener_extremo_diario(sensor, tipo_extremo):
    """Obtiene el pico máximo o mínimo registrado durante el día en curso."""
    if tipo_extremo not in ["max", "min"]:
        return {"error": "El tipo de extremo debe especificarse rigurosamente como 'max' o 'min'."}
        
    funcion_sql = "MAX" if tipo_extremo == "max" else "MIN"
    query = f"SELECT {funcion_sql}(value) as extremo FROM mediciones WHERE sensor = '{sensor}' AND time >= CURRENT_DATE;"
    print(f"   [⚙️ Ejecutando SQL Real en TimescaleDB para {sensor} - Extremo {tipo_extremo}]")
    
    valores_mock = {"max": 28.5, "min": 14.2}
    return {
        "sensor": sensor, 
        "tipo_extremo": tipo_extremo, 
        "valor": valores_mock.get(tipo_extremo, 0.0)
    }

def analizar_tendencia_temporal(sensor, dias):
    """Calcula promedios móviles y tendencias vectoriales agregadas."""
    query = f"""
    SELECT AVG(value) as promedio 
    FROM mediciones 
    WHERE sensor = '{sensor}' AND time >= NOW() - INTERVAL '{dias} days';
    """
    print(f"   [⚙️ Ejecutando SQL Real en TimescaleDB para {sensor} - Tendencia {dias} días]")
    
    return {
        "sensor": sensor, 
        "tendencia": "alza_constante", 
        "promedio_semanal": 6.8
    }

def leer_datos_de_sensores(sensor: str, operacion: str, rango_horas: int = None, agrupacion_minutos: int = None, fecha_inicio: str = None, fecha_fin: str = None):
    """
    Ejecuta consultas estadísticas en PostgreSQL.
    Permite buscar por tiempo relativo (rango_horas) o tiempo absoluto (fechas con o sin hora).
    """
    sensores_validos = ["temp_ambiente", "hum_ambiente", "presion_atm", "temp_suelo", "hum_suelo", "ph_suelo"]
    operaciones_validas = {"PROMEDIO": "AVG", "MAXIMO": "MAX", "MINIMO": "MIN", "ULTIMO": "LAST"}
    unidades = {
        "temp_ambiente": "°C", "hum_ambiente": "%", "presion": "hPa",
        "temp_suelo": "°C", "hum_suelo": "%", "ph_suelo": "pH"
    }
    if sensor not in sensores_validos:
        return {"error": f"El sensor '{sensor}' no es válido."}
        
    op_sql = operaciones_validas.get(operacion.upper())
    if not op_sql:
        return {"error": "Operación no válida. Usa PROMEDIO, MAXIMO, MINIMO o ULTIMO."}

    # Patrón: Acepta "YYYY-MM-DD" o "YYYY-MM-DD HH:MM"
    patron_fecha = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**DB_CREDENTIALS)
        cursor = conn.cursor(cursor_factory=RealDictCursor) 
        
        filtros_sql = []
        parametros_sql = []

        # 1. CONSTRUCCIÓN DINÁMICA DEL FILTRO DE TIEMPO
        if fecha_inicio and fecha_fin:
            if not patron_fecha.match(fecha_inicio) or not patron_fecha.match(fecha_fin):
                return {"error": "Formato inválido. Usa 'YYYY-MM-DD' o 'YYYY-MM-DD HH:MM'."}
            
            # Autocompletado inteligente para días completos
            if len(fecha_inicio) == 10: fecha_inicio += " 00:00:00"
            if len(fecha_fin) == 10: fecha_fin += " 23:59:59"
            
            filtros_sql.append("fecha >= %s::timestamp AND fecha <= %s::timestamp")
            parametros_sql.extend([fecha_inicio, fecha_fin])
            
        elif rango_horas:
            filtros_sql.append(f"fecha >= NOW() - INTERVAL '{int(rango_horas)} hours'")
        elif operacion.upper() == "ULTIMO":
            filtros_sql.append(f"fecha >= NOW() - INTERVAL '1 hours'")
        else:
            return {"error": "Provee 'rango_horas' o un par de fechas ('fecha_inicio' y 'fecha_fin')."}
            
        clausula_where = " AND ".join(filtros_sql)

        # 2. EJECUCIÓN DE LA CONSULTA (Tres Casos)
        
        # CASO A: ULTIMO (Dato en tiempo real)
        if operacion.upper() == "ULTIMO":
            query = f"""
                SELECT {sensor} AS valor_calculado
                FROM mediciones_sensores
                WHERE {clausula_where}
                ORDER BY fecha DESC
                LIMIT 1;
            """
            print(f"\n query = \n {query}")
            cursor.execute(query, tuple(parametros_sql))
            resultado = cursor.fetchone()
            valor = round(resultado["valor_calculado"], 2) if resultado and resultado["valor_calculado"] is not None else None
            return {"tipo": "valor_unico", "sensor": sensor, "unidad": unidades[sensor], "operacion": "ULTIMO", "valor": valor}

        # CASO B: Agrupación temporal (Tendencias en Postgres nativo)
        elif agrupacion_minutos:
            query = f"""
                SELECT 
                    TO_TIMESTAMP(FLOOR(EXTRACT(epoch FROM fecha) / ({agrupacion_minutos} * 60)) * ({agrupacion_minutos} * 60)) AS intervalo_tiempo,
                    {op_sql}({sensor}) AS valor_calculado
                FROM mediciones_sensores
                WHERE {clausula_where}
                GROUP BY intervalo_tiempo
                ORDER BY intervalo_tiempo ASC;
            """
            print(f"\n query = \n {query}")
            cursor.execute(query, tuple(parametros_sql))
            resultados = cursor.fetchall()
            datos_limpios = [
                {"fecha": row["intervalo_tiempo"].strftime("%Y-%m-%d %H:%M"), "valor": round(row["valor_calculado"], 2) if row["valor_calculado"] is not None else None} 
                for row in resultados
            ]
            return {"tipo": "serie_temporal", "sensor": sensor, "unidad": unidades[sensor], "operacion": operacion, "datos": datos_limpios}

        # CASO C: Valor absoluto del rango temporal
        else:
            query = f"""
                SELECT {op_sql}({sensor}) AS valor_calculado
                FROM mediciones_sensores
                WHERE {clausula_where};
            """
            print(f"\n query = \n {query}")
            cursor.execute(query, tuple(parametros_sql))
            resultado = cursor.fetchone()
            valor = round(resultado["valor_calculado"], 2) if resultado and resultado["valor_calculado"] is not None else None
            return {"tipo": "valor_unico", "sensor": sensor, "unidad": unidades[sensor], "operacion": operacion, "valor": valor}

    except Exception as e:
        return {"error": f"Error de ejecución: {str(e)}"}
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Enrutador para mapeo dinámico del Agente
diccionario_herramientas = {
    "leer_datos_de_sensores": leer_datos_de_sensores
    #"obtener_lectura_actual": obtener_lectura_actual,
    #"obtener_extremo_diario": obtener_extremo_diario,
    #"analizar_tendencia_temporal": analizar_tendencia_temporal
}