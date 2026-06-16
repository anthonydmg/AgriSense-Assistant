import psycopg2
from psycopg2 import extras
import csv
import math
import random
from datetime import datetime, timedelta
from config import DB_CREDENTIALS

def generar_datos_estacion(dias=21, intervalo_minutos=10, archivo_salida='datos_estacion.csv'):
    # Configuración inicial
    fecha_inicio = datetime.now() - timedelta(days=dias)
    total_registros = int((dias * 24 * 60) / intervalo_minutos)
    
    print(f"Generando {total_registros} registros para {dias} días...")

    with open(archivo_salida, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Cabeceras (Tu esquema exacto)
        writer.writerow(['fecha', 'temp_amb', 'hum_amb', 'presion', 'temp_suelo', 'hum_suelo', 'ph_suelo'])

        # Variables base para simular tendencias lentas
        humedad_suelo_base = 25.0
        ph_suelo_base = 6.2

        for i in range(total_registros):
            fecha_actual = fecha_inicio + timedelta(minutes=intervalo_minutos * i)
            
            # Usamos la hora del día (0-23.99) para los ciclos
            hora_decimal = fecha_actual.hour + (fecha_actual.minute / 60.0)
            
            # 1. Temperatura Ambiental (Ciclo diurno: pico a las 14:00, mínimo a las 04:00)
            # Offset de -4 horas para alinear el seno con las horas reales
            temp_base = 24.5 + 3.5 * math.sin(math.pi * (hora_decimal - 8) / 12.0)
            temp_amb = max(21.0, min(28.0, temp_base + random.gauss(0, 0.3)))
            
            # 2. Humedad Ambiental (Inversamente proporcional a la temperatura)
            hum_base = 87.0 - 3.0 * math.sin(math.pi * (hora_decimal - 8) / 12.0)
            hum_amb = max(84.0, min(90.0, hum_base + random.gauss(0, 0.5)))
            
            # 3. Presión Atmosférica (Relativamente estable)
            presion = 1012.0 + random.gauss(0, 1.5)
            
            # 4. Temperatura del Suelo (Sigue a la temp ambiental pero con retraso y menos variación)
            temp_suelo_base = 18.0 + 4.0 * math.sin(math.pi * (hora_decimal - 10) / 12.0)
            temp_suelo = temp_suelo_base + random.gauss(0, 0.2)
            
            # 5. Humedad del Suelo (Baja lentamente, simula que se seca el campo)
            humedad_suelo_base -= 0.005 # Se seca un poquito cada 10 minutos
            # Simulamos un riego cada 7 días
            if i > 0 and i % (7 * 24 * 6) == 0:
                humedad_suelo_base = 40.0 
            hum_suelo = min(100.0, max(0.0, humedad_suelo_base + random.gauss(0, 0.5)))
            
            # 6. pH del Suelo (Muy estable, cambia poquísimo)
            ph_suelo = ph_suelo_base + random.gauss(0, 0.02)
            
            # Formatear a 2 decimales y guardar
            writer.writerow([
                fecha_actual.strftime('%Y-%m-%d %H:%M:%S'),
                round(temp_amb, 2),
                round(hum_amb, 2),
                round(presion, 2),
                round(temp_suelo, 2),
                round(hum_suelo, 2),
                round(ph_suelo, 2)
            ])

    print(f"¡Listo! Datos guardados en {archivo_salida}")

# Ejecutar para 21 días (3 semanas)

def inicializar_postgres(csv_path='datos_estacion.csv'):
    try:
        print("🔌 Conectando a PostgreSQL...")
        conexion = psycopg2.connect(**DB_CREDENTIALS)
        cursor = conexion.cursor()

        # 2. Crear el esquema de la tabla (Usando tipos de Postgres)
        print("🏗️ Creando la tabla 'mediciones_sensores'...")

        cursor.execute("""
            SELECT to_regclass('public.mediciones_sensores');
        """)

        if cursor.fetchone()[0] is not None:
            cursor.execute("""
                TRUNCATE TABLE mediciones_sensores RESTART IDENTITY;
            """) 


        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mediciones_sensores (
                id SERIAL PRIMARY KEY,
                fecha TIMESTAMP,
                temp_ambiente NUMERIC(5,2),
                hum_ambiente NUMERIC(5,2),
                presion_atm NUMERIC(6,2),
                temp_suelo NUMERIC(5,2),
                hum_suelo NUMERIC(5,2),
                ph_suelo NUMERIC(4,2)
            )
        ''')
        
        # Limpiamos la tabla por si ya tenía datos
        cursor.execute('TRUNCATE TABLE mediciones_sensores RESTART IDENTITY;')

        # 3. Leer el CSV
        print(f"📖 Leyendo datos desde {csv_path}...")
        with open(csv_path, mode='r', encoding='utf-8') as archivo_csv:
            lector = csv.reader(archivo_csv)
            next(lector) # Saltamos la primera fila (cabeceras)
            
            # Extraemos todas las filas en una lista
            datos_a_insertar = [tuple(fila) for fila in lector]
            
            # 4. Inserción masiva ultra-rápida (Bulk Insert)
            print("🚀 Insertando datos en bloque...")
            query_insert = '''
                INSERT INTO mediciones_sensores 
                (fecha, temp_ambiente, hum_ambiente, presion_atm, temp_suelo, hum_suelo, ph_suelo) 
                VALUES %s
            '''
            
            # execute_values es una función especial de Postgres para máxima velocidad
            extras.execute_values(cursor, query_insert, datos_a_insertar)
            
            # Guardamos los cambios
            conexion.commit()
            print(f"✅ ¡Éxito! Se insertaron los registros correctamente en PostgreSQL.")

    except psycopg2.OperationalError as e:
        print(f"❌ Error de Conexión: Verifica tus credenciales o si el servidor Postgres está encendido.\nDetalle: {e}")
    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
        if conexion:
            conexion.rollback() # Deshace los cambios si hubo un error
    finally:
        if 'conexion' in locals() and conexion:
            cursor.close()
            conexion.close()
            print("🔒 Conexión cerrada.")

if __name__ == "__main__":
    generar_datos_estacion(dias=120)
    inicializar_postgres()