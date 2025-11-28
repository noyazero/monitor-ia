const logs = [];
const MAX_LOGS = 300; // Guardamos historial de 300 eventos

function getTimestamp() {
    // Hora Chile
    return new Date().toLocaleString('es-CL', { timeZone: 'America/Santiago' });
}

function addLog(source, level, message) {
    const entry = {
        id: Date.now() + Math.random().toString(36).substr(2, 5),
        timestamp: getTimestamp(),
        source: source || 'SISTEMA', // Ej: FUEGO, EPP
        level: level || 'INFO',      // Ej: ALERTA, PELIGRO
        message: message
    };
    logs.unshift(entry); // El más nuevo primero
    if (logs.length > MAX_LOGS) logs.pop();
    return entry;
}

function getLogs(filterSource) {
    if (filterSource) return logs.filter(l => l.source === filterSource);
    return logs;
}

module.exports = { addLog, getLogs };