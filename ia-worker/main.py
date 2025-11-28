import cv2
import time
import requests
import os
import importlib.util
import sys

API_URL = os.getenv("API_URL", "http://core:3001/api")
MODULES_DIR = "modules"

class Orchestrator:
    def __init__(self):
        self.modules = []
        self.rtsp_url = None
        
        # Espera inicial para que el backend arranque
        time.sleep(int(os.getenv("STARTUP_DELAY", 5)))
        
        self.connect_backend()
        self.load_modules()

    def connect_backend(self):
        """Busca la config RTSP en el backend"""
        print("📡 Conectando al Core...")
        while not self.rtsp_url:
            try:
                r = requests.get(f"{API_URL}/config", timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    self.rtsp_url = data.get('rtsp_url')
                    if self.rtsp_url:
                        print(f"✅ Cámara configurada: {self.rtsp_url}")
                        self.send_log("VISION", "INFO", "Sistema de visión iniciado")
                    else:
                        print("⚠️ Backend conectado, pero falta configurar RTSP. Esperando...")
                        time.sleep(5)
                else:
                    print("⚠️ Backend no responde OK. Reintentando...")
                    time.sleep(5)
            except:
                print("❌ No se encuentra el Backend. ¿Está corriendo el contenedor 'core'?")
                time.sleep(5)

    def load_modules(self):
        """Carga dinámica de carpetas en modules/"""
        if not os.path.exists(MODULES_DIR): os.makedirs(MODULES_DIR)
        
        for folder in os.listdir(MODULES_DIR):
            path = os.path.join(MODULES_DIR, folder)
            if os.path.isdir(path) and not folder.startswith('_'):
                try:
                    logic_path = os.path.join(path, "logic.py")
                    if not os.path.exists(logic_path): continue
                    
                    spec = importlib.util.spec_from_file_location(f"mod_{folder}", logic_path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    
                    # Instanciamos el Detector
                    instance = mod.Detector(path)
                    self.modules.append(instance)
                    print(f"🧩 Módulo Cargado: {instance.name}")
                    self.send_log("VISION", "INFO", f"Módulo cargado: {instance.name}")
                except Exception as e:
                    print(f"❌ Error cargando {folder}: {e}")

    def send_log(self, source, level, msg):
        try:
            requests.post(f"{API_URL}/log", json={"source": source, "level": level, "message": msg})
        except: pass

    def run(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Cámara desconectada. Reintentando...")
                time.sleep(5)
                cap = cv2.VideoCapture(self.rtsp_url)
                continue
            
            # Procesamos cada 5 frames para no saturar
            if frame_idx % 5 == 0:
                for mod in self.modules:
                    try:
                        res = mod.process(frame)
                        if res and res.get('alert'):
                            self.send_log(mod.name, res.get('level', 'ALERTA'), res.get('message'))
                    except Exception as e:
                        print(f"Error en {mod.name}: {e}")
            
            frame_idx += 1
            time.sleep(0.01)

if __name__ == "__main__":
    Orchestrator().run()