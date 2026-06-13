import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor

def obtener_lectura_actual(sensor):
    # Aquí iría: cursor.execute("SELECT value FROM mediciones WHERE sensor = %s ORDER BY time DESC LIMIT 1", (sensor,))
    print(f"   [⚙️ Ejecutando SQL Real en TimescaleDB para {sensor} - Lectura Actual]")
    return {"sensor": sensor, "valor": 24.5, "unidad": "°C"} # Dato simulado

def obtener_extremo_diario(sensor, tipo_extremo):
    # Aquí iría el SQL con MAX() o MIN() filtrado por el día de hoy
    print(f"   [⚙️ Ejecutando SQL Real en TimescaleDB para {sensor} - Extremo {tipo_extremo}]")
    return {"sensor": sensor, "tipo_extremo": tipo_extremo, "valor": 28.5} # Dato simulado

def analizar_tendencia_temporal(sensor, dias):
    # Aquí iría el SQL para calcular la media móvil (Moving Average)
    print(f"   [⚙️ Ejecutando SQL Real en TimescaleDB para {sensor} - Tendencia {dias} días]")
    return {"sensor": sensor, "tendencia": "alza_constante", "promedio_semanal": 6.8} # Dato simulado

# Diccionario de enrutamiento: Conecta el texto del LLM con la función de Python
diccionario_herramientas = {
    "obtener_lectura_actual": obtener_lectura_actual,
    "obtener_extremo_diario": obtener_extremo_diario,
    "analizar_tendencia_temporal": analizar_tendencia_temporal
}

# ==========================================
# 1. FUNCIÓN DE EJECUCIÓN (CONEXIÓN A GEMMA 4)
# ==========================================

def consultar_base_datos_real(query_generada_por_llm):
    # Usa las mismas credenciales que configuraste en el script de carga
    credenciales = {
        "dbname": "develop", "user": "postgres", 
        "password": "admin", "host": "localhost", "port": "5432"
    }
    
    try:
        conexion = psycopg2.connect(**credenciales)
        # RealDictCursor hace que los resultados salgan como Diccionarios (JSON) automáticamente
        cursor = conexion.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(query_generada_por_llm)
        resultados = cursor.fetchall()
        conexion.close()
        
        if not resultados:
            return "No se encontraron datos para esa consulta."
            
        # Convertimos la salida de Postgres a una lista estándar de Python
        return [dict(fila) for fila in resultados]
        
    except psycopg2.Error as e:
        # El Agente Crítico usará este mensaje para corregir a Gemma 4
        return f"Error de sintaxis en PostgreSQL: {e}"
    

# ==========================================

def llamar_gemma4_stream(mensajes, tipo_fase="PROCESANDO"):
    """
    Se comunica con Ollama usando streaming.
    Muestra en tiempo real el pensamiento y captura el JSON final.
    """
    url = "http://localhost:11434/api/chat"
    
    payload = {
        "model": "gemma4:26b", 
        "messages": mensajes,
        "format": "json", 
        "stream": True,    # ¡ACTIVADO!
        "think": True,
        "options": {
            "temperature": 0.2 
        }
    }
    
    try:
        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()
        
        texto_json_acumulado = ""
        imprimió_encabezado_pensamiento = False
        imprimió_encabezado_json = False
        
        # Iteramos sobre cada línea que nos escupe el servidor local de Ollama
        for linea in response.iter_lines():
            if not linea:
                continue
                
            # Ollama responde con un objeto JSON por cada token
            chunk = json.loads(linea.decode('utf-8'))
            
            # 1. CAPTURA DEL PENSAMIENTO NATIVO (Streaming)
            # Dependiendo de tu versión de Ollama, el token de pensamiento viene en 'thinking'
            pensamiento_chunk = chunk.get("message", {}).get("thinking", "")
            if pensamiento_chunk:
                if not imprimió_encabezado_pensamiento:
                    print(f"\n🧠 [PENSAMIENTO NATIVO - {tipo_fase}]:")
                    imprimió_encabezado_pensamiento = True
                print(pensamiento_chunk, end="", flush=True)
                continue # Saltamos al siguiente token si es solo pensamiento
            
            # 2. CAPTURA DE LA RESPUESTA ESTRUCTURADA (Streaming)
            contenido_chunk = chunk.get("message", {}).get("content", "")
            if contenido_chunk:
                if not imprimió_encabezado_json:
                    # Si venía de mostrar pensamiento, agregamos un salto de línea decorativo
                    if imprimió_encabezado_pensamiento:
                        print("\n") 
                    print(f"✨ [GENERANDO SALIDA ESTRUCTURADA...]")
                    imprimió_encabezado_json = True
                
                # Acumulamos los fragmentos del string JSON
                texto_json_acumulado += contenido_chunk
                # Opcional: Puedes descomentar la línea de abajo si quieres ver cómo se escribe el JSON en vivo
                # print(contenido_chunk, end="", flush=True)
        
        print("") # Salto de línea final tras terminar el stream
        
        # Al finalizar el stream de tokens, parseamos el JSON acumulado para retornar el diccionario a Python
        if texto_json_acumulado:
            return json.loads(texto_json_acumulado)
        return None
        
    except Exception as e:
        print(f"\n❌ Error en el stream de Gemma 4: {e}")
        return None


