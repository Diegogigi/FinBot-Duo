# 🏦 Bot de Finanzas Familiares

## 📝 Descripción
Chatbot de Telegram desarrollado en Python para gestionar las finanzas familiares. Permite registrar ingresos, gastos y deudas de múltiples usuarios, consolidando toda la información en Google Sheets con recordatorios automáticos y análisis financiero.

## ✨ Funcionalidades

### 🔥 Principales
- ✅ **Registro de ingresos, gastos y deudas** con categorización
- ✅ **Soporte multiusuario** para parejas/familias
- ✅ **Integración con Google Sheets** para almacenamiento
- ✅ **Recordatorios automáticos** de fechas de pago
- ✅ **Plan de ahorro inteligente** con análisis de tasa de ahorro
- ✅ **Historial detallado** de transacciones
- ✅ **Resúmenes financieros** por usuario y familiares

### 📊 Análisis Financiero
- Plan de ahorro mensual automático
- Cálculo de tasa de ahorro
- Análisis de gastos por categorías
- Balance financiero por usuario
- Recordatorios de deudas próximas a vencer

### 🔔 Recordatorios
- Configuración de días de pago personalizados
- Alertas de deudas próximas al vencimiento
- Notificaciones automáticas de cobro de sueldo

## 🛠️ Tecnologías Utilizadas

| Componente | Herramienta |
|------------|-------------|
| **Lenguaje** | Python 3.8+ |
| **Bot Framework** | python-telegram-bot |
| **Base de Datos** | Google Sheets API |
| **Autenticación** | OAuth2Client |
| **Scheduler** | Schedule |
| **Variables de Entorno** | python-dotenv |
| **Zona Horaria** | pytz |

## 📁 Estructura del Proyecto

```
finanzas_bot/
├── 📄 bot.py                          # Bot principal (versión básica)
├── 📄 config.py                       # Configuraciones y constantes
├── 📄 requirements.txt                # Dependencias Python
├── 📄 Procfile                        # Configuración para despliegue
├── 📄 FinanzasFamiliares_Plantilla.csv # Plantilla para Google Sheets
├── 📄 .env.example                    # Ejemplo de variables de entorno
├── 📄 credentials.json                # Credenciales Google API (no incluido)
└── 📄 README.md                       # Este archivo
```

## ⚙️ Configuración e Instalación

### 1️⃣ Requisitos Previos
- Python 3.8 o superior
- Cuenta de Google (para Google Sheets API)
- Token de bot de Telegram (BotFather)

### 2️⃣ Configuración de Google Sheets
1. Crear una hoja de cálculo en Google Drive llamada "FinanzasFamiliares"
2. Activar Google Sheets API y Google Drive API en Google Cloud Console
3. Crear credenciales de cuenta de servicio
4. Descargar `credentials.json` y colocarlo en la raíz del proyecto
5. Compartir la hoja de Google Sheets con el email de la cuenta de servicio

