const express = require('express');
const cors = require('cors');
const path = require('path'); // <--- IMPORTANTE: Agregamos esto
const swaggerUi = require('swagger-ui-express');
const swaggerJsdoc = require('swagger-jsdoc');

// Importamos servicios internos
const Config = require('./services/configManager');
const Logger = require('./services/logger');

const app = express();
const PORT = 3001;

// Middlewares
app.use(cors({ origin: '*' }));
app.use(express.json());

// ==========================================
// 📘 CONFIGURACIÓN DE SWAGGER
// ==========================================
const swaggerOptions = {
    definition: {
        openapi: '3.0.0',
        info: {
            title: 'Monitor-IA API Core',
            version: '2.1.0',
            description: 'API Central para logs y configuración.',
        },
        servers: [
            { url: '/', description: 'Servidor Actual' }
        ],
    },
    // USAMOS RUTA ABSOLUTA PARA EVITAR ERRORES EN DOCKER
    apis: [path.join(__dirname, 'index.js')], 
};

const swaggerDocs = swaggerJsdoc(swaggerOptions);
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerDocs));


// ==========================================
// ⚙️ RUTAS DE CONFIGURACIÓN
// ==========================================

/**
 * @swagger
 * /api/config:
 * get:
 * summary: Obtener configuración actual
 * tags: [Configuración]
 * responses:
 * 200:
 * description: Configuración obtenida
 * content:
 * application/json:
 * schema:
 * type: object
 * properties:
 * rtsp_url:
 * type: string
 * example: "rtsp://admin:1234@192.168.1.50:554/cam"
 */
app.get('/api/config', (req, res) => {
    res.json(Config.getConfig());
});

/**
 * @swagger
 * /api/config:
 * post:
 * summary: Actualizar configuración
 * tags: [Configuración]
 * requestBody:
 * required: true
 * content:
 * application/json:
 * schema:
 * type: object
 * properties:
 * rtsp_url:
 * type: string
 * example: "rtsp://admin:1234@192.168.1.50:554/cam"
 * global_enabled:
 * type: boolean
 * responses:
 * 200:
 * description: Guardado exitosamente
 */
app.post('/api/config', (req, res) => {
    Config.saveConfig(req.body);
    Logger.addLog('SISTEMA', 'INFO', 'Configuración actualizada vía API');
    res.json({ success: true });
});


// ==========================================
// 📜 RUTAS DE LOGS
// ==========================================

/**
 * @swagger
 * /api/log:
 * post:
 * summary: Registrar evento de IA
 * tags: [Logs]
 * requestBody:
 * required: true
 * content:
 * application/json:
 * schema:
 * type: object
 * required: [message]
 * properties:
 * source:
 * type: string
 * level:
 * type: string
 * message:
 * type: string
 * responses:
 * 200:
 * description: Log creado
 */
app.post('/api/log', (req, res) => {
    const { source, level, message } = req.body;
    if (!message) return res.status(400).json({ error: 'Falta mensaje' });
    Logger.addLog(source, level, message);
    console.log(`📝 [${source || 'SISTEMA'}] ${message}`);
    res.status(200).json({ success: true });
});

/**
 * @swagger
 * /api/logs:
 * get:
 * summary: Consultar historial
 * tags: [Logs]
 * parameters:
 * - in: query
 * name: source
 * schema:
 * type: string
 * description: Filtrar por módulo
 * responses:
 * 200:
 * description: Lista de eventos
 */
app.get('/api/logs', (req, res) => {
    const { source } = req.query; 
    res.json(Logger.getLogs(source));
});

app.get('/health', (req, res) => res.send('OK'));

app.listen(PORT, () => {
    console.log(`🚀 API en puerto: ${PORT}`);
    console.log(`📘 Docs en /api-docs`);
});