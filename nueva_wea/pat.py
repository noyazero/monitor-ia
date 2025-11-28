import cv2
from ultralytics import YOLO
import easyocr
import re
from collections import Counter
import time
import subprocess
import os
import shutil
from threading import Thread, Lock 

# ---------------------------------------------------------
# CLASE ANTI-LAG
# ---------------------------------------------------------
class CameraStream:
    def __init__(self, src):
        self.stream = cv2.VideoCapture(src)
        (self.grabbed, self.frame) = self.stream.read()
        self.started = False
        self.read_lock = Lock()

    def start(self):
        if self.started: return None
        self.started = True
        self.thread = Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()
        return self

    def update(self):
        while self.started:
            (grabbed, frame) = self.stream.read()
            self.read_lock.acquire()
            self.grabbed, self.frame = grabbed, frame
            self.read_lock.release()
            time.sleep(0.01)

    def read(self):
        self.read_lock.acquire()
        frame = self.frame.copy() if self.frame is not None else None
        self.read_lock.release()
        return frame

    def stop(self):
        self.started = False
        self.thread.join()
        self.stream.release()

# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------

def cargar_whitelist(ruta_txt):
    patentes = set()
    try:
        with open(ruta_txt, 'r') as f:
            for linea in f:
                p = linea.strip().upper() 
                if p: patentes.add(p)
        print(f"Base de datos cargada: {len(patentes)} patentes.")
        return patentes
    except FileNotFoundError:
        return set()

def abrir_porton_adb_thread(numero_porton):
    print(f"[HILO] Iniciando llamada a {numero_porton}...")
    adb_path = "adb.exe" if os.path.exists("adb.exe") else "adb"
    try:
        subprocess.run(f'{adb_path} shell input keyevent 224', shell=True)
        subprocess.run(f'{adb_path} shell input keyevent 82', shell=True)
        time.sleep(1)
        subprocess.run(f'{adb_path} shell am start -a android.intent.action.CALL -d tel:{numero_porton}', shell=True)
        time.sleep(15) 
        subprocess.run(f'{adb_path} shell input keyevent 6', shell=True)
        print("[HILO] Llamada finalizada.")
    except Exception as e:
        print(f"[ERROR HILO] {e}")

def validar_patente_chile(texto):
    texto_limpio = re.sub(r'[^A-Z0-9]', '', texto.upper())
    if re.match(r'^[A-Z]{4}\d{2}$', texto_limpio) or re.match(r'^[A-Z]{2}\d{4}$', texto_limpio):
        return texto_limpio
    if len(texto_limpio) == 7:
        recorte = texto_limpio[1:]
        if re.match(r'^[A-Z]{4}\d{2}$', recorte) or re.match(r'^[A-Z]{2}\d{4}$', recorte):
            return recorte
    return None

# ---------------------------------------------------------
# PROCESO PRINCIPAL
# ---------------------------------------------------------

