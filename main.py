import sys
from agent import AgriSenseAgent

def run_agent(stream = False):
    agente = AgriSenseAgent()
    modo_texto = "STREAM" if stream else "ESTÁTICO"
    print(f"\n🤖 Agente AgroHass Inicializado en modo {modo_texto}.")
    print("(Escribe 'salir' o 'regresar' para cambiar de modo o terminar)\n")
    
    while True:
        try:
            pregunta_usuario = input("👨‍🌾 Agricultor: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nCerrando sesión del agente de forma segura...")
            sys.exit(0)
            
        if not pregunta_usuario:
            continue
            
        if pregunta_usuario.lower() in ['salir', 'regresar']:
            print("Regresando al menú principal...\n")
            break
            
        if stream:
            agente.procesar_interaccion_stream(pregunta_usuario)
        else:
            agente.procesar_interaccion_estatica(pregunta_usuario)

if __name__ == "__main__":
    run_agent(stream = False)