# MensaDesk — Cliente de Escritorio (.exe)

Cliente Windows del sistema MensaPanel + MensaDesk.
Se ejecuta en segundo plano en cada PC de la empresa y muestra ventanas emergentes cuando el administrador envía un mensaje.

---

## Requisitos para compilar el .exe

| Herramienta | Version | Donde descargar |
|-------------|---------|-----------------|
| Python      | 3.10+   | https://www.python.org/downloads/ |
| pip         | Incluido con Python | — |

> Python solo se necesita en la PC que **compila** el .exe.
> Las PCs que reciben mensajes solo necesitan el archivo `MensaDesk.exe`.

---

## Paso 1 — Instalar dependencias Python

Abrir una terminal (cmd o PowerShell) en la carpeta `infoDesk` y ejecutar:

```bash
pip install -r requirements.txt
```

Esto instala:

| Libreria        | Para que sirve |
|-----------------|----------------|
| websocket-client | Conexion WebSocket al servidor Reverb |
| pystray          | Icono en la bandeja del sistema (system tray) |
| Pillow           | Mostrar imagenes en la ventana emergente |
| PyMuPDF          | Renderizar paginas de PDF como imagenes |
| pywin32          | Registro de Windows para inicio automatico |
| requests         | Llamadas HTTP al servidor (confirmaciones, registro) |
| pyinstaller      | Compilar todo en un .exe sin dependencias |

---

## Paso 2 — Configurar config.ini

> **IMPORTANTE:** Todos los campos del `config.ini` describen DONDE esta el SERVIDOR (infoAdmin/Laravel),
> no donde esta el .exe. El .exe es el que se conecta al servidor — no tiene IP propia.

```
PC del empleado (tiene el .exe)         Servidor de la empresa (tiene infoAdmin)
      [MensaDesk.exe]          ───────>       [Laravel + Reverb]
         config.ini                              .env del servidor
   (apunta al servidor)
```

Editar el archivo `config.ini` antes de compilar:

```ini
[servidor]
host    = localhost
port    = 8080
app_key = xk2z9tboo2ajmwtwl2qn
scheme  = ws
api_url = http://localhost:8000

[pc]
nombre =
```

---

### Explicacion de cada campo

#### `host` — IP o dominio del servidor donde corre infoAdmin

Es la direccion de la maquina donde esta instalado y corriendo el panel MensaPanel.
NO es la IP de la PC que tiene el .exe.

```ini
host = localhost          ; El servidor es la misma PC donde estas probando
host = 192.168.1.100      ; El servidor es otra PC dentro de la misma red de la empresa
host = mensajes.empresa.com  ; El servidor es un VPS en internet con dominio propio
```

---

#### `port` — Puerto del servidor WebSocket Reverb

Puerto donde escucha `php artisan reverb:start` en el servidor.
Por defecto es **8080** y no necesitas cambiarlo salvo que lo hayas modificado
en el `.env` del servidor (`REVERB_SERVER_PORT`).

```ini
port = 8080   ; Desarrollo y red local (sin SSL)
port = 443    ; Produccion con SSL (el servidor usa HTTPS)
```

---

#### `app_key` — Clave secreta del canal WebSocket

Es la contrasena/identificador compartido entre el servidor y los clientes.
Si este valor no coincide exactamente con el del servidor, la conexion WebSocket
sera rechazada y no llegaran mensajes.

**Como obtenerlo:**

1. Abrir el archivo `infoAdmin/.env` del servidor
2. Buscar la linea:
```env
REVERB_APP_KEY=xk2z9tboo2ajmwtwl2qn
```
3. Copiar ese valor exacto al `config.ini`:
```ini
app_key = xk2z9tboo2ajmwtwl2qn
```

> Si el administrador cambia el `REVERB_APP_KEY` en el servidor,
> hay que actualizar `config.ini` en todos los .exe de la empresa y recompilar.

