# MidoluzBot

Bot de comandos y logging para redes **Meshtastic**, pensado para uso hogareño / experimental. Escucha todo el tráfico de la red mesh, muestra la información en consola de forma legible y guarda los eventos en una base de datos MySQL para análisis posterior.

Además, responde a algunos comandos simples enviados por texto, integrando datos externos (cortes de energía y demanda eléctrica).

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

Todo esto sin frenar el bot si hay errores de red, API o base de datos.



## Comandos disponibles

Los comandos se envían como mensajes de texto que empiezan con `/`:

* `/ping`
  Responde `pong`. Útil para probar conectividad.

* `/demanda`
  Devuelve una línea compacta con la demanda eléctrica actual y el predespacho, consultando una API local.

* `/cortes`
  Devuelve cortes eléctricos agrupados por empresa (Edenor / Edesur u otras), con localidad, cantidad de usuarios afectados y hora estimada.

  Si hay muchos datos, la respuesta se envía en varios mensajes con pequeñas pausas.



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

```bash
python3 midoluzbot.py
```

Si la conexión al nodo es exitosa, el bot queda escuchando indefinidamente hasta que se corte con `Ctrl+C`.

Se puede automatizar mediante un servicio de Systemd sin problemas.

## Notas finales

* Agradezco enormemente a https://github.com/Meshtastic-Argentina por el código del Grumpybot, sirvió de inspiración para este proyectito!
* Funciona bien en hardware modesto (Raspberry, mini PC).
* Ideal para aprender cómo fluye la info en una red Meshtastic y tener histórico de lo que pasa, en una base de datos

