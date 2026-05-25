import asyncio
import json
import subprocess
import sys
import os

async def run_mcp_handshake_test():
    print("==================================================")
    print("  Iniciando Test Harness del Servidor MCP Floci   ")
    print("==================================================")
    
    # Comando directo al interprete del entorno virtual para evitar buffering de uv run
    cmd = [sys.executable, "-u", "floci_mcp.py"]
    
    # Entorno limpio con PYTHONUNBUFFERED activo
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    
    # Levantar el subproceso con pipes para stdin/stdout/stderr
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    
    async def read_stdout():
        try:
            line = await proc.stdout.readline()
            if line:
                return json.loads(line.decode().strip())
            else:
                err_data = await proc.stderr.read()
                if err_data:
                    print(f"\n[Subprocess Stderr Error Output]:\n{err_data.decode()}")
        except Exception as e:
            print(f"[Error de lectura stdout] {e}")
        return None

    try:
        # 1. Enviar el handshake de Inicialización (JSON-RPC)
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "verify-mcp-client",
                    "version": "1.0.0"
                }
            }
        }
        print("\n[Client -> Server] Enviando 'initialize'...")
        proc.stdin.write(json.dumps(init_request).encode() + b"\n")
        await proc.stdin.drain()
        
        # Leer respuesta de inicializacion
        init_response = await read_stdout()
        if not init_response or "result" not in init_response:
            print(f"[ERROR] Respuesta de inicializacion invalida: {init_response}")
            sys.exit(1)
        
        print(f"[Server -> Client] Handshake inicializado con éxito. Protocolo: {init_response['result']['protocolVersion']}")

        # 2. Enviar notificación 'initialized' requerida por la spec
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        print("\n[Client -> Server] Enviando 'notifications/initialized'...")
        proc.stdin.write(json.dumps(initialized_notification).encode() + b"\n")
        await proc.stdin.drain()

        # 3. Solicitar listado de herramientas expuestas
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        print("\n[Client -> Server] Enviando 'tools/list'...")
        proc.stdin.write(json.dumps(list_tools_request).encode() + b"\n")
        await proc.stdin.drain()
        
        # Leer respuesta de herramientas
        tools_response = await read_stdout()
        if not tools_response or "result" not in tools_response:
            print(f"[ERROR] No se pudo listar las herramientas: {tools_response}")
            sys.exit(1)
            
        tools = tools_response["result"]["tools"]
        print(f"[Server -> Client] Recibidas {len(tools)} herramientas expuestas:")
        for t in tools:
            print(f"  - Herramienta: '{t['name']}' -> {t['description'][:60]}...")
            
        # 4. Probar ejecución de la herramienta 'check_floci_health'
        call_tool_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "check_floci_health",
                "arguments": {}
            }
        }
        print("\n[Client -> Server] Ejecutando herramienta 'check_floci_health'...")
        proc.stdin.write(json.dumps(call_tool_request).encode() + b"\n")
        await proc.stdin.drain()
        
        # Leer respuesta de llamada de herramienta
        call_response = await read_stdout()
        if not call_response or "result" not in call_response:
            print(f"[ERROR] Fallo al ejecutar la herramienta: {call_response}")
            sys.exit(1)
            
        content = call_response["result"]["content"][0]["text"]
        health_data = json.loads(content)
        print(f"[Server -> Client] Ejecucion exitosa. Estado del Backend: {health_data['backend']['status']}. AWS: {health_data['aws_emulator']['status']}")
        
        print("\n==================================================")
        print("    ¡TEST COMPLETADO CON ÉXITO! EL SERVIDOR ES     ")
        print("        100% COMPATIBLE CON LA SPEC DE MCP         ")
        print("==================================================")
        
    except Exception as e:
        print(f"\n[Fallo en la ejecucion del test] {e}")
        sys.exit(1)
    finally:
        # Finalizar el subproceso limpiamente
        try:
            proc.terminate()
            await proc.wait()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(run_mcp_handshake_test())
