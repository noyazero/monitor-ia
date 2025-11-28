const express = require('express');
const cors = require('cors');
const swaggerUi = require('swagger-ui-express');

// --- AQUÍ LA DIFERENCIA: Importamos el JSON directo ---
const swaggerDocument = require('./swagger.json');

const Config = require('./services/configManager');
const Logger = require('./services/logger');

const app = express();
const PORT = 3001;

app.use(cors({ origin: '*' }));
app.use(express.json());

// --- CONFIGURACIÓN SWAGGER SIMPLE ---
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerDocument));


// ================= RUTAS =================

app.get('/api/config', (req, res) => {
    res.json(Config.getConfig());
});

app.post('/api/config', (req, res) => {
    Config.saveConfig(req.body);
    Logger.addLog('SISTEMA', 'INFO', 'Configuración actualizada vía API');
    res.json({ success: true });
});

app.post('/api/log', (req, res) => {
    const { source, level, message } = req.body;
    if (!message) return res.status(400).json({ error: 'Falta mensaje' });
    Logger.addLog(source, level, message);
    console.log(`📝 [${source || 'SISTEMA'}] ${message}`);
    res.status(200).json({ success: true });
});

app.get('/api/logs', (req, res) => {
    const { source } = req.query; 
    res.json(Logger.getLogs(source));
});

app.get('/health', (req, res) => res.send('OK'));

app.listen(PORT, () => {
    console.log(`🚀 API Core en puerto ${PORT}`);
    console.log(`📘 Docs en /api-docs`);
});