import json
from tools import diccionario_herramientas
from datetime import datetime
from config import OLLAMA_URL, OLLAMA_MODEL
import requests

fecha_de_hoy = datetime.now().strftime("%Y-%m-%d")
hora_actual = datetime.now().strftime("%H:%M")

prompt_sistema = """Eres el motor de razonamiento de una estación meteorológica para un cultivo de paltos Hass. Tu objetivo es interpretar las consultas del agricultor, decidir si necesitas extraer datos físicos de los sensores, y entregar la información requerida.

CONTEXTO TEMPORAL DEL SISTEMA:
- Fecha Actual: {fecha_de_hoy}
- Hora Actual: {hora_actual}
Usa este contexto obligatoriamente para ubicarte cuando el usuario haga preguntas sobre "hoy", "ayer" o "esta misma hora".
s
REGLA DE ORO ESTRICTA:
Eres un sistema PURAMENTE OBSERVACIONAL Y DIAGNÓSTICO. Tienes terminantemente prohibido dar consejos, sugerir acciones, recetar productos o decirle al agricultor qué debe hacer (NUNCA uses frases como "te recomiendo", "deberías regar", "aplica fungicida"). Tu única función es describir el comportamiento de los datos físicos de manera clara, objetiva y amable.

SENSORES DISPONIBLES:
- temp_ambiente (Temperatura del aire)
- hum_ambiente (Humedad del aire)
- presion (Presión atmosférica)
- temp_suelo (Temperatura de la tierra)
- hum_suelo (Humedad de la tierra / infiltración de riego)
- ph_suelo (Acidez/Alcalinidad de la tierra)

"""

