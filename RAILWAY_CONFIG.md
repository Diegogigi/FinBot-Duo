# 🚀 Configuración de Railway para FinBot Duo

## Variables de Entorno Requeridas

Para que el bot funcione correctamente en Railway, debes configurar estas variables de entorno:

### 1. **BOT_TOKEN**
```
BOT_TOKEN=7193615704:AAET5zBhy7KtkyvlEvno58rTXQHswz88X-g
```

### 2. **GOOGLE_SHEETS_NAME**
```
GOOGLE_SHEETS_NAME=FinanzasFamiliares
```

### 3. **TIMEZONE**
```
TIMEZONE=America/Santiago
```

### 4. **GOOGLE_CREDENTIALS_JSON** (CRÍTICO)
```
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":"tu-proyecto","private_key_id":"...","private_key":"...","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}
```

## 📋 Pasos para Configurar en Railway

### 1. Accede a tu proyecto en Railway
- Ve a [railway.app](https://railway.app)
- Selecciona tu proyecto del bot

### 2. Configurar Variables de Entorno
- Haz clic en tu servicio
- Ve a la pestaña **"Variables"**
- Agrega cada variable una por una:

#### **BOT_TOKEN**
- Nombre: `BOT_TOKEN`
- Valor: `7193615704:AAET5zBhy7KtkyvlEvno58rTXQHswz88X-g`

#### **GOOGLE_SHEETS_NAME** 
- Nombre: `GOOGLE_SHEETS_NAME`
- Valor: `FinanzasFamiliares`

#### **TIMEZONE**
- Nombre: `TIMEZONE` 
- Valor: `America/Santiago`

#### **GOOGLE_CREDENTIALS_JSON** (MUY IMPORTANTE)
- Nombre: `GOOGLE_CREDENTIALS_JSON`
- Valor: El contenido completo de tu archivo `credentials.json` (todo en una línea)

### 3. Formato del credentials.json

Tu archivo `credentials.json` debe verse así:
```json
{
  "type": "service_account",
  "project_id": "tu-proyecto-id",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "finanzas-bot@tu-proyecto.iam.gserviceaccount.com",
  "client_id": "123456789...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/finanzas-bot%40tu-proyecto.iam.gserviceaccount.com"
}
```

### 4. Copiar credentials.json como Variable de Entorno

**Método 1: Manual**
1. Abre tu archivo `credentials.json`
2. Copia todo el contenido (debe estar en una sola línea)
3. Pégalo como valor de `GOOGLE_CREDENTIALS_JSON`

**Método 2: Con herramientas**
```bash
# En tu computadora local, convierte el JSON a una línea
cat credentials.json | tr -d '\n' | tr -d ' '
```

### 5. Redeploy

Después de agregar las variables:
1. Haz un commit y push a tu repositorio
2. O fuerza un redeploy en Railway
3. Ve a los logs para verificar la conexión

## 🔍 Verificar la Configuración

### Logs Exitosos
Si todo está bien configurado, deberías ver en los logs:
```
✅ Conexion exitosa con Google Sheets - Sistema multihojas configurado
🤖 FinBot Duo Avanzado iniciado correctamente
```

### Logs de Error
Si hay problemas, verás:
```
❌ Error al conectar con Google Sheets: [detalles del error]
```

## 🚨 Solución de Problemas Comunes

### Error: "Name or service not known"
- Problema: No hay conexión a internet o credenciales inválidas
- Solución: Verificar que `GOOGLE_CREDENTIALS_JSON` esté bien configurado

### Error: "Insufficient Permission"
- Problema: La service account no tiene permisos
- Solución: Compartir la hoja de Google Sheets con el email de la service account

### Error: "Spreadsheet not found"
- Problema: El nombre de la hoja no coincide
- Solución: Verificar que `GOOGLE_SHEETS_NAME=FinanzasFamiliares` (exacto)

### Bot funciona pero no guarda datos
- Problema: Faltan permisos de escritura
- Solución: Dar permisos de "Editor" a la service account en Google Sheets

## 📱 Compartir Google Sheets

1. Abre tu hoja "FinanzasFamiliares" en Google Sheets
2. Haz clic en "Compartir" (esquina superior derecha)
3. Agrega el email de la service account (está en `client_email` del JSON)
4. Dale permisos de "Editor"
5. Haz clic en "Enviar"

## ✅ Verificación Final

Para verificar que todo funciona:
1. Usa el bot en Telegram
2. Registra una transacción de prueba
3. Ve a tu Google Sheets
4. Verifica que aparezca la transacción

¡Ahora tu bot debería funcionar perfectamente en Railway! 🎉 