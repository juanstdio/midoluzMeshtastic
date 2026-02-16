#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# MidoLuzBot - Bot de comandos,logging y mensajeo para redes Meshtastic
# basado en el trabajo de https://github.com/Meshtastic-Argentina/meshtastic_grumpy_bot/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import time
import logging
from datetime import datetime
from pubsub import pub
import mysql.connector
import json


import threading


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, constr,Field
import uvicorn

try:
    import meshtastic
    import meshtastic.serial_interface
    import meshtastic.tcp_interface
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError as e:
    print(f"ERROR: Falta instalar dependencias: {e}")
    sys.exit(1)

# ------------------------
# DB CONFIG
# ------------------------

DB_CONFIG = {
    "host": "192.168.0.121",
    "user": "meshlogger",
    "password": "profesor",
    "database": "meshtastic",
    "charset": "utf8mb4"
}

# ------------------------
# FASTAPI CONFIG
# ------------------------

app = FastAPI(
    title="MidoluzBot REST API",
    description=(
        "API REST del MidoluzBot. "
        "Permite enviar mensajes a canales o chats de la mesh."
        "Proyecto experimental orientado a resiliencia comunicacional "
        "y exploración técnica en redes fuera de internet."
    ),
    version="3.12",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1})
    
class SendMessageRequest(BaseModel):
    channel: int = Field(
        ...,
        example=0,
        description="Índice del canal Meshtastic al que se enviará el mensaje, canal 0 es el primary"
    )
    message: constr(max_length=200) = Field(
        ...,
        example="Hola mesh 😎⚡",
        description="Mensaje UTF-8 hasta 200 caracteres (emojis permitidos)"
    )

mesh_bot_instance = None

@app.post("/SendMessage", summary="Enviar mensaje a la red mesh",
    description=(
        "Envía un mensaje de texto a un canal Meshtastic desde HTTP. "
        "Máximo 200 caracteres."
    ),
    response_description="Confirmación simple de envío al canal indicado")
    
