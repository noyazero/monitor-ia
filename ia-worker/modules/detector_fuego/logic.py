from ultralytics import YOLO
import json
import os
import time

class Detector:
    def __init__(self, path):
        self.name = "DETECTOR_FUEGO"
        self.path = path
        
        # 1. Cargar Configuración Propia
        config_path = os.path.join(path, 'config.json')
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        # 2. Cargar Modelo (Asegúrate de tener un best.pt aquí o usa 'yolov8n.pt' para test)
        model_path = os.path.join(path, 'best.pt')
        if not os.path.exists(model_path):
            print(f"⚠️ No se encontró best.pt en {path}, usando modelo base...")
            self.model = YOLO('yolov8n.pt') 
        else:
            self.model = YOLO(model_path)

        # Control de "Enfriamiento" para no mandar 100 alertas por segundo
        self.last_alert_time = 0
        self.cooldown = self.config.get('cooldown_segundos', 10)

    def process(self, frame):
        # Verificar cooldown
        if (time.time() - self.last_alert_time) < self.cooldown:
            return None

        conf_umbral = self.config.get('confianza', 0.5)
        
        # Inferencia
        # Importante: classes=[...] depende de tu modelo. 
        # Si usas un modelo genérico, clase 0 suele ser persona. Ajusta según tu entrenamiento.
        results = self.model(frame, conf=conf_umbral, verbose=False)
        
        for r in results:
            if len(r.boxes) > 0:
                # ¡DETECCION!
                self.last_alert_time = time.time()
                return {
                    "alert": True,
                    "level": "PELIGRO",
                    "message": f"Fuego detectado (Conf: {r.boxes.conf[0]:.2f})"
                }
        
        return None