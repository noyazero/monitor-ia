import cv2
import threading
import queue
import face_recognition
import numpy as np
from ultralytics import YOLO
import os
import torch
import math
import time

# --- CLASE 1: Lector RTSP (Optimizado para hilos múltiples) ---
class LectorRTSP:
    def __init__(self, url_rtsp, nombre_camara):
        self.nombre = nombre_camara
        self.cap = cv2.VideoCapture(url_rtsp)
        # Cola muy pequeña (1 frame) para evitar que se acumule lag
        self.q = queue.Queue(maxsize=1) 
        self.running = True
        self.connected = self.cap.isOpened()
        
        if self.connected:
            print(f"✅ Conectado a {nombre_camara}")
        else:
            print(f"❌ Error al conectar a {nombre_camara}")

        self.t = threading.Thread(target=self._leer_frames)
        self.t.daemon = True
        self.t.start()

    def _leer_frames(self):
        while self.running:
            if self.connected:
                ret, frame = self.cap.read()
                if not ret:
                    print(f"⚠️ Pérdida de señal en {self.nombre}, reconectando...")
                    self.cap.release()
                    self.connected = False
                    continue
                
                # Vaciar cola y poner frame nuevo
                if not self.q.empty():
                    try: self.q.get_nowait()
                    except queue.Empty: pass
                self.q.put(frame)
            else:
                # Intento de reconexión simple
                time.sleep(2)
                # Aquí podrías poner lógica de reconexión real si fuera necesario

    def leer(self):
        return self.q.get() if not self.q.empty() else None

    def detener(self):
        self.running = False
        if self.cap.isOpened():
            self.cap.release()

