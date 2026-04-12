# LabFlow — Sistema de Gestión de Reactivos para Citometría de Flujo

Aplicación web para gestionar inventario de reactivos y anticuerpos, con calendario de pacientes y predicción de consumo.

---

## Despliegue en Railway (recomendado — gratis)

### Requisitos previos
- Cuenta de GitHub (ya tienes una ✓)
- Cuenta de Railway: créala en https://railway.app con tu cuenta de GitHub

### Pasos

**1. Sube el código a GitHub**

Ve a https://github.com/new y crea un repositorio nuevo llamado `labflow` (privado o público, lo que prefieras).

Luego, en tu computadora, abre una terminal y ejecuta:

```bash
# Solo la primera vez: instala git si no lo tienes
# Windows: https://git-scm.com/download/win
# Mac: ya viene instalado

cd labflow          # entra a la carpeta del proyecto
git init
git add .
git commit -m "Initial commit - LabFlow"
git remote add origin https://github.com/TU_USUARIO/labflow.git
git branch -M main
git push -u origin main
```

**2. Despliega en Railway**

1. Ve a https://railway.app
2. Haz clic en "New Project"
3. Selecciona "Deploy from GitHub repo"
4. Elige el repositorio `labflow`
5. Railway detecta automáticamente que es Python y lo despliega

**3. Configura la base de datos persistente**

Por defecto SQLite guarda en el mismo servidor (se borra si Railway reinicia el contenedor). Para datos permanentes:

En tu proyecto de Railway:
1. Haz clic en "+ New" → "Database" → "Add PostgreSQL" (Railway lo conecta automáticamente)
2. Railway agrega la variable `DATABASE_URL` automáticamente

**Nota**: La app ya detecta `DATABASE_URL` en el ambiente. Si no hay PostgreSQL, usa SQLite local (funciona bien para empezar).

**4. Tu URL**

Railway te da una URL como `https://labflow-production-xxxx.up.railway.app`
Esa es tu aplicación, accesible desde cualquier dispositivo con internet.

---

## Despliegue en Render (alternativa gratuita)

1. Ve a https://render.com y crea cuenta con GitHub
2. "New" → "Web Service"
3. Conecta el repositorio `labflow`
4. Configuración:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Clic en "Create Web Service"

---

## Desarrollo local (para probar antes de subir)

```bash
pip install -r requirements.txt
python app.py
# Abre http://localhost:5000
```

---

## Estructura del proyecto

```
labflow/
├── app.py              # Backend Flask + API REST
├── requirements.txt    # Dependencias Python
├── Procfile            # Instrucciones para el servidor
├── runtime.txt         # Versión de Python
├── templates/
│   └── index.html      # Frontend completo (HTML + CSS + JS)
└── labflow.db          # Base de datos SQLite (se crea automáticamente)
```

---

## Funcionalidades

- **Dashboard**: Vista general con estado de inventario y alertas críticas
- **Calendario**: Asigna pacientes por día (clic en cualquier día)
- **Predicción**: Consumo proyectado a 30 días con días estimados de agotamiento
- **Reactivos base**: FACS Lysing, FIX & PERM, PBS — configurables
- **Anticuerpos**: Nombre, volumen total, µL por tubo, tipo de tinción (extracelular/intracelular/nuclear)
- **Paneles/Tubos**: Define cuántos tubos por paciente y de qué tipo
