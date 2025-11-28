# 👁️ Monitor-IA — Arquitectura del Sistema (V2.0 Modular)

Este documento describe la arquitectura técnica, el flujo de datos y la estructura de servicios del proyecto **Monitor-IA** en su versión actual (Microservicios + IA modular).

---

## 🏗️ Panorama general

El sistema se compone de microservicios orquestados con Docker Compose. Su objetivo principal es procesar video localmente (con soporte GPU), generar alertas inteligentes y exponerlas a un frontend en la nube usando un túnel seguro (sin abrir puertos en el router).

## 🧩 Diagrama de flujo

```mermaid
graph LR
    CAM(Cámara RTSP) -->|Video stream| VISION[IA Worker (Python + GPU)]
    VISION -->|HTTP POST (alertas)| CORE[API Core (Node.js)]
    USER(Frontend Vercel) -->|HTTP GET (logs)| TUNNEL[Cloudflare Tunnel]
    TUNNEL -->|Reenvío seguro| CORE
    CORE -->|Lectura/Escritura| DB[(Config & Logs en memoria)]
```

## Estructura del proyecto

```
monitor-ia/
├── docker-compose.yml          # Orquestador de los contenedores
├── api-backend/                # SERVICIO: core
│   ├── index.js                # API REST (Express) + Swagger
│   ├── swagger.json            # Documentación API
│   ├── config.json             # Persistencia: URL RTSP y ajustes globales
│   └── services/
│       ├── logger.js           # Historial de eventos (FIFO)
│       └── configManager.js    # Lectura/escritura de configuración
├── ia-worker/                  # SERVICIO: vision
│   ├── main.py                 # Orquestador: carga módulos y lee cámaras
│   ├── Dockerfile              # Entorno Python (GPU, OpenGL)
│   └── modules/                # Módulos de detección (plugins)
│       ├── detector_epp/
│       │   ├── logic.py        # Lógica del detector (clase Detector)
│       │   ├── config.json     # Umbrales y cooldown
│       │   └── best.pt         # Modelo YOLO entrenado
│       └── detector_fuego/
│           └── ...
└── monitoring/                 # Prometheus, Grafana, etc.
        └── prometheus/
                └── prometheus.yml      # Configuración de métricas
```

## 🚀 Servicios y responsabilidades

1. Core (sistema_core)
     - Tecnología: Node.js (Express)
     - Puerto interno: 3001
     - Funciones:
         - Recibe alertas desde la IA (POST /api/log)
         - Guarda/actualiza configuración de cámaras (POST /api/config)
         - Expone la documentación Swagger en `/api-docs`

2. Vision (sistema_vision)
     - Tecnología: Python 3.9 + Ultralytics YOLO + OpenCV
     - Hardware: Acceso a NVIDIA GPU (si está disponible)
     - Funcionamiento:
         - Al iniciar, consulta al Core para obtener la URL RTSP
         - Escanea `ia-worker/modules/` y carga cada módulo como un detector independiente
         - Procesa frames (con optimizaciones de saltado de frames)
         - Si un módulo detecta un evento, envía un JSON al Core

3. Tunnel (tunnel_logs)
     - Tecnología: cloudflared (Cloudflare Tunnel)
     - Función: expone el puerto 3001 del Core a Internet mediante una URL pública tipo `https://<random>.trycloudflare.com`

4. Monitoreo (observabilidad)
     - cAdvisor: métricas de contenedores (CPU/RAM)
     - Prometheus: recolección y almacenamiento de métricas
     - Grafana: visualización (puerto típico: 3003)

## 📡 API (endpoints relevantes)

La API está documentada con Swagger. Si el túnel está activo, la UI de Swagger está disponible en:

`https://TU-TUNNEL.trycloudflare.com/api-docs`

Principales endpoints:

- GET /api/config — Obtiene la URL RTSP y configuración actual
- POST /api/config — Actualiza la cámara o activa/desactiva el sistema
- GET /api/logs — Obtiene el historial de alertas (soporta filtros, p. ej. `?source=DETECTOR_EPP`)
- POST /api/log — Uso interno: registra una nueva alerta desde la IA

## 🛠️ Guía de operación diaria

Encender el sistema (levanta todos los servicios):

```bash
docker compose up -d
```

Esto levanta todos los contenedores y mantiene la URL del túnel si ya estaba corriendo.

Actualizar código de un módulo de IA:

1. Edita `ia-worker/modules/<tu_modulo>/logic.py` o `config.json`.
2. Reinicia sólo el servicio de visión:

```bash
docker compose restart vision
```

Si cambiaste la estructura de la clase o dependencias, reconstruye el servicio:

```bash
docker compose up -d --build vision
```

Ver logs en vivo:

```bash
docker logs -f sistema_vision   # Logs del worker de IA
docker logs -f sistema_core     # Logs del backend API
docker logs tunnel_logs         # Para obtener la URL pública del túnel
```

Cambiar configuración de cámara

1. Entra a Swagger (o usa curl/postman) y usa `POST /api/config`.
2. El contenedor `vision` detectará el cambio automáticamente (o reinícialo si quieres forzar la recarga).

## ⚠️ Notas importantes

- Persistencia del túnel: evita apagar el contenedor `tunnel` si necesitas mantener la URL pública.
- GPU: el servicio `vision` requiere drivers y el NVIDIA container toolkit en el host para acceder a la GPU.
- Logs: los logs del Core son volátiles por diseño (historial en memoria), pensados para monitoreo en tiempo real.