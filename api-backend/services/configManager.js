const fs = require('fs');
const path = require('path');
const FILE = path.join(__dirname, '../config.json');

const defaults = { rtsp_url: null };

function getConfig() {
    if (fs.existsSync(FILE)) {
        try { return { ...defaults, ...JSON.parse(fs.readFileSync(FILE)) }; }
        catch (e) { return defaults; }
    }
    return defaults;
}

function saveConfig(data) {
    const current = getConfig();
    const next = { ...current, ...data };
    fs.writeFileSync(FILE, JSON.stringify(next, null, 2));
    return next;
}

module.exports = { getConfig, saveConfig };