async def send_message(req: SendMessageRequest):
    global mesh_bot_instance

    if not mesh_bot_instance or not mesh_bot_instance.interface:
        raise HTTPException(status_code=503, detail="Bot no conectado")

    try:
        mesh_bot_instance.interface.sendText(
            text=req.message,
            channelIndex=req.channel
        )

        return {
            "status": "Mensaje Enviado!",
            "channel": req.channel,
            "message": req.message
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SendDirectMessageRequest(BaseModel):
    destination_id: str = Field(
        ...,
        example="!abcd1234",
        description="NodeID destino Meshtastic (hex con ! o formato largo)"
    )
    message: constr(max_length=200) = Field(
        ...,
        example="Ping directo ⚡",
        description="Mensaje UTF-8 hasta 200 caracteres"
    )


@app.post(
    "/SendDirectMessage",
    summary="Enviar mensaje directo a nodo",
    description=(
        "Envía un mensaje privado a un nodo específico de la red mesh. "
        "No usa canal broadcast: el paquete se enruta directo al NodeID."
    ),
    response_description="Confirmación de envío al nodo destino"
)
async def send_direct_message(req: SendDirectMessageRequest):
    global mesh_bot_instance

    if not mesh_bot_instance or not mesh_bot_instance.interface:
        raise HTTPException(status_code=503, detail="Bot no conectado")

    try:
        mesh_bot_instance.interface.sendText(
            text=req.message,
            destinationId=req.destination_id
        )

        return {
            "status": "ok",
            "destination": req.destination_id,
            "message": req.message
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



def start_rest_api():
    uvicorn.run(app, host="0.0.0.0", port=1215, log_level="info")


# ------------------------
# DB UTILS
# ------------------------

def serializar_para_json(obj):
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {str(k): serializar_para_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serializar_para_json(i) for i in obj]
    if hasattr(obj, "__dict__"):
        return str(obj)
    return str(obj)


def registrar_en_db(tipo, emisor_id, emisor_name, receptor_id, extra_data):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        data_limpia = serializar_para_json(extra_data)

        query = """
            INSERT INTO eventos (tipo_paquete, emisor_id, emisor_name, receptor_id, data_json)
            VALUES (%s, %s, %s, %s, %s)
        """

        valores = (
            tipo,
            emisor_id,
            emisor_name,
            receptor_id,
            json.dumps(data_limpia)
        )

        cursor.execute(query, valores)
        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"{Fore.RED}[DB ERROR] {e}{Style.RESET_ALL}")


# ------------------------
# Funciones de API
# ------------------------

def obtener_cortes_por_empresa():
    try:
        import requests
        from collections import defaultdict
        r = requests.get("http://192.168.0.27:8000/cortes_detalle_agrupados", timeout=3)
        data = r.json().get("resultados", [])
        if not data: return ["Sin cortes reportados"]

        empresas = defaultdict(list)
        for c in data:
            est_raw = c.get("normalizacion_estimada", "")
            try:
                hora = datetime.strptime(est_raw, "%Y-%m-%d %H:%M").strftime("%H:%M")
            except:
                hora = "??"
            loc = c.get("localidad", "Unk")
            afectados = c.get("total_afectados", 0)
            empresas[c["empresa"]].append(f"{loc} {afectados}@{hora}")

        mensajes_finales = []
        mapa_nombres = {"Edenor": "EN", "Edesur": "ES"}
        for empresa, items in empresas.items():
            prefijo = mapa_nombres.get(empresa, empresa)
            mensajes_finales.append(f"{prefijo} | {', '.join(items)}"[:200])
        return mensajes_finales
    except Exception as e:
        return [f"Error cortes: {e}"]

def obtener_demanda_compacta():
    try:
        import requests
        r = requests.get("http://192.168.0.8:5005/api/last_sadi", timeout=3)
        d = r.json()
        return f"Demanda {d.get('time_muestra','??')} | Hoy:{d.get('DemHoy','?')}MW | Est:{d.get('Predespacho','?')}MW"
    except Exception:
        return "Error leyendo demanda"
        
def obtener_estado_subte_compacto():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        query = """
            SELECT s1.linea, s1.estado, s1.fecha_registro
            FROM estado_subte s1
            INNER JOIN (
                SELECT linea, MAX(fecha_registro) as max_fecha
                FROM estado_subte
                GROUP BY linea
            ) s2 ON s1.linea = s2.linea AND s1.fecha_registro = s2.max_fecha
            ORDER BY s1.linea ASC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows: return "❌ Sin datos de subte"

        resumen = []
        fecha_data = rows[0][2].strftime("%H:%M")
        
        for linea, estado, _ in rows:
            # 1. Limpiar nombre: "Linea A" -> "A"
            L = linea.replace("Linea ", "").strip()
            
            # 2. Lógica inteligente de resumen de estado
            est = estado.upper()
            if "NORMAL" in est:
                msg = "OK"
            elif "OBRAS" in est or "RENOVACION" in est:
                msg = "OBRAS"
            elif "INTERRUMPID" in est or "SUSPENDID" in est:
                msg = "CORTE"
            elif "DEMORA" in est:
                msg = "DEMORA"
            elif "LIMITADO" in est:
                msg = "LIMIT"
            else:
                # Si es un texto raro, tomamos las primeras 10 letras
                msg = estado[:10].strip()

            resumen.append(f"{L}:{msg}")

        cursor.close()
        conn.close()
        
        # Unimos con separador compacto
        final_msg = f"🚇{fecha_data} | " + " ".join(resumen)
        
        # Si aún así supera los 200 (raro), recortamos
        return final_msg[:200]

    except Exception as e:
        return f"Error Subte: {e}"  

# ------------------------
# Clase Principal del Bot
# ------------------------


class MeshtasticCommandBot:

    def __init__(self):
        self.interface = None
        self.setup_logging()

    def setup_logging(self):
        log_format = (
            f"{Fore.WHITE}{Style.DIM}%(asctime)s{Style.RESET_ALL} "
            f"{Fore.GREEN}{Style.BRIGHT}[%(levelname)s]{Style.RESET_ALL} %(message)s"
        )
        logging.basicConfig(level=logging.INFO, format=log_format, datefmt='%H:%M:%S')
        self.logger = logging.getLogger("MeshBot")
        self.logger.info(
            f"{Fore.MAGENTA}{Style.BRIGHT}MidoLuz-Bot REST activo{Style.RESET_ALL}"
        )

    def get_node_label(self, node_id):
        if node_id == 0xffffffff or node_id == "^all": return "ALL"
        try:
            if node_id in self.interface.nodes:
                return self.interface.nodes[node_id]["user"]["shortName"]
        except: pass
        return f"!{node_id:08x}" if isinstance(node_id, int) else str(node_id)

    def connect(self, address):
        try:
            self.logger.info(f"Conectando a {address}...")
            self.interface = meshtastic.tcp_interface.TCPInterface(hostname=address)
            return True
        except Exception as e:
            self.logger.error(f"Error conexión: {e}")
            return False

    def on_receive(self, packet, interface):
        try:
            decoded = packet.get("decoded", {})
            port = decoded.get("portnum")
            from_id = packet.get("fromId")
            dest_id = packet.get("toId")
            
            sender = self.get_node_label(from_id)
            dest = self.get_node_label(dest_id)
            peers = f"{Fore.CYAN}{Style.BRIGHT}{sender:>6}{Style.RESET_ALL} -> {Fore.YELLOW}{Style.BRIGHT}{dest:<6}"
            # Extract data para la DB
            payload_db = {}
            tipo_db = port
            # --- TEXT MESSAGES ---
            if port == "TEXT_MESSAGE_APP":
                text = decoded.get("text", "").strip()
                payload_db = {"text": text}
                self.logger.info(f"{Fore.WHITE}{Style.BRIGHT}{'Text Message':<18} {peers} {Fore.MAGENTA}Msg: {text}")
                if text.startswith("/"):
                    self.handle_command(text, from_id, sender)

            # --- POSITION ---
            elif port == "POSITION_APP":
                pos = decoded.get("position", {})
                payload_db = {
                    "latitude": pos.get("latitude"),
                    "longitude": pos.get("longitude"),
                    "altitude": pos.get("altitude"),
                    "sats": pos.get("sats"),
                    "PDOP": pos.get("PDOP")
                }  
                lat = pos.get("latitude")
                lon = pos.get("longitude")
                alt = pos.get("altitude", 0)
                self.logger.info(f"{Fore.BLUE}{Style.BRIGHT}{'Position':<18} {peers} {Style.DIM}Lat: {lat}, Lon: {lon}, Alt: {alt}m")

            # --- NODE INFO ---
            elif port == "NODEINFO_APP":
                user = decoded.get("user", {})
                payload_db = user
                name = user.get("longName", "???")
                hw = user.get("hwModel", "???")
                self.logger.info(f"{Fore.YELLOW}{Style.BRIGHT}{'Node Info':<18} {peers} {Style.DIM}Name: {name} | HW: {hw}")

            # --- TELEMETRY ---
            elif port == "TELEMETRY_APP":
                tel = decoded.get("telemetry", {}).get("deviceMetrics", {})
                payload_db = tel
                volt = tel.get("voltage", 0)
                bat = tel.get("batteryLevel", 0)
                self.logger.info(f"{Fore.MAGENTA}{Style.BRIGHT}{'Telemetry':<18} {peers} {Style.DIM}Volt: {volt}V, Bat: {bat}%")

            # --- ROUTING ---
            elif port == "ROUTING_APP":
                payload_db = {"raw": str(decoded)}
                self.logger.info(f"{Fore.CYAN}{Style.DIM}{'Routing':<18} {peers} {Style.DIM}Mesh Routing Packet")

            # --- RANGE TEST ---
            elif port == "RANGE_TEST_APP":
                payload = decoded.get("payload", "")
                payload_db = {"raw": str(decoded)}
                self.logger.info(f"{Fore.GREEN}{Style.BRIGHT}{'Range Test':<18} {peers} {Style.DIM}Seq: {payload}")

            # --- DETECTION SENSOR ---
            elif port == "DETECTION_SENSOR_APP":
                payload_db = {"raw": str(decoded)}
                self.logger.info(f"{Fore.RED}{Style.BRIGHT}{'Sensor Alert':<18} {peers} {Fore.RED}SENSOR TRIGGERED")

            # --- ADMIN ---
            elif port == "ADMIN_APP":
                payload_db = {"raw": str(decoded)}
                self.logger.info(f"{Fore.RED}{'Admin':<18} {peers} Admin Config Packet")
            # LLAMADA A LA BASE DE DATOS
            registrar_en_db(
                tipo=tipo_db,
                emisor_id=f"{from_id:08x}" if isinstance(from_id, int) else str(from_id),
                emisor_name=sender,
                receptor_id=f"{dest_id:08x}" if isinstance(dest_id, int) else str(dest_id),
                extra_data=payload_db
            )

        except Exception as e:
            self.logger.error(f"Error procesando paquete: {e}")

    def handle_command(self, text, sender_id, sender_name):
        cmd = text.lower()
        if "/cortes" in cmd:
            mensajes = obtener_cortes_por_empresa()
            for i, m in enumerate(mensajes):
                self.logger.info(f"\t{Fore.GREEN}Respuesta ({i+1}/{len(mensajes)}): {Style.RESET_ALL}{m}")
                self.interface.sendText(m, destinationId=sender_id)
                if i < len(mensajes) - 1: time.sleep(5)
        elif "/demanda" in cmd:
            reply = obtener_demanda_compacta()
            self.interface.sendText(reply, destinationId=sender_id)
        elif "/subte" in cmd:
            reply = obtener_estado_subte_compacto()
            self.logger.info(f"\t{Fore.GREEN}Respuesta Subte: {Style.RESET_ALL}{reply}")
            self.interface.sendText(reply, destinationId=sender_id)
        elif "/ping" in cmd:
            self.interface.sendText("pong", destinationId=sender_id)


    def start(self):
        pub.subscribe(self.on_receive, "meshtastic.receive")
        self.logger.info("Escuchando red Meshtastic...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            if self.interface:
                self.interface.close()


# ------------------------
# MAIN
# ------------------------

if __name__ == "__main__":
    bot = MeshtasticCommandBot()
    mesh_bot_instance = bot

    if bot.connect("192.168.0.156"):

        # API REST paralela mediante threading
        threading.Thread(target=start_rest_api, daemon=True).start()

        bot.start()