# --- CLASE 2: Sistema IA Centralizado ---
class SistemaIA:
    def __init__(self):
        dispositivo = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"⚡ IA corriendo en: {dispositivo.upper()}")
        
        self.detector_personas = YOLO('yolov8n.pt') 
        self.caras_conocidas_encodings = []
        self.caras_conocidas_nombres = []
        self.cargar_base_de_datos("empleados")

        # DICCIONARIO DE MEMORIAS: Clave = ID de Cámara, Valor = Lista de personas
        self.memorias_por_camara = {} 
        self.umbral_seguimiento = 100 

    def cargar_base_de_datos(self, carpeta_raiz):
        if not os.path.exists(carpeta_raiz): os.makedirs(carpeta_raiz); return
        
        nombres = [d for d in os.listdir(carpeta_raiz) if os.path.isdir(os.path.join(carpeta_raiz, d))]
        for nombre in nombres:
            ruta = os.path.join(carpeta_raiz, nombre)
            for foto in os.listdir(ruta):
                if foto.lower().endswith(('.jpg', '.jpeg', '.png')):
                    try:
                        path = os.path.join(ruta, foto)
                        img = face_recognition.load_image_file(path)
                        encs = face_recognition.face_encodings(img)
                        if encs:
                            self.caras_conocidas_encodings.append(encs[0])
                            self.caras_conocidas_nombres.append(nombre)
                    except: pass
        print(f"✅ Base de datos: {len(self.caras_conocidas_nombres)} personas cargadas.")

    def calcular_centro(self, x1, y1, x2, y2):
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def procesar_frame(self, frame, id_camara):
        if frame is None: return np.zeros((360, 640, 3), dtype=np.uint8)
        
        # Inicializar memoria para esta cámara si no existe
        if id_camara not in self.memorias_por_camara:
            self.memorias_por_camara[id_camara] = []

        alto, ancho, _ = frame.shape
        
        # Detección YOLO
        # Usamos conf=0.5 para filtrar falsos positivos y ganar velocidad
        resultados = self.detector_personas(frame, classes=[0], verbose=False, device=0 if torch.cuda.is_available() else 'cpu', conf=0.5)
        
        personas_frame_actual = []
        memoria_anterior = self.memorias_por_camara[id_camara]

        for r in resultados:
            for caja in r.boxes:
                x1, y1, x2, y2 = map(int, caja.xyxy[0])
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(ancho, x2), min(alto, y2)
                
                centro_actual = self.calcular_centro(x1, y1, x2, y2)
                
                # --- TRACKING (Recuperar identidad por posición) ---
                nombre_detectado = "Visitante"
                color = (0, 165, 255) # Naranja
                
                mejor_distancia = 9999
                match_memoria = None

                for persona_memoria in memoria_anterior:
                    centro_viejo = persona_memoria['centro']
                    distancia = math.hypot(centro_actual[0] - centro_viejo[0], centro_actual[1] - centro_viejo[1])
                    if distancia < self.umbral_seguimiento and distancia < mejor_distancia:
                        mejor_distancia = distancia
                        match_memoria = persona_memoria

                if match_memoria:
                    nombre_detectado = match_memoria['nombre']
                    if nombre_detectado != "Visitante":
                        color = (0, 255, 0)

                # --- RECONOCIMIENTO FACIAL ---
                persona_img = frame[y1:y2, x1:x2]
                if persona_img.size > 0:
                    try:
                        # Reducimos imagen para velocidad (optimización clave para multicámara)
                        small_frame = cv2.resize(persona_img, (0, 0), fx=0.5, fy=0.5)
                        rgb_recorte = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                        
                        locaciones = face_recognition.face_locations(rgb_recorte, model="hog")
                        if locaciones:
                            encodings = face_recognition.face_encodings(rgb_recorte, locaciones)
                            for encoding in encodings:
                                matches = face_recognition.compare_faces(self.caras_conocidas_encodings, encoding, tolerance=0.55)
                                if True in matches:
                                    nombre_detectado = self.caras_conocidas_nombres[matches.index(True)]
                                    color = (0, 255, 0)
                                    break
                    except: pass

                personas_frame_actual.append({
                    'centro': centro_actual, 'nombre': nombre_detectado, 
                    'box': (x1, y1, x2, y2), 'color': color
                })

                # Dibujar
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, nombre_detectado, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Actualizamos la memoria específica de ESTA cámara
        self.memorias_por_camara[id_camara] = personas_frame_actual
        
        # Escribimos el nombre de la cámara en la pantalla
        cv2.putText(frame, id_camara, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        return frame

# --- FUNCIÓN DE VISUALIZACIÓN (MOSAICO) ---
def crear_mosaico(lista_frames, columnas=3, tamaño_fijo=(640, 360)):
    frames_redimensionados = []
    for f in lista_frames:
        if f is not None:
            frames_redimensionados.append(cv2.resize(f, tamaño_fijo))
        else:
            # Si una cámara falla, mostramos cuadro negro
            frames_redimensionados.append(np.zeros((tamaño_fijo[1], tamaño_fijo[0], 3), dtype=np.uint8))

    # Rellenar con cuadros negros si faltan para completar la fila
    while len(frames_redimensionados) % columnas != 0:
        frames_redimensionados.append(np.zeros((tamaño_fijo[1], tamaño_fijo[0], 3), dtype=np.uint8))

    # Crear filas y unirlas
    filas = []
    for i in range(0, len(frames_redimensionados), columnas):
        fila = np.hstack(frames_redimensionados[i:i+columnas])
        filas.append(fila)
    
    return np.vstack(filas)

# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    # 1. DEFINICIÓN DE CÁMARAS
    base_url = "rtsp://Nico:Nico2025@190.102.229.163:8554/cam/realmonitor?channel={}&subtype=0"
    canales = [8, 9, 10, 11, 12] # Agrega o quita canales aquí
    
    # Lista de objetos lectores
    lectores = []
    for canal in canales:
        url = base_url.format(canal)
        lectores.append(LectorRTSP(url, f"Camara {canal}"))

    sistema = SistemaIA()

    print("--- MONITOR CENTRALIZADO INICIADO ---")
    
    try:
        while True:
            frames_capturados = []
            
            # 2. LEER Y PROCESAR CADA CÁMARA
            for lector in lectores:
                frame = lector.leer()
                
                # Procesamos el frame (le pasamos el nombre de la cámara para que use la memoria correcta)
                if frame is not None:
                    # Reducir resolución de entrada para mejorar FPS si es necesario
                    # frame = cv2.resize(frame, (640, 360)) 
                    frame_procesado = sistema.procesar_frame(frame, lector.nombre)
                    frames_capturados.append(frame_procesado)
                else:
                    frames_capturados.append(None)

            # 3. GENERAR VISTA DE MOSAICO
            if any(f is not None for f in frames_capturados):
                # Ajusta 'columnas' según cuántas cámaras tengas (ej: 2 o 3)
                mosaico = crear_mosaico(frames_capturados, columnas=3, tamaño_fijo=(480, 270))
                
                cv2.imshow("Centro de Control AI", mosaico)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        print(f"Error global: {e}")
    finally:
        for l in lectores: l.detener()
        cv2.destroyAllWindows()