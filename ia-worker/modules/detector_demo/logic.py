import time

class Detector:
    def __init__(self, path):
        self.name = "DEMO_TEST"
        self.last_trigger = 0
        
    def process(self, frame):
        # Simula una alerta cada 30 segundos solo para probar la conexión
        now = time.time()
        if now - self.last_trigger > 30:
            self.last_trigger = now
            return {
                "alert": True,
                "level": "INFO",
                "message": "Prueba de conexión: El sistema de visión está vivo."
            }
        return None