def llamar_gemma4_completo(mensajes):
    """
    Se comunica con Ollama de forma síncrona (SIN STREAM).
    Devuelve todo el objeto de golpe para inspeccionar su estructura exacta.
    """
    url = "http://localhost:11434/api/chat"
    
    payload = {
        "model": "gemma4:12b", 
        "messages": mensajes,
        "format": "json", 
        "stream": False,   # ¡DESACTIVADO para pruebas!
        "think": True,     # Mantiene el rastro lógico activo
        "options": {
            "temperature": 0.2 
        }
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        respuesta_completa = response.json()
        
        print(f"\n respuesta_completa: \n {respuesta_completa} \n")
        # --- BLOQUE DE INSPECCIÓN PARA TUS PRUEBAS ---
        # Descomenta la línea de abajo si quieres ver absolutamente todo lo que devuelve Ollama en la consola
        # print("DEBUG COMPLETO OLLAMA:", json.dumps(respuesta_completa, indent=2))
        # ---------------------------------------------

        mensaje_objeto = respuesta_completa.get("message", {})
        
        # 1. Extraemos el JSON del content generado por el modelo
        contenido_crudo = mensaje_objeto.get("content", "")
        objeto_json = json.loads(contenido_crudo)
        
        # 2. Capturamos el bloque de pensamiento completo que vino en la respuesta
        pensamiento_completo = mensaje_objeto.get("thinking") or respuesta_completa.get("thinking", "")
        
        if pensamiento_completo:
            objeto_json["_pensamiento_nativo_"] = pensamiento_completo
            
        return objeto_json
        
    except Exception as e:
        print(f"❌ Error en la llamada completa a Gemma 4: {e}")
        return None

prompt_sistema = """Eres el motor de razonamiento de una estación meteorológica para un cultivo de paltos Hass. Tu objetivo es interpretar las consultas del agricultor, decidir si necesitas extraer datos físicos de los sensores, y entregar la información requerida.

REGLA DE ORO ESTRICTA:
Eres un sistema PURAMENTE OBSERVACIONAL Y DIAGNÓSTICO. Tienes terminantemente prohibido dar consejos, sugerir acciones, recetar productos o decirle al agricultor qué debe hacer (NUNCA uses frases como "te recomiendo", "deberías regar", "aplica fungicida"). Tu única función es describir el comportamiento de los datos físicos de manera clara, objetiva y amable.

SENSORES DISPONIBLES:
- temp_ambiente (Temperatura del aire)
- hum_ambiente (Humedad del aire)
- presion (Presión atmosférica)
- temp_suelo (Temperatura de la tierra)
- hum_suelo (Humedad de la tierra / infiltración de riego)
- ph_suelo (Acidez/Alcalinidad de la tierra)

HERRAMIENTAS DISPONIBLES:
1. "obtener_lectura_actual": Obtiene el valor exacto y más reciente de un sensor. 
   - Parámetros: {"sensor": "<nombre_del_sensor>"}
2. "obtener_extremo_diario": Obtiene el pico máximo o mínimo del día. 
   - Parámetros: {"sensor": "<nombre_del_sensor>", "tipo_extremo": "max" o "min"}
3. "analizar_tendencia_temporal": Calcula la media móvil y la tendencia en un rango de días. 
   - Parámetros: {"sensor": "<nombre_del_sensor>", "dias": <numero_entero>}

INSTRUCCIONES DE FORMATO DE RESPUESTA:
Siempre debes responder ÚNICAMENTE con un objeto JSON válido. No agregues texto fuera del JSON.

ESCENARIO A - Necesitas buscar datos en los sensores:
{
  "herramienta": "nombre_de_la_herramienta",
  "parametros": {"clave": "valor"}
}

ESCENARIO B - Responder directamente al usuario (Usa EXACTAMENTE la clave "respuesta_directa")::
{
  "respuesta_directa": "Aquí va tu respuesta final al agricultor, redactando el análisis de los datos de manera amigable pero netamente observacional."
}
"""

def ejecutar_agente_stream():
    historial = [
        {"role": "system", "content": prompt_sistema}
    ]
    
    print("🤖 Agente AgroHass Inicializado en modo STREAM. (Escribe 'salir' para terminar)")
    
    while True:
        pregunta_usuario = input("\n👨‍🌾 Agricultor: ")
        if pregunta_usuario.lower() == 'salir':
            print("Cerrando el sistema de monitoreo. ¡Hasta luego!")
            break
            
        historial.append({"role": "user", "content": pregunta_usuario})
        print("⏳ Conectando con Gemma...")
        
        # PRIMERA LLAMADA (Stream en vivo de la evaluación)
        respuesta_json = llamar_gemma4_stream(historial, tipo_fase="EVALUACIÓN") 
        if not respuesta_json:
            print("❌ No se obtuvo respuesta válida.")
            continue
        
        nombre_herramienta = respuesta_json.get("herramienta")
        
        if nombre_herramienta and nombre_herramienta in diccionario_herramientas:
            parametros = respuesta_json.get("parametros", {})
            print(f"🛠️ [ACCIÓN]: Invocando herramienta -> {nombre_herramienta} con args: {parametros}")
            
            # Ejecución interna de la herramienta
            funcion_a_llamar = diccionario_herramientas[nombre_herramienta]
            datos_reales = funcion_a_llamar(**parametros) 
            resultados_texto = json.dumps(datos_reales)
            print(f"📊 [DATOS OBTENIDOS DE BD]: {resultados_texto}")
            
            historial.append({"role": "assistant", "content": json.dumps(respuesta_json)})
            
            instruccion_traduccion = f"Resultado de BD: {resultados_texto}. Genera la respuesta final al agricultor siguiendo el Escenario B."
            historial.append({"role": "user", "content": instruccion_traduccion})
            
            # SEGUNDA LLAMADA (Stream en vivo de la redacción final)
            respuesta_final_json = llamar_gemma4_stream(historial, tipo_fase="SÍNTESIS")
            if not respuesta_final_json:
                continue
                
            mensaje_final = respuesta_final_json.get('respuesta_directa', 'Error al procesar la respuesta final.')
            print(f"\n🤖 [RESPUESTA FINAL]: {mensaje_final}")
            
            historial.pop() 
            historial.append({"role": "assistant", "content": mensaje_final})
            
        else:
            # Flujo directo (Escenario B)
            mensaje_directo = respuesta_json.get('respuesta_directa', 'No entiendo el requerimiento.')
            print(f"\n🤖 [RESPUESTA DIRECTA]: {mensaje_directo}")
            historial.append({"role": "assistant", "content": mensaje_directo})


def ejecutar_agente_prueba():
    historial = [
        {"role": "system", "content": prompt_sistema}
    ]
    
    print("🤖 Agente AgroHass en Modo PRUEBA ESTÁTICA. (Escribe 'salir' para terminar)")
    
    while True:
        pregunta_usuario = input("\n👨‍🌾 Agricultor: ")
        if pregunta_usuario.lower() == 'salir':
            break
            
        historial.append({"role": "user", "content": pregunta_usuario})
        print("⏳ Esperando respuesta completa de Gemma (Bloqueante)...")
        
        # Usamos la función no-stream
        respuesta_json = llamar_gemma4_completo(historial)
        #print(f"\n\n {respuesta_json} \n\n") 
        if not respuesta_json:
            continue
            
        # Mostramos el pensamiento completo recibido de un solo golpe
        if "_pensamiento_nativo_" in respuesta_json:
            print("\n=================== PENSAMIENTO DE EVALUACIÓN OBTENIDO ===================")
            print(respuesta_json["_pensamiento_nativo_"])
            print("=========================================================================\n")
        
        nombre_herramienta = respuesta_json.get("herramienta")
        
        if nombre_herramienta and nombre_herramienta in diccionario_herramientas:
            parametros = respuesta_json.get("parametros", {})
            print(f"🛠️ [ACCIÓN DETECTADA]: {nombre_herramienta} con args: {parametros}")
            
            # Simulación o ejecución de la herramienta
            funcion_a_llamar = diccionario_herramientas[nombre_herramienta]
            datos_reales = funcion_a_llamar(**parametros) 
            resultados_texto = json.dumps(datos_reales)
            
            respuesta_json.pop("_pensamiento_nativo_", None)
            historial.append({"role": "assistant", "content": json.dumps(respuesta_json)})
            
            instruccion_traduccion = f"Resultado de BD: {resultados_texto}. Genera la respuesta final al agricultor siguiendo el Escenario B."
            historial.append({"role": "user", "content": instruccion_traduccion})
            
            print("⏳ Esperando redacción final completa...")
            respuesta_final_json = llamar_gemma4_completo(historial)
            if not respuesta_final_json:
                continue
                
            if "_pensamiento_nativo_" in respuesta_final_json:
                print("\n=================== PENSAMIENTO DE REDACCIÓN OBTENIDO ===================")
                print(respuesta_final_json["_pensamiento_nativo_"])
                print("=========================================================================\n")
            
            mensaje_final = respuesta_final_json.get('respuesta_directa', 'Error.')
            print(f"🤖 [RESPUESTA FINAL]: {mensaje_final}")
            
            historial.pop() 
            historial.append({"role": "assistant", "content": mensaje_final})
            
        else:
            mensaje_directo = respuesta_json.get('respuesta_directa', 'No entiendo el requerimiento.')
            print(f"🤖 [RESPUESTA DIRECTA]: {mensaje_directo}")
            historial.append({"role": "assistant", "content": mensaje_directo})

if __name__ == "__main__":
    ejecutar_agente_prueba()