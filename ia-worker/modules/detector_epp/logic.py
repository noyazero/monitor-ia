from ultralytics import YOLO
import os
import time
import json

class Detector:
    def __init__(self, path):
        """
        Inicializa el detector de EPP.
        path: La ruta de la carpeta del módulo (donde está el config.json y el modelo)
        """
        self.name = "DETECTOR_EPP"
        self.path = path
        
        # 1. Cargar Configuración (o usar valores por defecto)
        config_file = os.path.join(path, 'config.json')
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = { "confianza": 0.5, "cooldown": 10, "clases_alerta": [] }

        # 2. Cargar Modelo
        # Intenta buscar 'best.pt' en la carpeta del módulo. 
        # Si no está, usa el modelo base de YOLO para que no falle.
        model_path = os.path.join(path, 'best.pt')
        if os.path.exists(model_path):
            print(f"🛡️ {self.name}: Cargando modelo personalizado desde {model_path}")
            self.model = YOLO(model_path)
        else:
            print(f"⚠️ {self.name}: No se encontró 'best.pt'. Usando 'yolov8n.pt' (modo prueba)")
            self.model = YOLO('yolov8n.pt')

        # Variables para controlar el spam de alertas (Cooldown)
        self.last_alert_time = 0
        self.cooldown = self.config.get('cooldown', 10) # Segundos entre alertas

    def process(self, frame):
        """
        Recibe un frame de video, busca infracciones y retorna alerta si corresponde.
        """
        # 1. Verificar si estamos en tiempo de enfriamiento (para no spammear)
        if (time.time() - self.last_alert_time) < self.cooldown:
            return None

        # 2. Configurar umbral de confianza
        confianza = self.config.get('confianza', 0.5)
        
        # 3. Inferencia (Detección)
        # verbose=False evita llenar la consola de texto
        results = self.model(frame, conf=confianza, verbose=False)

        clases_alerta = self.config.get('clases_alerta', []) 
        # Si clases_alerta está vacío, alertará con CUALQUIER cosa que detecte.
        
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0]) # ID de la clase detectada (0, 1, 2...)
                conf_val = float(box.conf[0])
                class_name = self.model.names[cls_id]

                # LÓGICA DE ALERTA:
                # Si la lista de alertas está vacía -> Alerta por todo lo que vea.
                # Si tiene IDs -> Solo alerta si la clase coincide (ej: solo "No-Helmet").
                if not clases_alerta or cls_id in clases_alerta:
                    
                    self.last_alert_time = time.time() # Reiniciar cooldown
                    
                    return {
                        "alert": True,
                        "level": "ALERTA", # Puede ser INFO, ALERTA, PELIGRO
                        "message": f"Detección EPP: {class_name} ({conf_val:.2f})"
                    }

        return None