class AgriSenseAgent:
    def __init__(self):
        self.historial = [{"role": "system", "content": prompt_sistema}]

    def procesar_interaccion_stream(self, pregunta_usuario):
        self.historial.append({"role": "user", "content": pregunta_usuario})
        print("⏳ Conectando con Gemma...")
        
        respuesta_json = self.llamar_gemma4_stream(self.historial, tipo_fase="EVALUACIÓN") 
        if not respuesta_json:
            print("❌ No se obtuvo una respuesta válida.")
            return
        
        nombre_herramienta = respuesta_json.get("herramienta")
        
        if nombre_herramienta and nombre_herramienta in diccionario_herramientas:
            parametros = respuesta_json.get("parametros", {})
            print(f"🛠️ [ACCIÓN]: Invocando herramienta -> {nombre_herramienta} con args: {parametros}")
            
            funcion_a_llamar = diccionario_herramientas[nombre_herramienta]
            datos_reales = funcion_a_llamar(**parametros) 
            resultados_texto = json.dumps(datos_reales)
            print(f"📊 [DATOS OBTENIDOS DE BD]: {resultados_texto}")
            
            self.historial.append({"role": "assistant", "content": json.dumps(respuesta_json)})
            
            instruccion_traduccion = f"Resultado de BD: {resultados_texto}. Genera la respuesta final al agricultor siguiendo el Escenario B."
            self.historial.append({"role": "user", "content": instruccion_traduccion})
            
            respuesta_final_json = self.llamar_gemma4_stream(self.historial, tipo_fase="SÍNTESIS")
            if not respuesta_final_json:
                return
                
            mensaje_final = respuesta_final_json.get('respuesta_directa', 'Error al procesar la respuesta final.')
            print(f"\n🤖 [RESPUESTA FINAL]: {mensaje_final}")
            
            self.historial.pop() 
            self.historial.append({"role": "assistant", "content": mensaje_final})
        else:
            mensaje_directo = respuesta_json.get('respuesta_directa', 'No entiendo el requerimiento.')
            print(f"\n🤖 [RESPUESTA DIRECTA]: {mensaje_directo}")
            self.historial.append({"role": "assistant", "content": mensaje_directo})

    def llamar_gemma4(self, mensajes):
        """
        Llamada bloqueante clásica. Ideal para análisis estáticos de logs 
        o procesamiento por lotes inyectando el rastro lógico en el retorno.
        """

        mis_herramientas = [{
            "type": "function",
            "function": {
                "name": "leer_datos_de_sensores",
                "description": "Busca datos físicos en la base de datos de los sensores. Úsala siempre que el agricultor pregunte por el clima, temperatura, humedad, etc.",
                "parameters": {
                "type": "object",
                "properties": {
                    "sensor": {
                    "type": "string",
                    "enum": ["temp_ambiente", "hum_ambiente", "presion", "temp_suelo", "hum_suelo", "ph_suelo"],
                    "description": "El nombre del sensor a consultar."
                    },
                    "operacion": {
                    "type": "string",
                    "enum": ["PROMEDIO", "MAXIMO", "MINIMO", "ULTIMO"],
                    "description": "El tipo de cálculo matemático a realizar."
                    },
                    "agrupacion_minutos": {
                    "type": "integer",
                    "description": "(Opcional) Úsalo solo si necesitas agrupar series de tiempo (ej. 1440 para tendencias agrupadas por día)."
                    },
                    "rango_horas": {
                    "type": "integer",
                    "description": "Horas hacia atrás desde este instante (ej. 24 para las últimas 24 horas)."
                    },
                    "fecha_inicio": {
                    "type": "string",
                    "description": "Formato 'YYYY-MM-DD' o 'YYYY-MM-DD HH:MM'."
                    },
                    "fecha_fin": {
                    "type": "string",
                    "description": "Formato 'YYYY-MM-DD' o 'YYYY-MM-DD HH:MM'."
                    }
                },
                "required": ["sensor", "operacion"]
                }
            }
        }]
        
        payload = {
            "model": OLLAMA_MODEL, 
            "messages": mensajes,
            "tools": mis_herramientas,
            #"format": "json", 
            "stream": False,
            "think": True,
            "options": {"temperature": 0.2}
        }
        
        try:
            response = requests.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            
            respuesta_completa = response.json()
            print(f"\nllamar_gemma4_completo - respuesta_completa = \n {respuesta_completa}\n")
            mensaje_objeto = respuesta_completa.get("message", {})
            
            #contenido_crudo = mensaje_objeto.get("content", "")
            objeto_json = mensaje_objeto #json.loads(contenido_crudo)
            
            pensamiento_completo = mensaje_objeto.get("thinking") or respuesta_completa.get("thinking", "")
            if pensamiento_completo:
                objeto_json["_pensamiento_nativo_"] = pensamiento_completo
                
            return objeto_json
            
        except Exception as e:
            print(f"❌ Error en la llamada completa a Gemma 4: {e}")
        return None

    def llamar_gemma4_stream(mensajes, tipo_fase="PROCESANDO"):
        """
        Establece conexión stream con Ollama. Captura y renderiza el pensamiento
        nativo mientras procesa el almacenamiento estructurado de la salida JSON.
        """
        payload = {
            "model": OLLAMA_MODEL, 
            "messages": mensajes,
            "format": "json", 
            "stream": True,
            "think": True,
            "options": {"temperature": 0.2}
        }
        
        try:
            response = requests.post(OLLAMA_URL, json=payload, stream=True)
            response.raise_for_status()
            
            texto_json_acumulado = ""
            imprimio_encabezado_pensamiento = False
            imprimio_encabezado_json = False
            
            for linea in response.iter_lines():
                if not linea:
                    continue
                    
                chunk = json.loads(linea.decode('utf-8'))
                pensamiento_chunk = chunk.get("message", {}).get("thinking", "")
                
                if pensamiento_chunk:
                    if not imprimio_encabezado_pensamiento:
                        print(f"\n🧠 [PENSAMIENTO NATIVO - {tipo_fase}]:")
                        imprimio_encabezado_pensamiento = True
                    print(pensamiento_chunk, end="", flush=True)
                    continue
                
                contenido_chunk = chunk.get("message", {}).get("content", "")
                if contenido_chunk:
                    if not imprimio_encabezado_json:
                        if imprimio_encabezado_pensamiento:
                            print("\n") 
                        print(f"✨ [GENERANDO SALIDA ESTRUCTURADA...]")
                        imprimio_encabezado_json = True
                    
                    texto_json_acumulado += contenido_chunk
            
            print("") 
            
            if texto_json_acumulado:
                return json.loads(texto_json_acumulado)
            return None
            
        except Exception as e:
            print(f"\n❌ Error en el stream de Gemma 4: {e}")
            return None
     
    def procesar_interaccion_estatica(self, pregunta_usuario):
        self.historial.append({"role": "user", "content": pregunta_usuario})
        print("⏳ Esperando respuesta completa de Gemma (Bloqueante)...")
        
        respuesta_json = self.llamar_gemma4(self.historial)
        print(f"\n respuesta_json = \n {respuesta_json} \n")

        if not respuesta_json:
            return
            
        if "_pensamiento_nativo_" in respuesta_json:
            print("\n=================== PENSAMIENTO ===================")
            print(respuesta_json["_pensamiento_nativo_"])
            print("=========================================================================\n")
        
        if "tool_calls" in respuesta_json:
            
            tools = respuesta_json.get("tool_calls")

            self.historial.append({"role": "assistant", 
                                   "content": "",
                                   "tool_calls": tools
                                   })
            
            print(f"\n tools = \n {tools} \n")

            for tool in tools:
                nombre_funcion = tool["function"]["name"]
                argumentos = tool["function"]["arguments"]
                print("\n=================== HERRAMIENTA SELECCIONADA ===================")
                print("nombre_funcion:", nombre_funcion)
                print("argumentos:", argumentos)
                print("=========================================================================\n")

                if nombre_funcion and nombre_funcion in diccionario_herramientas:
                    funcion_a_llamar = diccionario_herramientas[nombre_funcion]
                    datos_db = funcion_a_llamar(**argumentos)
                    #print(f"\n datos_db = {datos_db}") 
                    
                    datos_texto = json.dumps(datos_db, default=str)

                    print(f"datos_texto\n: {datos_texto}")
                    
                    self.historial.append({"role": "tool", 
                                           "content": datos_texto})

                    print("\nself.historial:\n", self.historial)

                    respuesta_final_json = self.llamar_gemma4(self.historial)
                    if not respuesta_final_json:
                        return
                    
                    if "_pensamiento_nativo_" in respuesta_final_json:
                        print("\n=================== PENSAMIENTO ===================")
                        print(respuesta_final_json["_pensamiento_nativo_"])
                        print("=========================================================================\n")

                       
                    mensaje_final = respuesta_final_json.get('content', 'Error.')
                    print(f"🤖 Agente: {mensaje_final}")
            
        else:
            mensaje_directo = respuesta_json.get('content', 'No entiendo el requerimiento.')
            print(f"🤖 Agente: {mensaje_directo}")
            self.historial.append({"role": "assistant", "content": mensaje_directo})

