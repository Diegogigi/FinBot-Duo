import pytz

# Configuración directa para pruebas
BOT_TOKEN = "7193615704:AAET5zBhy7KtkyvlEvno58rTXQHswz88X-g"
GOOGLE_SHEETS_NAME = "FinanzasFamiliares"
TIMEZONE = pytz.timezone("America/Santiago")

# Estados de conversación
(CHOOSING, TYPING_AMOUNT, TYPING_CATEGORY, TYPING_DESCRIPTION, 
 TYPING_DUE_DATE, SELECTING_USER, SETTING_PAYDAY, CONFIRMING_SALARY) = range(8)

# Configuración de Google Sheets
GOOGLE_SHEETS_SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

SHEET_HEADERS = [
    'Fecha', 'Usuario', 'Tipo', 'Monto', 
    'Categoria', 'Descripcion', 'Fecha_Vencimiento', 'Estado_Pago'
]

# Categorías por tipo
CATEGORIES = {
    'ingreso': [
        '💼 Sueldo', '💰 Freelance', '🎁 Bono', 
        '📈 Inversiones', '🏠 Arriendo', '🔄 Otro'
    ],
    'gasto': [
        '🛒 Supermercado', '🏠 Arriendo', '🚗 Transporte', 
        '⚡ Servicios', '🍕 Comida', '👕 Ropa', 
        '🎮 Entretenimiento', '🔄 Otro'
    ],
    'deuda': [
        '💳 Tarjeta de Crédito', '🏦 Préstamo Bancario', 
        '🏠 Hipoteca', '🚗 Crédito Automotriz', 
        '👥 Préstamo Personal', '🔄 Otro'
    ]
}

# Mensajes del bot
WELCOME_MESSAGE = """
¡Hola {name}! 👋

Soy tu bot de finanzas familiares 🏦. Te ayudo a:

✅ Registrar ingresos, gastos y deudas
✅ Mantener un historial familiar
✅ Configurar recordatorios de pagos
✅ Generar resúmenes y planes de ahorro

¿Qué deseas hacer hoy?
"""

MAIN_MENU = [
    ['💰 Registrar Ingreso', '🛒 Registrar Gasto'],
    ['💳 Registrar Deuda', '📊 Ver Plan de Ahorro'],
    ['📜 Ver Historial', '⚙️ Configuración'],
    ['📈 Generar Resumen', '🔔 Recordatorios']
] 