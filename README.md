# Drop Report — Dashboard Operativo de Dropshipping

Drop Report es un panel de control ultra-ligero y privado diseñado para procesar exportaciones de Excel de Dropi, visualizar KPIs en tiempo real, y gestionar un call center interno. Está optimizado para ejecutarse en entornos de bajos recursos como una **Raspberry Pi** utilizando Docker y SQLite.

---

## 🛠️ Requisitos Previos

- **En desarrollo (Mac/PC):** Python 3.9+, entorno virtual (`venv`).
- **En producción (Raspberry Pi):** Docker y Docker Compose instalados.

---

## 🚀 Cómo correrlo localmente (Para Desarrollo)

1. **Crear y activar el entorno virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar variables de entorno:**
   Ya existe un archivo `.env` configurado. Asegúrate de que contenga:
   ```env
   DB_PATH=./data/dropreport.db
   SECRET_KEY=tu-clave-secreta-muy-segura
   ADMIN_USER=admin
   ADMIN_PASS=dropi2024
   ```

4. **Arrancar el servidor:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Entra a `http://localhost:8000` en tu navegador e inicia sesión con las credenciales del `.env`.

---

## 💾 Persistencia de Datos y Migración (De Mac a Raspberry Pi)

**Toda la información del sistema** (reportes subidos, notas de llamadas, y usuarios) se guarda en un solo lugar: el archivo `dropreport.db` dentro de la carpeta `data/`.

### ¿Cómo migrar los datos a la Raspberry Pi sin perder nada?

1. En tu Mac, ve a la carpeta del proyecto y comprime la carpeta `data/`.
2. Pásala a tu Raspberry Pi (por USB, SCP, etc.) y colócala dentro de la carpeta del proyecto en la Raspberry Pi, asegurándote de que la ruta sea `drop-report/data/dropreport.db`.
3. Cuando levantes Docker en la Raspberry Pi, el sistema reconocerá automáticamente este archivo y arrancarás con todo tu historial intacto.

---

## 🐳 Despliegue en Raspberry Pi (Producción)

Dado que la Raspberry Pi usa arquitectura ARM, Docker es la mejor manera de correr el proyecto de forma aislada y segura.

1. **(Opcional pero recomendado) Construir la imagen desde tu Mac para ARM:**
   Si tu Mac tiene procesador M1/M2/M3 (que también es ARM), puedes construir la imagen y pasarla. Sin embargo, lo más fácil es clonar el repositorio directo en la Raspberry Pi.

2. **En la Raspberry Pi:**
   ```bash
   # Entra a la carpeta del proyecto
   cd drop-report

   # Edita el archivo .env con contraseñas seguras para producción
   nano .env
   ```

3. **Levantar el contenedor:**
   ```bash
   docker-compose up -d --build
   ```

4. **Acceder:**
   Abre un navegador en cualquier dispositivo conectado a tu red local (o a través de internet si abriste puertos/usaste un túnel) y ve a la dirección IP de tu Raspberry Pi:
   `http://<IP_DE_LA_RASPBERRY_PI>:8000`

### Mantenimiento en Docker
- Ver los logs del servidor: `docker-compose logs -f`
- Detener el servidor: `docker-compose down`
- Reiniciar el servidor: `docker-compose restart`

---

## 📄 Notas de uso de la App

- **Subida de Archivos:** Usa SIEMPRE el reporte de Dropi llamado **"Órdenes con Productos"** (`ordenes_productos_...xlsx`). El reporte normal de "Órdenes" no sirve porque no trae las columnas de Producto y Cantidad.
- **Actualización Inteligente:** Puedes subir el mismo archivo varias veces o subir archivos más recientes. El sistema usa los IDs de Dropi, por lo que nunca duplicará pedidos; solo actualizará el estado (ej: de Pendiente a Entregado) de los que ya existan.
- **Gestión de Usuarios:** Inicia sesión con la cuenta de administrador para acceder a la pestaña oculta de "Usuarios" y crear credenciales para tus agentes de Call Center.