def iniciar_vigilancia():
    ruta_modelo = 'runs/detect/mi_entrenamiento_local6/weights/best.pt' 
    url_rtsp = "rtsp://Nico:Nico2025@190.102.229.163:8554/cam/realmonitor?channel=4&subtype=0"
    archivo_whitelist = 'patentesRegistradas.txt'
    TIEMPO_ESPERA_ENTRE_LLAMADAS = 45 

    # UMBRAL DE MOVIMIENTO (Píxeles)
    # Si la patente se mueve menos de esto, se considera que está quieta.
    # Si el valor es positivo (> UMBRAL), está bajando (entrando).
    UMBRAL_MOVIMIENTO_PIXELES = 30 

    NOMBRE_VENTANA = "Deteccion Direccional"
    cv2.namedWindow(NOMBRE_VENTANA, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(NOMBRE_VENTANA, 1280, 720)

    patentes_buscadas = cargar_whitelist(archivo_whitelist)
    historial_llamadas = {} 
    
    mensaje_pantalla = "ESPERANDO VEHICULO..."
    color_mensaje = (255, 255, 255) 

    print("Cargando IA...")
    reader = easyocr.Reader(['en'], gpu=True) 
    model = YOLO(ruta_modelo)
    
    print("Conectando cámara...")
    cam_stream = CameraStream(url_rtsp).start()
    time.sleep(2) 

    buffer_lecturas = []
    buffer_y = [] # ### NUEVO: AQUÍ GUARDAREMOS LA ALTURA Y ###
    tamanho_buffer = 15 

    print("--- VIGILANCIA DIRECCIONAL ACTIVA ---")

    while True:
        frame = cam_stream.read()
        if frame is None:
            time.sleep(0.1)
            continue

        results = model.predict(frame, conf=0.6, verbose=False)
        deteccion_en_cuadro = False

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                h, w, _ = frame.shape
                x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                
                # Calculamos el centro vertical de la patente
                centro_y = (y1 + y2) // 2

                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                
                patente_img = frame[y1:y2, x1:x2]
                if patente_img.shape[0] < 10 or patente_img.shape[1] < 10: continue

                try:
                    lectura = reader.readtext(patente_img, detail=0, paragraph=True)
                    if lectura:
                        p_valida = validar_patente_chile(lectura[0])

                        if p_valida:
                            buffer_lecturas.append(p_valida)
                            buffer_y.append(centro_y) # ### GUARDAMOS POSICIÓN ###
                            deteccion_en_cuadro = True
                            
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                            cv2.putText(frame, p_valida, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                except: pass

        if not deteccion_en_cuadro and len(buffer_lecturas) > 0:
            buffer_lecturas.pop(0)
            if len(buffer_y) > 0: buffer_y.pop(0)

        # --- ANÁLISIS ---
        if len(buffer_lecturas) >= tamanho_buffer:
            conteo = Counter(buffer_lecturas)
            patente_ganadora, votos = conteo.most_common(1)[0]
            
            if votos > (tamanho_buffer / 2):
                
                # ### LÓGICA DE DIRECCIÓN ###
                # Tomamos el promedio de los primeros 5 frames vs los últimos 5 frames
                # para evitar errores por saltos pequeños
                inicio_y = sum(buffer_y[:5]) / 5
                fin_y = sum(buffer_y[-5:]) / 5
                
                desplazamiento = fin_y - inicio_y
                
                # Debug en consola
                # print(f"Patente: {patente_ganadora} | Inicio Y: {inicio_y:.1f} | Fin Y: {fin_y:.1f} | Mov: {desplazamiento:.1f}")

                es_entrada = False
                
                # Si el desplazamiento es POSITIVO y mayor al umbral, está BAJANDO (Entrando)
                if desplazamiento > UMBRAL_MOVIMIENTO_PIXELES:
                    es_entrada = True
                    mensaje_pantalla = f"ENTRANDO ({int(desplazamiento)}px)"
                    color_mensaje = (0, 255, 0) # Verde
                # Si es NEGATIVO y menor al umbral negativo, está SUBIENDO (Saliendo)
                elif desplazamiento < -UMBRAL_MOVIMIENTO_PIXELES:
                    es_entrada = False
                    mensaje_pantalla = f"SALIENDO ({int(desplazamiento)}px) - IGNORAR"
                    color_mensaje = (0, 0, 255) # Rojo
                else:
                    mensaje_pantalla = "VEHICULO DETENIDO"
                    color_mensaje = (255, 255, 0) # Amarillo

                # Solo abrimos si ES ENTRADA y está en WHITELIST
                if es_entrada:
                    if patente_ganadora in patentes_buscadas:
                        tiempo_actual = time.time()
                        ultima_llamada = historial_llamadas.get(patente_ganadora, 0)
                        
                        if (tiempo_actual - ultima_llamada) > TIEMPO_ESPERA_ENTRE_LLAMADAS:
                            print(f"!!! ACCESO: {patente_ganadora} (Entrando) !!!")
                            mensaje_pantalla = f"ABRIENDO: {patente_ganadora}"
                            
                            NUMERO = "+56978074942"
                            t = Thread(target=abrir_porton_adb_thread, args=(NUMERO,))
                            t.start()
                            
                            historial_llamadas[patente_ganadora] = tiempo_actual
                        else:
                            mensaje_pantalla = f"ENFRIAMIENTO: {patente_ganadora}"
                    else:
                        mensaje_pantalla = f"NO REGISTRADA: {patente_ganadora}"
                        color_mensaje = (0, 0, 255)

                # Limpiamos buffers para reiniciar análisis
                buffer_lecturas.clear()
                buffer_y.clear()

            else:
                buffer_lecturas.pop(0)
                if len(buffer_y) > 0: buffer_y.pop(0)
        
        # Reset visual
        if not deteccion_en_cuadro and "ABRIENDO" not in mensaje_pantalla:
            if len(buffer_lecturas) == 0:
                mensaje_pantalla = "VIGILANDO ZONA..."
                color_mensaje = (200, 200, 200)

        # Interfaz
        cv2.rectangle(frame, (0, 0), (650, 60), (0, 0, 0), -1)
        cv2.putText(frame, mensaje_pantalla, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_mensaje, 2)
        
        # Dibujar flecha guía (opcional, para referencia)
        h_img, w_img = frame.shape[:2]
        # Flecha verde hacia abajo en el lado derecho indicando "Entrada"
        cv2.arrowedLine(frame, (w_img-50, 50), (w_img-50, 150), (0, 255, 0), 3, tipLength=0.3)
        cv2.putText(frame, "ENTRADA", (w_img-120, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.imshow(NOMBRE_VENTANA, frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam_stream.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    iniciar_vigilancia()