---

#### `scheme` — Protocolo de la conexion WebSocket

```ini
scheme = ws    ; Sin SSL — para desarrollo o red local interna (HTTP)
scheme = wss   ; Con SSL — para servidor en internet con certificado HTTPS
```

Regla simple:
- Si `api_url` empieza con `http://`  → usar `scheme = ws`
- Si `api_url` empieza con `https://` → usar `scheme = wss`

---

#### `api_url` — URL base HTTP del servidor Laravel

El .exe usa esta URL para dos cosas:
1. Registrar la PC como activa (el panel muestra cuantas PCs estan conectadas)
2. Enviar confirmaciones de lectura cuando el empleado presiona "Confirmar lectura"

```ini
api_url = http://localhost:8000         ; Desarrollo local
api_url = http://192.168.1.100:8000     ; Red local, servidor en otra PC
api_url = https://mensajes.empresa.com  ; Servidor en internet con SSL
```

> El puerto `:8000` es el de `php artisan serve`. En produccion con Nginx no necesitas el puerto.

---

#### `nombre` (seccion [pc]) — Nombre identificador de esta PC

Con este nombre el administrador identifica cada PC en la pantalla de Confirmaciones.

```ini
nombre =               ; Autodetecta el hostname de Windows (ej: DESKTOP-ABC123)
nombre = PC-VENTAS-01  ; Nombre personalizado (recomendado para mayor claridad)
nombre = Recepcion     ; Puede ser el nombre del puesto de trabajo
```

---

### Ejemplos de configuracion completa

**Desarrollo / prueba en la misma PC:**
```ini
[servidor]
host    = localhost
port    = 8080
app_key = xk2z9tboo2ajmwtwl2qn
scheme  = ws
api_url = http://localhost:8000

[pc]
nombre = PC-PRUEBA
```

**Red local de empresa (servidor en PC con IP fija 192.168.1.100):**
```ini
[servidor]
host    = 192.168.1.100
port    = 8080
app_key = xk2z9tboo2ajmwtwl2qn
scheme  = ws
api_url = http://192.168.1.100:8000

[pc]
nombre = PC-CONTABILIDAD-01
```

**Servidor en internet con dominio y SSL:**
```ini
[servidor]
host    = mensajes.miempresa.com
port    = 443
app_key = xk2z9tboo2ajmwtwl2qn
scheme  = wss
api_url = https://mensajes.miempresa.com

[pc]
nombre = PC-SUCURSAL-NORTE
```

---

## Paso 3 — Agregar un icono (opcional)

Colocar un archivo llamado `icono.ico` en la carpeta `infoDesk/`.

- Debe ser formato `.ico` de Windows
- Tamaño recomendado: 64x64 o 256x256 pixeles
- Si no existe, MensaDesk usa un icono azul generado automaticamente

---

## Paso 4 — Compilar el .exe

Ejecutar el script de compilacion:

```bash
build.bat
```

O manualmente con PyInstaller:

```bash
pyinstaller --onefile --windowed --icon=icono.ico --name=MensaDesk --add-data "config.ini;." cliente.py
```

El proceso tarda entre 1 y 5 minutos. Al terminar:

```
dist/
└── MensaDesk.exe   <- Este es el ejecutable final
```

---

## Paso 5 — Distribuir a cada PC

Copiar estos 2 archivos a cada computadora de la empresa:

```
MensaDesk.exe   <- El ejecutable compilado
config.ini      <- La configuracion con la URL del servidor
```

> El `config.ini` debe estar en la **misma carpeta** que `MensaDesk.exe`.

---

## Paso 6 — Ejecutar en cada PC

1. Hacer doble clic en `MensaDesk.exe`
2. Aparece un icono azul en la **bandeja del sistema** (esquina inferior derecha, junto al reloj)
3. MensaDesk queda corriendo en segundo plano
4. La primera vez que se ejecuta, se registra automaticamente para **iniciar con Windows**

