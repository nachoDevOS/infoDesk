# infoDesk — Cliente de Escritorio Windows

Cliente Windows del sistema **infoAdmin + infoDesk**.
Se instala en las PCs de los empleados, corre en segundo plano y muestra ventanas emergentes cuando el administrador envía un mensaje desde infoAdmin.

---

## Cómo funciona

```
PC del empleado (infoDesk.exe)          Servidor (infoAdmin)
        |                                       |
        |--- HTTP :443  --->  API Laravel  -----|
        |--- WS   :8081 --->  Reverb WS   -----|
        |                                       |
        |<-- broadcast "mensaje.enviado"  -------|
        |                                       |
   Muestra ventana emergente
```

- El exe **no escucha** en ningún puerto — solo hace conexiones salientes al servidor.
- La IP/dominio del servidor se configura en `config.ini` al lado del exe.
- El `API_TOKEN` y `REVERB_APP_KEY` van **compilados dentro del exe** — el usuario final no los ve ni los toca.

---

## Requisitos para compilar

| Herramienta | Versión |
|-------------|---------|
| Python | 3.10+ |
| pip | incluido con Python |

> Python solo se necesita en la PC que **compila**. Las PCs que reciben mensajes solo necesitan `infoDesk.exe`.

### Instalar dependencias

```bash
pip install -r requirements.txt
```

| Librería | Para qué sirve |
|----------|----------------|
| websocket-client | Conexión WebSocket a Reverb |
| pystray | Ícono en la bandeja del sistema |
| Pillow | Imágenes en la ventana emergente |
| PyMuPDF | Renderizar PDFs como imagen |
| requests | Llamadas HTTP al servidor |
| pyinstaller | Compilar todo en un .exe |

---

## Compilar el .exe

```bash
build.bat
```

El ejecutable queda en:

```
dist/
├── infoDesk.exe
└── config.ini      <- se copia automáticamente
```

---

## Valores compilados dentro del exe

Estos valores van **hardcodeados** en `cliente.py` y no son visibles para el usuario final.
Si los cambiás en el servidor hay que **recompilar y redistribuir** el exe.

| Variable en cliente.py | Variable en .env del servidor |
|------------------------|-------------------------------|
| `_API_TOKEN` | `API_TOKEN` |
| `_SERVIDOR_APP_KEY` | `REVERB_APP_KEY` |

---

## Configuración inicial (primer arranque)

La primera vez que se abre el exe aparece una ventana de configuración:

```
┌─────────────────────────────────────────┐
│  ⚙  Configuración inicial — infoDesk   │
├─────────────────────────────────────────┤
│  Servidor (IP o dominio): [_________]   │
│  Puerto de Laravel:       [8000     ]   │
│  Puerto de Reverb:        [8080     ]   │
│  Nombre de esta PC:       [DESKTOP..]   │
│                                         │
│           [ Guardar y continuar ]       │
└─────────────────────────────────────────┘
```

Los valores se guardan en `config.ini` al lado del exe.

### Cuándo vuelve a aparecer

Solo si `host` en `config.ini` está vacío, es `localhost` o `127.0.0.1`.
Si ya tiene una IP/dominio real, no vuelve a aparecer.

### Reconfigurar manualmente

Editar `config.ini` directamente:

```ini
[servidor]
host        = notificaciones.beni.gob.bo
api_port    = 443
reverb_port = 8081

[pc]
nombre = PC-RECEPCION
```

---

## Referencia de config.ini

| Campo | Descripción | Ejemplo local | Ejemplo producción |
|-------|-------------|---------------|-------------------|
| `host` | IP o dominio de infoAdmin | `192.168.1.10` | `notificaciones.beni.gob.bo` |
| `api_port` | Puerto de Laravel | `8000` | `443` |
| `reverb_port` | Puerto de Reverb (WebSocket) | `8081` | `8081` |
| `nombre` | Nombre de esta PC en el panel | `PC-VENTAS` | `PC-ADMINISTRACION` |

> `nombre` vacío → usa el hostname de Windows automáticamente.

### Cómo se construyen las URLs

| `api_port` | URL de la API |
|------------|---------------|
| `443` | `https://host` |
| `80` | `http://host` |
| otro | `http://host:puerto` |

El WebSocket siempre usa `ws://host:reverb_port`.

---

## Ejemplos de configuración completa

**Red local (servidor en PC con IP fija):**
```ini
[servidor]
host        = 192.168.1.10
api_port    = 8000
reverb_port = 8081

[pc]
nombre = PC-CONTABILIDAD
```

**Producción con dominio y SSL (Coolify):**
```ini
[servidor]
host        = notificaciones.beni.gob.bo
api_port    = 443
reverb_port = 8081

[pc]
nombre = PC-RECEPCION
```

---

## Distribución a PCs de empleados

Copiar estos archivos a cada PC:

```
infoDesk.exe    <- ejecutable
config.ini      <- configuración del servidor
```

Al ejecutar por primera vez:
1. Se registra en inicio automático de Windows
2. Aparece ícono verde en la bandeja del sistema
3. Queda escuchando mensajes en segundo plano

---

## Menú bandeja del sistema

Clic derecho sobre el ícono:

| Opción | Acción |
|--------|--------|
| Ver último mensaje | Re-abre la última notificación |
| Bandeja de mensajes | Abre el historial local |
| Salir | Cierra infoDesk |

---

## Log y diagnóstico

El exe genera `mensadesk.log` en la misma carpeta:

```
2026-06-05 16:29:01 [INFO] WebSocket conectado
2026-06-05 16:29:01 [INFO] Suscrito al canal 'mensajes'
2026-06-05 16:29:14 [INFO] Mensaje recibido: Título del mensaje
2026-06-05 16:29:16 [INFO] Confirmación enviada: mensaje #11 — recibido
```

### Errores comunes

| Error en log | Causa | Solución |
|---|---|---|
| `WebSocket error: opcode=8 data=b'\x0f\xa1'` (código 4001) | `REVERB_APP_KEY` incorrecto o puerto equivocado | Verificar `reverb_port` en `config.ini` |
| `Reintentando conexión en 10 segundos` | No llega al servidor | Verificar `host` y `reverb_port` |
| `Error al registrar PC` | No llega a la API | Verificar `host` y `api_port` |

---

## Desinstalar inicio automático de Windows

```powershell
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "infoDesk"
```

---

## Estructura del proyecto

```
infoDesk/
├── cliente.py        <- lógica principal: WebSocket, tray, registro
├── ventana.py        <- ventana emergente tkinter con visor PDF/imagen
├── config.ini        <- configuración del servidor (se edita por UI)
├── requirements.txt  <- dependencias Python
├── build.bat         <- script de compilación
├── icono.ico         <- ícono del exe y bandeja
└── dist/
    ├── infoDesk.exe  <- ejecutable final
    └── config.ini    <- copia de configuración
```