### 3️⃣ Configuración del Bot de Telegram
1. Crear bot con [@BotFather](https://t.me/BotFather)
2. Obtener el token del bot
3. Configurar las variables de entorno

### 4️⃣ Instalación Local

```bash
# Clonar o descargar el proyecto
cd finanzas_bot

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores

# Importar la plantilla a Google Sheets (opcional)
# Usa FinanzasFamiliares_Plantilla.csv como referencia

# Ejecutar el bot
python bot.py
```

### 5️⃣ Variables de Entorno (.env)

```ini
# Token del bot de Telegram
BOT_TOKEN=TU_TOKEN_DE_BOTFATHER

# Nombre de la hoja de Google Sheets
GOOGLE_SHEETS_NAME=FinanzasFamiliares

# Zona horaria para recordatorios
TIMEZONE=America/Santiago
```

## 🚀 Despliegue en la Nube

### Railway / Render / Heroku

1. **Subir el proyecto** a GitHub (sin `credentials.json` ni `.env`)

2. **Conectar** el repositorio a tu plataforma de despliegue

3. **Configurar variables de entorno** en la plataforma:
   - `BOT_TOKEN`
   - `GOOGLE_SHEETS_NAME`
   - `TIMEZONE`

4. **Subir `credentials.json`** usando el sistema de archivos de la plataforma o variables de entorno

5. **Deploy** automático con `Procfile`

## 🎮 Uso del Bot

### Comandos Disponibles
- `/start` - Iniciar el bot y mostrar menú principal
- `/help` - Mostrar ayuda y comandos
- `/cancel` - Cancelar operación actual

### Menú Principal
```
💰 Registrar Ingreso    🛒 Registrar Gasto
💳 Registrar Deuda      📊 Ver Plan de Ahorro
📜 Ver Historial        ⚙️ Configuración  
📈 Generar Resumen      🔔 Recordatorios
```

### Flujo de Registro
1. **Seleccionar** tipo de transacción
2. **Ingresar** monto (solo números)
3. **Elegir** categoría predefinida
4. **Añadir** descripción opcional
5. **Configurar** fecha de vencimiento (solo deudas)
6. **Confirmar** registro

### Categorías Disponibles

**Ingresos:**
- 💼 Sueldo, 💰 Freelance, 🎁 Bono, 📈 Inversiones, 🏠 Arriendo, 🔄 Otro

**Gastos:**
- 🛒 Supermercado, 🏠 Arriendo, 🚗 Transporte, ⚡ Servicios, 🍕 Comida, 👕 Ropa, 🎮 Entretenimiento, 🔄 Otro

**Deudas:**
- 💳 Tarjeta de Crédito, 🏦 Préstamo Bancario, 🏠 Hipoteca, 🚗 Crédito Automotriz, 👥 Préstamo Personal, 🔄 Otro

## 📊 Estructura de Datos (Google Sheets)

| Columna | Descripción | Ejemplo |
|---------|-------------|---------|
| **Fecha** | Timestamp del registro | 2024-01-15 10:30 |
| **Usuario** | Nombre del usuario | Usuario1 |
| **Tipo** | Tipo de transacción | Ingreso/Gasto/Deuda |
| **Monto** | Cantidad en CLP | 150000 |
| **Categoria** | Categoría seleccionada | Sueldo |
| **Descripcion** | Descripción opcional | Salario mensual |
| **Fecha_Vencimiento** | Solo para deudas | 15/02/2024 |
| **Estado_Pago** | Estado del pago | Completado/Pendiente |

## 🔐 Seguridad y Buenas Prácticas

### ✅ Recomendaciones
- Mantener `credentials.json` fuera de repositorios públicos
- Usar cuentas de Google separadas para el proyecto
- Configurar backups periódicos de Google Sheets
- Restringir permisos de la hoja solo a usuarios necesarios
- Monitorear logs del bot regularmente

### 🚫 Nunca Hagas
- Subir credenciales a repositorios públicos
- Compartir tokens del bot
- Dar acceso de edición innecesario a la hoja
- Ignorar errores de conexión a Google Sheets

## 🐛 Solución de Problemas

### Problemas Comunes

**Error de conexión a Google Sheets:**
```
Error al conectar con Google Sheets: [Errno -2] Name or service not known
```
- Verificar conexión a internet
- Validar `credentials.json`
- Comprobar permisos de la hoja

**Bot no responde:**
- Verificar `BOT_TOKEN`
- Comprobar que el bot esté ejecutándose
- Revisar logs para errores

**Datos no se guardan:**
- Verificar permisos de escritura en Google Sheets
- Comprobar nombre de la hoja en `.env`
- Validar formato de datos

## 🔄 Actualizaciones Futuras

### 📈 Características Planificadas
- [ ] Gráficos automáticos con matplotlib/plotly
- [ ] Exportación de reportes en PDF
- [ ] Integración con bancos via API
- [ ] Sistema de presupuestos mensuales
- [ ] Alertas por WhatsApp
- [ ] Dashboard web complementario
- [ ] Análisis predictivo de gastos
- [ ] Modo familiar con roles y permisos

### 🎯 Roadmap 2024
- **Q1:** Gráficos y visualizaciones
- **Q2:** Integración bancaria
- **Q3:** Dashboard web
- **Q4:** Análisis predictivo

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Si quieres mejorar el bot:

1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📜 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para más detalles.

## 📞 Soporte

¿Necesitas ayuda? 

- 📧 **Email:** tu-email@ejemplo.com
- 💬 **Telegram:** @tu_usuario
- 🐛 **Issues:** GitHub Issues
- 📖 **Wiki:** GitHub Wiki

---

**¡Construido con ❤️ para familias que quieren tomar control de sus finanzas!**

### 🏷️ Tags
`python` `telegram-bot` `google-sheets` `finanzas` `familia` `ahorro` `gastos` `recordatorios` `analytics` 