### Menu del icono en bandeja

Clic derecho sobre el icono de MensaDesk:

| Opcion | Accion |
|--------|--------|
| Ver ultimo mensaje | Re-abre la ultima notificacion recibida |
| Configuracion | Abre `config.ini` para editar la URL del servidor |
| Salir | Cierra MensaDesk completamente |

---

## Como funciona la ventana emergente

Cuando el administrador envia un mensaje desde MensaPanel, aparece automaticamente en la esquina inferior derecha:

```
+----------------------------------+
|  NOTIFICACION                  X |   <- Header con color segun tipo
+----------------------------------+
|  Titulo del mensaje              |
|  De: Administrador — 14:30:00   |
|  --------------------------------|
|  Contenido del mensaje...        |
|  (con scroll si es largo)        |
|  --------------------------------|
|  [imagen o paginas PDF aqui]     |
+----------------------------------+
|  [Confirmar lectura] [Ver tarde] |   <- Botones inferiores
+----------------------------------+
```

### Colores por tipo de mensaje

| Tipo         | Color    |
|--------------|----------|
| Notificacion | Azul     |
| Instructivo  | Verde    |
| Urgente      | Rojo + sonido de alerta |
| Reunion      | Naranja  |

### Si llega un nuevo mensaje mientras hay uno abierto

El nuevo mensaje se encola y aparece automaticamente cuando se cierra el actual.

### Botones

- **Confirmar lectura** — Registra que el empleado vio el mensaje y cierra la ventana
- **Ver mas tarde** — Cierra la ventana sin confirmar (el mensaje queda en la bandeja)

---

## Archivos del proyecto

```
infoDesk/
├── cliente.py        <- Logica principal: WebSocket, system tray, inicio automatico
├── ventana.py        <- Ventana emergente tkinter con visor PDF/imagen
├── config.ini        <- URL del servidor (editar antes de compilar)
├── requirements.txt  <- Dependencias Python
├── build.bat         <- Script de compilacion
├── icono.ico         <- Icono opcional (crear antes de compilar)
└── dist/
    └── MensaDesk.exe <- Ejecutable compilado (se genera con build.bat)
```

---

## Logs y depuracion

MensaDesk genera un archivo de log en la misma carpeta del `.exe`:

```
mensadesk.log
```

Contiene registros de:
- Conexiones y desconexiones al servidor
- Mensajes recibidos
- Confirmaciones enviadas
- Errores de red

---

## Desinstalar / quitar inicio automatico

Para remover MensaDesk del inicio automatico de Windows:

1. Abrir **Editor del Registro** (regedit.exe)
2. Ir a: `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
3. Eliminar la entrada llamada `MensaDesk`

O desde PowerShell:
```powershell
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "MensaDesk"
```

---

## Solucion de problemas

| Problema | Solucion |
|----------|----------|
| El .exe no aparece en bandeja | Verificar que `config.ini` esta en la misma carpeta que el .exe |
| "Error de conexion" en el log | Verificar que el servidor esta corriendo y la IP/puerto en `config.ini` es correcta |
| No llegan mensajes | Verificar que `app_key` en `config.ini` coincide con `REVERB_APP_KEY` del servidor |
| El .exe no compila | Ejecutar `pip install -r requirements.txt` nuevamente y revisar errores |
| La ventana no muestra el PDF | Verificar que PyMuPDF se instalo correctamente: `python -c "import fitz; print('OK')"` |
| Antivirus bloquea el .exe | Agregar excepcion en el antivirus para `MensaDesk.exe` (falso positivo comun con PyInstaller) |

---

## Probar sin compilar (modo desarrollo)

Para probar el cliente sin generar el .exe:

```bash
python cliente.py
```

Requiere que las dependencias esten instaladas (`pip install -r requirements.txt`).
"# infoAdmin" 
"# infoDesk" 
