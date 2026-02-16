# MidoluzBot
Bot de comandos y logging para redes **Meshtastic**, pensado para uso hogareño / experimental. Escucha todo el tráfico de la red mesh, muestra la información en consola de forma legible y guarda los eventos en una base de datos MySQL para análisis posterior.Además, responde a algunos comandos simples enviados por texto, integrando datos externos (cortes de energía y demanda eléctrica).

A partir de la versión midoluzbotv3.py, el bot también expone una API REST (FastAPI) para enviar mensajes a la red mesh desde HTTP.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Status](https://img.shields.io/badge/Status-stable-green)
![GitHub repo size](https://img.shields.io/github/repo-size/juanstdio/midoluzMeshtastic)
![GitHub license](https://img.shields.io/github/license/juanstdio/midoluzMeshtastic) 
![MySQL](https://shields.io/badge/MySQL-lightgrey?logo=mysql&style=plastic&logoColor=white&labelColor=blue)

Proyecto de hobby, orientado a monitoreo y curiosidad técnica.

## ¿Qué hace?

* Se conecta a un nodo Meshtastic por TCP.
* Escucha **todos los paquetes** que circulan por la red.
* Identifica y loguea distintos tipos de mensajes:

  * Mensajes de texto
  * Posición (GPS)
  * Información de nodo
  * Telemetría (batería, voltaje)
  * Routing, range test, sensores y paquetes admin
* Guarda cada evento en una base MySQL, serializando los datos en JSON.
* Responde comandos enviados por texto desde otros nodos.
* Expone una API REST para enviar mensajes a la red mesh.

Todo esto sin frenar el bot si hay errores de red, API o base de datos.

## API REST (solo midoluzbotv3.py)

El bot puede actuar como puente entre HTTP y la red mesh LoRa.

Corre un servidor FastAPI en el puerto:
```HTML
http://IP_DEL_BOT:1215
```
Documentación automática disponible en:
```HTML
http://IP_DEL_BOT::1215/docs#
```

## Endpoints disponibles
### POST /SendMessage

Envía un mensaje a un canal Meshtastic.

Parámetros JSON:
```JSON
{
  "channel": 0,
  "message": "Hola mesh 😎"
}
```
Características:
* Máximo 200 caracteres
* Soporte completo UTF-8 (emojis incluidos)
* Pensado para broadcast a canal

Respuesta típica:
```JSON
{
  "status": "ok",
  "channel": 0,
  "message": "Hola mesh 😎"
}
```

### POST /SendDirectMessage

Envía un mensaje directo a un nodo específico.

Parámetros JSON:
```JSON
{
  "destination_id": "!abcd1234",
  "message": "Ping directo ⚡"
}
```
Características:

* Mensaje privado nodo-a-nodo
* Hasta 200 caracteres
* No usa broadcast de canal

Respuesta típica:
```JSON
{
  "status": "ok",
  "destination": "!abcd1234",
  "message": "Ping directo ⚡"
}
```

## Comandos disponibles

Los comandos se envían como mensajes de texto que empiezan con `/`:

* `/ping`
  Responde `pong`. Útil para probar conectividad.

* `/demanda`
  Devuelve una línea compacta con la demanda eléctrica actual y el predespacho de [CAMMESA](https://cammesaweb.cammesa.com/).

* `/cortes`
  Devuelve cortes eléctricos agrupados por empresa (Edenor / Edesur u otras), con localidad, cantidad de usuarios afectados y hora estimada. Datos Oficiales del ENRE

  Si hay muchos datos, la respuesta se envía en varios mensajes con pequeñas pausas de 5 segundos.



## Logging

El bot muestra en consola información en tiempo real usando colores (colorama):

* Quién envía → quién recibe
* Tipo de paquete
* Datos relevantes según el caso

La idea es poder “ver” la red mesh viva, sin necesidad de decodificar nada a mano.



## Base de datos

Cada paquete recibido se guarda en MySQL en una tabla llamada `eventos`.

Se registra:

* Tipo de paquete (portnum)
* ID del emisor
* Nombre corto del emisor (si está disponible)
* ID del receptor
* Payload completo en formato JSON

El código intenta limpiar y serializar cualquier objeto raro de Meshtastic para evitar errores al guardar.

Si la base falla, el bot **no se cae**: solo loguea el error y sigue.



## Requisitos

* Python 3
* Un nodo Meshtastic accesible por TCP
* MySQL / MariaDB

Librerías principales:

* `meshtastic`
* `mysql-connector-python`
* `pubsub`
* `colorama`
* `requests`

---

## Configuración

Variables a revisar antes de usar:

* `IP_NODO`
  IP del nodo Meshtastic al que se conecta el bot.

* `DB_CONFIG`
  Datos de conexión a la base MySQL.

* URLs de las APIs locales usadas por `/cortes` y `/demanda`.

Todo está hardcodeado a propósito: es un bot simple, pensado para correr en una red local.


## Base de datos: creación inicial

A continuación se muestra un ejemplo completo para crear la base de datos, la tabla de eventos y el usuario necesario en MySQL / MariaDB.

Este esquema es el esperado por el bot tal como está escrito.

```sql
CREATE DATABASE IF NOT EXISTS meshtastic;
USE meshtastic;

CREATE TABLE IF NOT EXISTS eventos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
    tipo_paquete VARCHAR(50),      -- TEXT, POSITION, TELEMETRY, etc.
    emisor_id VARCHAR(20),         -- ID hexadecimal
    emisor_name VARCHAR(50),       -- ShortName si está disponible
    receptor_id VARCHAR(20),
    data_json TEXT,                -- Payload serializado en JSON
    canal INT DEFAULT 0
);

-- Usuario y permisos
CREATE USER IF NOT EXISTS 'meshlogger'@'%' IDENTIFIED BY 'profesor';
GRANT INSERT ON meshtastic.* TO 'meshlogger'@'%';

-- Soporte completo de UTF-8 (emojis incluidos)
ALTER DATABASE meshtastic CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
ALTER TABLE meshtastic.eventos CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

FLUSH PRIVILEGES;
```

Notas:

* `utf8mb4` es importante para evitar problemas con caracteres raros o emojis enviados desde la mesh.
* El campo `data_json` guarda el payload completo del paquete, ya limpiado y serializado por el bot.
* El bot asume que el usuario y la base ya existen: no crea nada automáticamente.



## Ejecución
Para versión clásica:
```bash
python3 midoluzbot.py
```
Para versión con API Rest:
```bash
python3 midoluzbotv3.py
```

Si la conexión al nodo es exitosa, el bot queda escuchando indefinidamente hasta que se corte con `Ctrl+C`.

Se puede automatizar mediante un servicio de Systemd sin problemas.

## Notas finales / Gratitudes

- Funciona bien en hardware modesto (Raspberry, mini PC). Ideal para aprender cómo fluye la info en una red Meshtastic y tener histórico de lo que pasa, en una base de datos
- Agradezco a **Meshtastic Argentina** - por el código del _Grumpybot_, sirvió de inspiración para este proyectito - [Meshtastic Argentina](https://github.com/Meshtastic-Argentina)
- **Compañía Administradora del Mercado Mayorista Eléctrico S.A.** - _Por Proveer los datos abiertamente_ - [CAMMESA](https://cammesaweb.cammesa.com/)

