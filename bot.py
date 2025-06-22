import logging
import os
import datetime
import pytz
import gspread
import schedule
import time
import threading
import json
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
import numpy as np
from collections import defaultdict, Counter
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler
from dotenv import load_dotenv
from config_temp import *

# Variables de entorno cargadas desde config_temp

# Configuración de logging mejorado
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración de Google Sheets
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", GOOGLE_SHEETS_SCOPE)
    client = gspread.authorize(creds)
    spreadsheet = client.open(GOOGLE_SHEETS_NAME)
    
    # Hoja principal para transacciones
    sheet = spreadsheet.sheet1
    
    # Crear o acceder a hojas adicionales
    try:
        sheet_goals = spreadsheet.worksheet("Metas_Ahorro")
    except gspread.WorksheetNotFound:
        sheet_goals = spreadsheet.add_worksheet("Metas_Ahorro", 1000, 10)
        
    try:
        sheet_budgets = spreadsheet.worksheet("Presupuestos")
    except gspread.WorksheetNotFound:
        sheet_budgets = spreadsheet.add_worksheet("Presupuestos", 1000, 6)
        
    try:
        sheet_users = spreadsheet.worksheet("Usuarios")
    except gspread.WorksheetNotFound:
        sheet_users = spreadsheet.add_worksheet("Usuarios", 1000, 8)
        
    try:
        sheet_categories = spreadsheet.worksheet("Categorias_Personalizadas")
    except gspread.WorksheetNotFound:
        sheet_categories = spreadsheet.add_worksheet("Categorias_Personalizadas", 1000, 4)
        
    try:
        sheet_paydays = spreadsheet.worksheet("Fechas_Pago")
    except gspread.WorksheetNotFound:
        sheet_paydays = spreadsheet.add_worksheet("Fechas_Pago", 1000, 6)
        
    try:
        sheet_family_groups = spreadsheet.worksheet("Grupos_Familiares")
    except gspread.WorksheetNotFound:
        sheet_family_groups = spreadsheet.add_worksheet("Grupos_Familiares", 1000, 8)
    
    logger.info("Conexion exitosa con Google Sheets - Sistema multihojas configurado")
except Exception as e:
    logger.error(f"Error al conectar con Google Sheets: {e}")
    sheet = None
    sheet_goals = None
    sheet_budgets = None
    sheet_users = None
    sheet_categories = None
    sheet_paydays = None
    sheet_family_groups = None

# Token del bot ya está definido en config_temp
if not BOT_TOKEN:
    logger.error("BOT_TOKEN no configurado")
    exit(1)

# Zona horaria
TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "America/Santiago"))

# Estados de la conversación ampliados
(CHOOSING, TYPING_AMOUNT, TYPING_CATEGORY, TYPING_DESCRIPTION, 
 TYPING_DUE_DATE, SELECTING_USER, SETTING_PAYDAY, CONFIRMING_SALARY,
 SETTING_BUDGET, SETTING_GOAL, TYPING_GOAL_AMOUNT, TYPING_GOAL_DATE,
 SELECTING_ANALYSIS, CONFIRMING_DELETE, TYPING_CUSTOM_CATEGORY,
 SETTING_PAYDAY_DATE, TYPING_PAYDAY_DAY, TYPING_PAYDAY_MONTH,
 REGISTERING_USER, TYPING_USERNAME, CHOOSING_REGISTRATION_TYPE,
 TYPING_INVITATION_CODE, CREATING_FAMILY_GROUP, TYPING_GROUP_NAME) = range(24)

# Datos de usuarios ampliados
user_data_store = {}

def get_reply_method(update_or_query):
    """Función auxiliar para obtener el método de respuesta correcto"""
    if hasattr(update_or_query, 'message'):
        # Es un update normal
        return update_or_query.message.reply_text
    else:
        # Es un query de callback
        return update_or_query.edit_message_text

class AdvancedFinanceBotManager:
    def __init__(self):
        self.users = {}
        self.paydays = {}  # {user_id: day_of_month}
        self.payday_dates = {}  # {user_id: {'day': X, 'month': Y, 'next_payday': date}}
        self.budgets = {}  # {user_id: {category: amount}}
        self.goals = {}    # {user_id: [{name, amount, target_date, saved}]}
        self.notifications = {}  # {user_id: [notification_settings]}
        self.custom_categories = {}  # {user_id: {type: [categories]}}
        self.family_groups = {}  # {group_id: {name, code, creator, members, settings}}
        self.user_groups = {}  # {user_id: group_id}
        
        # Cargar datos desde Google Sheets al inicializar
        self.load_all_data()
        
    def register_user(self, user_id, username):
        """Registra un nuevo usuario con perfil completo"""
        if user_id not in self.users:
            self.users[user_id] = {
                'username': username,
                'registered_date': datetime.datetime.now(TIMEZONE),
                'payday': None,
                'payday_date': None,
                'monthly_income': 0,
                'last_activity': datetime.datetime.now(TIMEZONE),
                'preferences': {
                    'currency': 'CLP',
                    'notifications': True,
                    'language': 'es',
                    'payday_reminders': True,
                    'reminder_days_before': 3
                }
            }
            logger.info(f"Nuevo usuario registrado: {username} (ID: {user_id})")
            self.save_user_data(user_id)
            
    def save_user_data(self, user_id):
        """Guarda los datos del usuario en Google Sheets"""
        if not sheet_users or user_id not in self.users:
            return False
            
        try:
            user_info = self.users[user_id]
            now = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
            registered = user_info['registered_date'].strftime("%Y-%m-%d") if isinstance(user_info['registered_date'], datetime.datetime) else str(user_info['registered_date'])
            last_activity = user_info['last_activity'].strftime("%Y-%m-%d %H:%M") if isinstance(user_info['last_activity'], datetime.datetime) else str(user_info['last_activity'])
            
            # Buscar si el usuario ya existe
            records = sheet_users.get_all_records()
            existing_row = None
            for i, record in enumerate(records, 2):  # Empezar desde fila 2
                if str(record.get('Usuario_ID')) == str(user_id):
                    existing_row = i
                    break
            
            row_data = [
                str(user_id),
                user_info['username'],
                registered,
                last_activity,
                str(user_info.get('payday', '')),
                str(user_info.get('payday_date', '')),
                str(user_info.get('monthly_income', 0)),
                str(user_info.get('preferences', {}))
            ]
            
            if existing_row:
                # Actualizar fila existente
                for col, value in enumerate(row_data, 1):
                    sheet_users.update_cell(existing_row, col, value)
            else:
                # Agregar nueva fila
                sheet_users.append_row(row_data)
            
            return True
        except Exception as e:
            logger.error(f"Error guardando datos de usuario: {e}")
            return False
    
    def load_all_data(self):
        """Carga todos los datos desde Google Sheets"""
        self.load_users_data()
        self.load_goals_data()
        self.load_budgets_data()
        self.load_categories_data()
        self.load_paydays_data()
        self.load_family_groups_data()
    
    def load_users_data(self):
        """Carga datos de usuarios desde Google Sheets"""
        if not sheet_users:
            return
            
        try:
            records = sheet_users.get_all_records()
            for record in records:
                user_id = int(record.get('Usuario_ID', 0))
                if user_id > 0:
                    try:
                        registered_date = datetime.datetime.strptime(record.get('Fecha_Registro', ''), "%Y-%m-%d")
                    except:
                        registered_date = datetime.datetime.now(TIMEZONE)
                    
                    try:
                        last_activity = datetime.datetime.strptime(record.get('Ultima_Actividad', ''), "%Y-%m-%d %H:%M")
                    except:
                        last_activity = datetime.datetime.now(TIMEZONE)
                    
                    self.users[user_id] = {
                        'username': record.get('Usuario_Nombre', f'Usuario{user_id}'),
                        'registered_date': registered_date,
                        'payday': record.get('Dia_Pago', ''),
                        'payday_date': record.get('Fecha_Pago_Completa', ''),
                        'monthly_income': float(record.get('Ingreso_Mensual', 0) or 0),
                        'last_activity': last_activity,
                        'preferences': {
                            'currency': 'CLP',
                            'notifications': True,
                            'language': 'es',
                            'payday_reminders': True,
                            'reminder_days_before': 3
                        }
                    }
            logger.info(f"Cargados {len(self.users)} usuarios desde Google Sheets")
        except Exception as e:
            logger.error(f"Error cargando usuarios: {e}")
    
    def save_goal(self, user_id, goal):
        """Guarda una meta de ahorro en Google Sheets"""
        if not sheet_goals:
            return False
            
        try:
            username = self.users.get(user_id, {}).get('username', f'Usuario{user_id}')
            now = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
            
            row_data = [
                str(user_id),
                username,
                goal['name'],
                str(goal['amount']),
                str(goal['saved']),
                goal['target_date'],
                now,
                'Activa'
            ]
            
            sheet_goals.append_row(row_data)
            return True
        except Exception as e:
            logger.error(f"Error guardando meta: {e}")
            return False
    
    def load_goals_data(self):
        """Carga metas de ahorro desde Google Sheets"""
        if not sheet_goals:
            return
            
        try:
            records = sheet_goals.get_all_records()
            for record in records:
                user_id = int(record.get('Usuario_ID', 0))
                if user_id > 0:
                    if user_id not in self.goals:
                        self.goals[user_id] = []
                    
                    goal = {
                        'name': record.get('Meta_Nombre', ''),
                        'amount': float(record.get('Monto_Meta', 0) or 0),
                        'saved': float(record.get('Monto_Ahorrado', 0) or 0),
                        'target_date': record.get('Fecha_Limite', ''),
                        'created_date': record.get('Fecha_Creacion', '')
                    }
                    self.goals[user_id].append(goal)
            
            total_goals = sum(len(goals) for goals in self.goals.values())
            logger.info(f"Cargadas {total_goals} metas de ahorro desde Google Sheets")
        except Exception as e:
            logger.error(f"Error cargando metas: {e}")
    
    def save_budget(self, user_id, category, amount):
        """Guarda un presupuesto en Google Sheets"""
        if not sheet_budgets:
            return False
            
        try:
            username = self.users.get(user_id, {}).get('username', f'Usuario{user_id}')
            now = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
            
            # Buscar si ya existe un presupuesto para esta categoría
            records = sheet_budgets.get_all_records()
            existing_row = None
            for i, record in enumerate(records, 2):  # Empezar desde fila 2
                if (str(record.get('Usuario_ID')) == str(user_id) and 
                    record.get('Categoria') == category):
                    existing_row = i
                    break
            
            row_data = [
                str(user_id),
                username,
                category,
                str(amount),
                now,
                'Activo'
            ]
            
            if existing_row:
                # Actualizar fila existente
                for col, value in enumerate(row_data, 1):
                    sheet_budgets.update_cell(existing_row, col, value)
            else:
                # Agregar nueva fila
                sheet_budgets.append_row(row_data)
                
            return True
        except Exception as e:
            logger.error(f"Error guardando presupuesto: {e}")
            return False
    
    def load_budgets_data(self):
        """Carga presupuestos desde Google Sheets"""
        if not sheet_budgets:
            return
            
        try:
            records = sheet_budgets.get_all_records()
            for record in records:
                user_id = int(record.get('Usuario_ID', 0))
                if user_id > 0:
                    if user_id not in self.budgets:
                        self.budgets[user_id] = {}
                    
                    category = record.get('Categoria', '')
                    amount = float(record.get('Presupuesto', 0) or 0)
                    
                    if category and amount > 0:
                        self.budgets[user_id][category] = amount
            
            total_budgets = sum(len(budgets) for budgets in self.budgets.values())
            logger.info(f"Cargados {total_budgets} presupuestos desde Google Sheets")
        except Exception as e:
            logger.error(f"Error cargando presupuestos: {e}")
    
    def save_custom_category(self, user_id, record_type, category):
        """Guarda una categoría personalizada en Google Sheets"""
        if not sheet_categories:
            return False
            
        try:
            now = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
            
            row_data = [
                str(user_id),
                record_type,
                category,
                now
            ]
            
            sheet_categories.append_row(row_data)
            return True
        except Exception as e:
            logger.error(f"Error guardando categoría personalizada: {e}")
            return False
    
    def load_categories_data(self):
        """Carga categorías personalizadas desde Google Sheets"""
        if not sheet_categories:
            return
            
        try:
            records = sheet_categories.get_all_records()
            for record in records:
                user_id = int(record.get('Usuario_ID', 0))
                if user_id > 0:
                    if user_id not in self.custom_categories:
                        self.custom_categories[user_id] = {}
                    
                    record_type = record.get('Tipo_Registro', '')
                    category = record.get('Categoria_Personalizada', '')
                    
                    if record_type and category:
                        if record_type not in self.custom_categories[user_id]:
                            self.custom_categories[user_id][record_type] = []
                        
                        if category not in self.custom_categories[user_id][record_type]:
                            self.custom_categories[user_id][record_type].append(category)
            
            total_categories = sum(sum(len(cats) for cats in user_cats.values()) for user_cats in self.custom_categories.values())
            logger.info(f"Cargadas {total_categories} categorías personalizadas desde Google Sheets")
        except Exception as e:
            logger.error(f"Error cargando categorías personalizadas: {e}")
    
    def save_payday_date(self, user_id, day, month):
        """Guarda fecha de pago en Google Sheets"""
        if not sheet_paydays:
            return False
            
        try:
            username = self.users.get(user_id, {}).get('username', f'Usuario{user_id}')
            now = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
            
            # Calcular próxima fecha
            today = datetime.datetime.now(TIMEZONE)
            current_year = today.year
            next_payday = datetime.datetime(current_year, month, day, tzinfo=TIMEZONE)
            if next_payday < today:
                next_payday = datetime.datetime(current_year + 1, month, day, tzinfo=TIMEZONE)
            
            # Buscar si ya existe
            records = sheet_paydays.get_all_records()
            existing_row = None
            for i, record in enumerate(records, 2):
                if str(record.get('Usuario_ID')) == str(user_id):
                    existing_row = i
                    break
            
            row_data = [
                str(user_id),
                username,
                str(day),
                str(month),
                next_payday.strftime("%Y-%m-%d"),
                now
            ]
            
            if existing_row:
                for col, value in enumerate(row_data, 1):
                    sheet_paydays.update_cell(existing_row, col, value)
            else:
                sheet_paydays.append_row(row_data)
                
            return True
        except Exception as e:
            logger.error(f"Error guardando fecha de pago: {e}")
            return False
    
    def load_paydays_data(self):
        """Carga fechas de pago desde Google Sheets"""
        if not sheet_paydays:
            return
            
        try:
            records = sheet_paydays.get_all_records()
            for record in records:
                user_id = int(record.get('Usuario_ID', 0))
                if user_id > 0:
                    day = int(record.get('Dia_Pago', 0) or 0)
                    month = int(record.get('Mes_Pago', 0) or 0)
                    
                    if day > 0:
                        self.paydays[user_id] = day
                    
                    if day > 0 and month > 0:
                        try:
                            next_payday_str = record.get('Proxima_Fecha', '')
                            next_payday = datetime.datetime.strptime(next_payday_str, "%Y-%m-%d")
                            next_payday = TIMEZONE.localize(next_payday)
                            
                            self.payday_dates[user_id] = {
                                'day': day,
                                'month': month,
                                'next_payday': next_payday,
                                'last_updated': datetime.datetime.now(TIMEZONE)
                            }
                        except:
                            pass
            
            logger.info(f"Cargadas {len(self.paydays)} configuraciones de días de pago desde Google Sheets")
        except Exception as e:
            logger.error(f"Error cargando fechas de pago: {e}")
            
    def set_payday(self, user_id, day):
        """Establece el día de pago para un usuario"""
        self.paydays[user_id] = day
        if user_id in self.users:
            self.users[user_id]['payday'] = day
            self.save_user_data(user_id)
            logger.info(f"Dia de pago establecido para {user_id}: dia {day}")

    def set_payday_date(self, user_id, day, month):
        """Establece la fecha completa de pago (día y mes)"""
        try:
            # Validar fecha
            test_date = datetime.datetime(2024, month, day)
            
            # Calcular próximo día de pago
            today = datetime.datetime.now(TIMEZONE)
            current_year = today.year
            
            # Intentar con el año actual
            next_payday = datetime.datetime(current_year, month, day, tzinfo=TIMEZONE)
            
            # Si ya pasó este año, usar el próximo año
            if next_payday < today:
                next_payday = datetime.datetime(current_year + 1, month, day, tzinfo=TIMEZONE)
            
            self.payday_dates[user_id] = {
                'day': day,
                'month': month,
                'next_payday': next_payday,
                'last_updated': datetime.datetime.now(TIMEZONE)
            }
            
            if user_id in self.users:
                self.users[user_id]['payday_date'] = f"{day:02d}/{month:02d}"
                self.save_user_data(user_id)
            
            # Guardar en Google Sheets
            self.save_payday_date(user_id, day, month)
            
            logger.info(f"Fecha de pago establecida para {user_id}: {day:02d}/{month:02d}")
            return True
            
        except ValueError as e:
            logger.error(f"Error al establecer fecha de pago: {e}")
            return False

    def get_next_payday(self, user_id):
        """Obtiene la próxima fecha de pago para un usuario"""
        if user_id not in self.payday_dates:
            return None
        
        payday_info = self.payday_dates[user_id]
        today = datetime.datetime.now(TIMEZONE)
        
        # Si la fecha de pago ya pasó, calcular la próxima
        if payday_info['next_payday'] < today:
            current_year = today.year
            next_payday = datetime.datetime(current_year, payday_info['month'], payday_info['day'], tzinfo=TIMEZONE)
            
            # Si ya pasó este año, usar el próximo año
            if next_payday < today:
                next_payday = datetime.datetime(current_year + 1, payday_info['month'], payday_info['day'], tzinfo=TIMEZONE)
            
            payday_info['next_payday'] = next_payday
            payday_info['last_updated'] = datetime.datetime.now(TIMEZONE)
            
            # Actualizar en Google Sheets
            self.save_payday_date(user_id, payday_info['day'], payday_info['month'])
        
        return payday_info['next_payday']

    def should_send_payday_reminder(self, user_id):
        """Determina si se debe enviar recordatorio de pago"""
        if user_id not in self.payday_dates:
            return False
        
        user_prefs = self.users.get(user_id, {}).get('preferences', {})
        if not user_prefs.get('payday_reminders', True):
            return False
        
        next_payday = self.get_next_payday(user_id)
        if not next_payday:
            return False
        
        today = datetime.datetime.now(TIMEZONE)
        days_until_payday = (next_payday - today).days
        
        reminder_days = user_prefs.get('reminder_days_before', 3)
        
        return days_until_payday <= reminder_days and days_until_payday >= 0

    def get_payday_reminder_message(self, user_id):
        """Genera mensaje de recordatorio de pago personalizado"""
        if user_id not in self.payday_dates:
            return None
        
        next_payday = self.get_next_payday(user_id)
        if not next_payday:
            return None
        
        today = datetime.datetime.now(TIMEZONE)
        days_until_payday = (next_payday - today).days
        
        username = self.users.get(user_id, {}).get('username', 'Usuario')
        
        if days_until_payday == 0:
            msg = f"🎉 **¡HOY ES TU DÍA DE PAGO!** 🎉\n\n"
            msg += f"¡Hola {username}! Hoy es tu día de pago.\n\n"
            msg += "💰 **Recuerda registrar:**\n"
            msg += "• Tu ingreso de sueldo\n"
            msg += "• Pagos de deudas pendientes\n"
            msg += "• Aportes a metas de ahorro\n\n"
            msg += "💡 **Consejo:** Registra tu ingreso lo antes posible para mantener un control preciso de tus finanzas."
            
        elif days_until_payday == 1:
            msg = f"📅 **Recordatorio de Pago - MAÑANA**\n\n"
            msg += f"¡Hola {username}! Mañana es tu día de pago.\n\n"
            msg += "⏰ **Prepara:**\n"
            msg += "• Tu ingreso de sueldo\n"
            msg += "• Lista de pagos pendientes\n"
            msg += "• Plan de ahorro del mes\n\n"
            msg += "💡 **Consejo:** Planifica tus gastos del mes basándote en tu sueldo anterior."
            
        else:
            msg = f"📅 **Recordatorio de Pago - En {days_until_payday} días**\n\n"
            msg += f"¡Hola {username}! Tu día de pago está próximo.\n\n"
            msg += "📋 **Fecha de pago:** " + next_payday.strftime("%d/%m/%Y") + "\n"
            msg += "⏰ **Días restantes:** {days_until_payday}\n\n"
            msg += "💡 **Preparación:**\n"
            msg += "• Revisa tus gastos del mes actual\n"
            msg += "• Actualiza tus metas de ahorro\n"
            msg += "• Planifica el próximo mes\n\n"
            msg += "🎯 **Meta:** Mantén un control financiero saludable."
        
        return msg

    def set_budget(self, user_id, category, amount):
        """Establece un presupuesto por categoría"""
        if user_id not in self.budgets:
            self.budgets[user_id] = {}
        self.budgets[user_id][category] = amount
        
        # Guardar en Google Sheets
        self.save_budget(user_id, category, amount)
        
        logger.info(f"Presupuesto establecido: {category} = ${amount}")

    def add_goal(self, user_id, name, amount, target_date):
        """Añade una meta de ahorro"""
        if user_id not in self.goals:
            self.goals[user_id] = []
        
        goal = {
            'name': name,
            'amount': amount,
            'target_date': target_date,
            'saved': 0,
            'created_date': datetime.datetime.now(TIMEZONE)
        }
        self.goals[user_id].append(goal)
        
        # Guardar en Google Sheets
        self.save_goal(user_id, goal)
        
        logger.info(f"Nueva meta creada para {user_id}: {name}")

    def add_custom_category(self, user_id, record_type, category):
        """Añade una categoría personalizada"""
        if user_id not in self.custom_categories:
            self.custom_categories[user_id] = {}
        if record_type not in self.custom_categories[user_id]:
            self.custom_categories[user_id][record_type] = []
        
        if category not in self.custom_categories[user_id][record_type]:
            self.custom_categories[user_id][record_type].append(category)
            
            # Guardar en Google Sheets
            self.save_custom_category(user_id, record_type, category)
            
            return True
        return False

    def get_user_categories(self, user_id, record_type):
        """Obtiene categorías disponibles para un usuario (predefinidas + personalizadas)"""
        default_categories = CATEGORIES.get(record_type, [])
        custom_categories = self.custom_categories.get(user_id, {}).get(record_type, [])
        return default_categories + custom_categories
    
    # ===== SISTEMA DE GRUPOS FAMILIARES =====
    
    def generate_invitation_code(self):
        """Genera un código de invitación único"""
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        # Verificar que el código no exista
        while self.get_group_by_invitation_code(code):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return code
    
    def create_family_group(self, creator_id, group_name):
        """Crea un nuevo grupo familiar"""
        import uuid
        group_id = str(uuid.uuid4())[:8]
        invitation_code = self.generate_invitation_code()
        
        creator_username = self.users.get(creator_id, {}).get('username', f'Usuario{creator_id}')
        
        group_data = {
            'id': group_id,
            'name': group_name,
            'invitation_code': invitation_code,
            'creator_id': creator_id,
            'creator_username': creator_username,
            'members': [creator_id],
            'member_usernames': [creator_username],
            'created_date': datetime.datetime.now(TIMEZONE),
            'status': 'Activo',
            'settings': {
                'shared_budgets': True,
                'shared_goals': True,
                'notification_all_transactions': False
            }
        }
        
        self.family_groups[group_id] = group_data
        self.user_groups[creator_id] = group_id
        
        # Guardar en Google Sheets
        self.save_family_group(group_data)
        
        logger.info(f"Grupo familiar creado: {group_name} (ID: {group_id}) por {creator_username}")
        return group_id, invitation_code
    
    def get_group_by_invitation_code(self, code):
        """Busca un grupo por código de invitación"""
        for group_id, group_data in self.family_groups.items():
            if group_data.get('invitation_code') == code:
                return group_id, group_data
        return None
    
    def join_family_group(self, user_id, invitation_code):
        """Une un usuario a un grupo familiar usando código de invitación"""
        group_info = self.get_group_by_invitation_code(invitation_code)
        if not group_info:
            return False, "Código de invitación inválido"
        
        group_id, group_data = group_info
        
        if user_id in group_data['members']:
            return False, "Ya eres miembro de este grupo"
        
        if user_id in self.user_groups:
            return False, "Ya perteneces a otro grupo familiar"
        
        username = self.users.get(user_id, {}).get('username', f'Usuario{user_id}')
        
        # Agregar usuario al grupo
        group_data['members'].append(user_id)
        group_data['member_usernames'].append(username)
        self.user_groups[user_id] = group_id
        
        # Actualizar en Google Sheets
        self.update_family_group(group_data)
        
        logger.info(f"Usuario {username} se unió al grupo {group_data['name']}")
        return True, f"Te has unido exitosamente al grupo '{group_data['name']}'"
    
    def get_user_group(self, user_id):
        """Obtiene el grupo familiar del usuario"""
        group_id = self.user_groups.get(user_id)
        if group_id and group_id in self.family_groups:
            return self.family_groups[group_id]
        return None
    
    def get_group_members(self, user_id):
        """Obtiene la lista de miembros del grupo del usuario"""
        group = self.get_user_group(user_id)
        if group:
            return group['members']
        return [user_id]  # Solo el usuario si no está en un grupo
    
    def is_user_registered(self, user_id):
        """Verifica si un usuario está completamente registrado"""
        user_info = self.users.get(user_id)
        if not user_info:
            return False
        # Verificar que tenga username personalizado (no autogenerado)
        username = user_info.get('username', '')
        return username and not username.startswith('Usuario')
    
    def save_family_group(self, group_data):
        """Guarda un grupo familiar en Google Sheets"""
        if not sheet_family_groups:
            return False
        
        try:
            members_str = ','.join(map(str, group_data['members']))
            created_date = group_data['created_date'].strftime("%Y-%m-%d %H:%M")
            settings_str = str(group_data.get('settings', {}))
            
            row_data = [
                group_data['id'],
                group_data['name'],
                group_data['invitation_code'],
                str(group_data['creator_id']),
                members_str,
                created_date,
                group_data['status'],
                settings_str
            ]
            
            sheet_family_groups.append_row(row_data)
            return True
        except Exception as e:
            logger.error(f"Error guardando grupo familiar: {e}")
            return False
    
    def update_family_group(self, group_data):
        """Actualiza un grupo familiar en Google Sheets"""
        if not sheet_family_groups:
            return False
        
        try:
            records = sheet_family_groups.get_all_records()
            existing_row = None
            
            for i, record in enumerate(records, 2):
                if record.get('Grupo_ID') == group_data['id']:
                    existing_row = i
                    break
            
            if existing_row:
                members_str = ','.join(map(str, group_data['members']))
                settings_str = str(group_data.get('settings', {}))
                
                # Actualizar columnas específicas
                sheet_family_groups.update_cell(existing_row, 5, members_str)  # Miembros
                sheet_family_groups.update_cell(existing_row, 8, settings_str)  # Configuraciones
                
            return True
        except Exception as e:
            logger.error(f"Error actualizando grupo familiar: {e}")
            return False
    
    def load_family_groups_data(self):
        """Carga grupos familiares desde Google Sheets"""
        if not sheet_family_groups:
            return
        
        try:
            records = sheet_family_groups.get_all_records()
            for record in records:
                group_id = record.get('Grupo_ID', '')
                if group_id:
                    try:
                        members_str = record.get('Miembros', '')
                        members = [int(x.strip()) for x in members_str.split(',') if x.strip().isdigit()]
                        
                        created_date_str = record.get('Fecha_Creacion', '')
                        try:
                            created_date = datetime.datetime.strptime(created_date_str, "%Y-%m-%d %H:%M")
                        except:
                            created_date = datetime.datetime.now(TIMEZONE)
                        
                        # Obtener nombres de usuarios
                        member_usernames = []
                        for member_id in members:
                            username = self.users.get(member_id, {}).get('username', f'Usuario{member_id}')
                            member_usernames.append(username)
                        
                        group_data = {
                            'id': group_id,
                            'name': record.get('Nombre_Grupo', ''),
                            'invitation_code': record.get('Codigo_Invitacion', ''),
                            'creator_id': int(record.get('Creador_ID', 0)),
                            'creator_username': self.users.get(int(record.get('Creador_ID', 0)), {}).get('username', ''),
                            'members': members,
                            'member_usernames': member_usernames,
                            'created_date': created_date,
                            'status': record.get('Estado', 'Activo'),
                            'settings': {
                                'shared_budgets': True,
                                'shared_goals': True,
                                'notification_all_transactions': False
                            }
                        }
                        
                        self.family_groups[group_id] = group_data
                        
                        # Mapear usuarios a grupos
                        for member_id in members:
                            self.user_groups[member_id] = group_id
                            
                    except Exception as e:
                        logger.error(f"Error procesando grupo {group_id}: {e}")
                        continue
            
            logger.info(f"Cargados {len(self.family_groups)} grupos familiares desde Google Sheets")
        except Exception as e:
            logger.error(f"Error cargando grupos familiares: {e}")

# Instancia global del manager mejorado
bot_manager = AdvancedFinanceBotManager()

class FinancialAnalyzer:
    """Clase para análisis financiero avanzado"""
    
    @staticmethod
    def get_monthly_summary(user_id=None):
        """Genera resumen mensual detallado"""
        if not sheet:
            return None
            
        try:
            records = sheet.get_all_records()
            current_month = datetime.datetime.now(TIMEZONE).strftime("%Y-%m")
            
            monthly_data = []
            for record in records:
                if user_id and record.get('Usuario') != bot_manager.users.get(user_id, {}).get('username'):
                    continue
                    
                date_str = record.get('Fecha', '')
                if date_str.startswith(current_month):
                    monthly_data.append(record)
            
            if not monthly_data:
                return None
                
            summary = {
                'total_income': sum(float(r.get('Monto', 0)) for r in monthly_data if r.get('Tipo') == 'Ingreso'),
                'total_expenses': sum(float(r.get('Monto', 0)) for r in monthly_data if r.get('Tipo') == 'Gasto'),
                'total_debts': sum(float(r.get('Monto', 0)) for r in monthly_data if r.get('Tipo') == 'Deuda'),
                'by_category': defaultdict(float),
                'transaction_count': len(monthly_data),
                'avg_transaction': 0
            }
            
            for record in monthly_data:
                category = record.get('Categoria', 'Sin categoría')
                amount = float(record.get('Monto', 0))
                summary['by_category'][category] += amount
            
            if monthly_data:
                summary['avg_transaction'] = sum(float(r.get('Monto', 0)) for r in monthly_data) / len(monthly_data)
            
            summary['balance'] = summary['total_income'] - summary['total_expenses'] - summary['total_debts']
            summary['savings_rate'] = (summary['balance'] / summary['total_income'] * 100) if summary['total_income'] > 0 else 0
            
            return summary
            
        except Exception as e:
            logger.error(f"Error en análisis mensual: {e}")
            return None

    @staticmethod
    def get_spending_trends(user_id=None, months=6):
        """Analiza tendencias de gasto en los últimos meses"""
        if not sheet:
            return None
            
        try:
            records = sheet.get_all_records()
            trends = defaultdict(lambda: defaultdict(float))
            
            for record in records:
                if user_id and record.get('Usuario') != bot_manager.users.get(user_id, {}).get('username'):
                    continue
                
                date_str = record.get('Fecha', '')
                if date_str:
                    try:
                        date_obj = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
                        month_key = date_obj.strftime("%Y-%m")
                        category = record.get('Categoria', 'Sin categoría')
                        amount = float(record.get('Monto', 0))
                        record_type = record.get('Tipo', '')
                        
                        if record_type == 'Gasto':
                            trends[month_key][category] += amount
                    except:
                        continue
            
            return dict(trends)
            
        except Exception as e:
            logger.error(f"Error en análisis de tendencias: {e}")
            return None

    @staticmethod
    def get_budget_analysis(user_id):
        """Analiza el cumplimiento del presupuesto"""
        if user_id not in bot_manager.budgets or not sheet:
            return None
            
        try:
            current_month = datetime.datetime.now(TIMEZONE).strftime("%Y-%m")
            records = sheet.get_all_records()
            username = bot_manager.users.get(user_id, {}).get('username')
            
            monthly_spending = defaultdict(float)
            
            for record in records:
                if (record.get('Usuario') == username and 
                    record.get('Tipo') == 'Gasto' and 
                    record.get('Fecha', '').startswith(current_month)):
                    
                    category = record.get('Categoria', 'Sin categoría')
                    amount = float(record.get('Monto', 0))
                    monthly_spending[category] += amount
            
            budget_analysis = {}
            for category, budget_amount in bot_manager.budgets[user_id].items():
                spent = monthly_spending.get(category, 0)
                percentage = (spent / budget_amount * 100) if budget_amount > 0 else 0
                remaining = budget_amount - spent
                
                budget_analysis[category] = {
                    'budget': budget_amount,
                    'spent': spent,
                    'remaining': remaining,
                    'percentage': percentage,
                    'status': 'over' if spent > budget_amount else 'warning' if percentage > 80 else 'good'
                }
            
            return budget_analysis
            
        except Exception as e:
            logger.error(f"Error en análisis de presupuesto: {e}")
            return None

# Instancia del analizador
analyzer = FinancialAnalyzer()

def ensure_sheet_headers():
    """Asegura que la hoja tenga los encabezados correctos"""
    if not sheet:
        return False
        
    try:
        headers = sheet.row_values(1)
        
        if not headers or headers != SHEET_HEADERS:
            sheet.clear()
            sheet.append_row(SHEET_HEADERS)
            logger.info("📋 Encabezados de la hoja principal actualizados")
        return True
    except Exception as e:
        logger.error(f"❌ Error al configurar encabezados: {e}")
        return False

def ensure_all_sheet_headers():
    """Asegura que todas las hojas tengan los encabezados correctos"""
    success = True
    
    # Hoja principal de transacciones
    if not ensure_sheet_headers():
        success = False
    
    # Hoja de metas de ahorro
    if sheet_goals:
        try:
            headers = sheet_goals.row_values(1)
            goals_headers = ['Usuario_ID', 'Usuario_Nombre', 'Meta_Nombre', 'Monto_Meta', 'Monto_Ahorrado', 'Fecha_Limite', 'Fecha_Creacion', 'Estado']
            if not headers or headers != goals_headers:
                sheet_goals.clear()
                sheet_goals.append_row(goals_headers)
                logger.info("📋 Encabezados de Metas de Ahorro configurados")
        except Exception as e:
            logger.error(f"❌ Error en encabezados de metas: {e}")
            success = False
    
    # Hoja de presupuestos
    if sheet_budgets:
        try:
            headers = sheet_budgets.row_values(1)
            budget_headers = ['Usuario_ID', 'Usuario_Nombre', 'Categoria', 'Presupuesto', 'Fecha_Creacion', 'Estado']
            if not headers or headers != budget_headers:
                sheet_budgets.clear()
                sheet_budgets.append_row(budget_headers)
                logger.info("📋 Encabezados de Presupuestos configurados")
        except Exception as e:
            logger.error(f"❌ Error en encabezados de presupuestos: {e}")
            success = False
    
    # Hoja de usuarios
    if sheet_users:
        try:
            headers = sheet_users.row_values(1)
            user_headers = ['Usuario_ID', 'Usuario_Nombre', 'Fecha_Registro', 'Ultima_Actividad', 'Dia_Pago', 'Fecha_Pago_Completa', 'Ingreso_Mensual', 'Configuraciones']
            if not headers or headers != user_headers:
                sheet_users.clear()
                sheet_users.append_row(user_headers)
                logger.info("📋 Encabezados de Usuarios configurados")
        except Exception as e:
            logger.error(f"❌ Error en encabezados de usuarios: {e}")
            success = False
    
    # Hoja de categorías personalizadas
    if sheet_categories:
        try:
            headers = sheet_categories.row_values(1)
            category_headers = ['Usuario_ID', 'Tipo_Registro', 'Categoria_Personalizada', 'Fecha_Creacion']
            if not headers or headers != category_headers:
                sheet_categories.clear()
                sheet_categories.append_row(category_headers)
                logger.info("📋 Encabezados de Categorías Personalizadas configurados")
        except Exception as e:
            logger.error(f"❌ Error en encabezados de categorías: {e}")
            success = False
    
    # Hoja de fechas de pago
    if sheet_paydays:
        try:
            headers = sheet_paydays.row_values(1)
            payday_headers = ['Usuario_ID', 'Usuario_Nombre', 'Dia_Pago', 'Mes_Pago', 'Proxima_Fecha', 'Ultima_Actualizacion']
            if not headers or headers != payday_headers:
                sheet_paydays.clear()
                sheet_paydays.append_row(payday_headers)
                logger.info("📋 Encabezados de Fechas de Pago configurados")
        except Exception as e:
            logger.error(f"❌ Error en encabezados de fechas de pago: {e}")
            success = False
    
    # Hoja de grupos familiares
    if sheet_family_groups:
        try:
            headers = sheet_family_groups.row_values(1)
            group_headers = ['Grupo_ID', 'Nombre_Grupo', 'Codigo_Invitacion', 'Creador_ID', 'Miembros', 'Fecha_Creacion', 'Estado', 'Configuraciones']
            if not headers or headers != group_headers:
                sheet_family_groups.clear()
                sheet_family_groups.append_row(group_headers)
                logger.info("📋 Encabezados de Grupos Familiares configurados")
        except Exception as e:
            logger.error(f"❌ Error en encabezados de grupos familiares: {e}")
            success = False
    
    return success

# Instancias globales
bot_manager = AdvancedFinanceBotManager()
analyzer = FinancialAnalyzer()

def get_user_display_name(user_id, context):
    """Obtiene el nombre de display del usuario"""
    if user_id in bot_manager.users:
        return bot_manager.users[user_id]['username']
    
    try:
        user = context.bot.get_chat(user_id)
        name = user.first_name or user.username or f"Usuario{user_id}"
        bot_manager.register_user(user_id, name)
        return name
    except Exception as e:
        logger.error(f"Error obteniendo nombre de usuario: {e}")
        return f"Usuario{user_id}"

def add_record_to_sheet(user_id, record_type, amount, category, description="", due_date="", status="Completado", context=None):
    """Añade un registro a la hoja de Google Sheets"""
    if not sheet:
        logger.error("❌ No hay conexión con Google Sheets")
        return False
        
    try:
        now = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
        username = get_user_display_name(user_id, context) if context else f"Usuario{user_id}"
        
        row = [now, username, record_type, amount, category, description, due_date, status]
        sheet.append_row(row)
        
        # Actualizar última actividad del usuario
        if user_id in bot_manager.users:
            bot_manager.users[user_id]['last_activity'] = datetime.datetime.now(TIMEZONE)
        
        logger.info(f"✅ Registro añadido: {username} - {record_type} - ${amount} - {category}")
        return True
    except Exception as e:
        logger.error(f"❌ Error al añadir registro: {e}")
        return False

def create_enhanced_main_menu():
    """Crea el menú principal mejorado"""
    return [
        ['💰 Registrar Ingreso', '🛒 Registrar Gasto'],
        ['💳 Registrar Deuda', '🎯 Metas de Ahorro'],
        ['📊 Análisis Completo', '📜 Ver Historial'],
        ['💡 Presupuestos', '📈 Tendencias'],
        ['🔔 Recordatorios', '⚙️ Configuración'],
        ['📤 Exportar Datos', '🤖 IA Financiera']
    ]

def start(update: Update, context: CallbackContext):
    """Comando /start - Detecta usuarios nuevos y los dirige al registro"""
    user = update.effective_user
    
    # Verificar si el usuario está completamente registrado
    if not bot_manager.is_user_registered(user.id):
        return start_registration(update, context)
    
    # Usuario ya registrado, mostrar menú principal
    username = bot_manager.users.get(user.id, {}).get('username', user.first_name)
    group = bot_manager.get_user_group(user.id)
    
    markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
    
    if group:
        welcome_msg = f"""
🤖 **¡Bienvenido de vuelta, {username}!** 

👨‍👩‍👧‍👦 **Grupo Familiar:** {group['name']}
👥 **Miembros:** {', '.join(group['member_usernames'])}

🎯 **Funcionalidades:**
• 📊 Análisis financiero inteligente
• 🎯 Sistema de metas de ahorro compartidas
• 💡 Presupuestos familiares
• 📈 Análisis de tendencias
• 🤖 Asistente IA financiero
• 📤 Exportación de datos

💡 **¿Qué deseas hacer hoy?**
"""
    else:
        welcome_msg = f"""
🤖 **¡Bienvenido de vuelta, {username}!** 

🎯 **Funcionalidades:**
• 📊 Análisis financiero inteligente
• 🎯 Sistema de metas de ahorro
• 💡 Presupuestos personalizados
• 📈 Análisis de tendencias
• 🤖 Asistente IA financiero
• 📤 Exportación de datos

💡 **¿Qué deseas hacer hoy?**

💭 **Tip:** ¿Quieres compartir finanzas con tu pareja? 
Ve a ⚙️ Configuración → 👥 Gestión Familiar
"""
    
    update.message.reply_text(welcome_msg, reply_markup=markup)
    return CHOOSING

def start_registration(update: Update, context: CallbackContext):
    """Inicia el proceso de registro para usuarios nuevos"""
    user = update.effective_user
    
    # Registrar usuario con datos básicos
    bot_manager.register_user(user.id, user.first_name or user.username or f"Usuario{user.id}")
    
    welcome_msg = f"""
🎉 **¡Bienvenido a FinBot Duo Avanzado!**

¡Hola! Soy tu asistente de finanzas familiares 🏦

Para comenzar, necesito que personalices tu perfil:

👤 **Paso 1:** Elige tu nombre de usuario
👨‍👩‍👧‍👦 **Paso 2:** Configura tu grupo familiar (opcional)

💡 **¿Cómo te gustaría que te llame?**

Escribe tu nombre preferido (ej: Diego, María, etc.)
"""
    
    update.message.reply_text(welcome_msg)
    return TYPING_USERNAME

def receive_username(update: Update, context: CallbackContext):
    """Recibe el nombre de usuario personalizado"""
    username = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Validar nombre de usuario
    if len(username) < 2 or len(username) > 25:
        update.message.reply_text("❌ El nombre debe tener entre 2 y 25 caracteres. Inténtalo de nuevo:")
        return TYPING_USERNAME
    
    if not username.replace(' ', '').isalpha():
        update.message.reply_text("❌ El nombre solo puede contener letras y espacios. Inténtalo de nuevo:")
        return TYPING_USERNAME
    
    # Actualizar username del usuario
    if user_id in bot_manager.users:
        bot_manager.users[user_id]['username'] = username
        bot_manager.save_user_data(user_id)
    
    # Mostrar opciones de registro
    keyboard = [
        [InlineKeyboardButton("👨‍👩‍👧‍👦 Crear Grupo Familiar", callback_data="create_family_group")],
        [InlineKeyboardButton("🔗 Unirme a Grupo Existente", callback_data="join_family_group")],
        [InlineKeyboardButton("👤 Continuar Solo", callback_data="continue_solo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = f"""
✅ **¡Perfecto, {username}!** Tu nombre ha sido guardado.

👨‍👩‍👧‍👦 **Configuración Familiar**

¿Te gustaría compartir tus finanzas con tu pareja o familia?

**Opciones:**

🆕 **Crear Grupo Familiar**
• Ideal para parejas o familias
• Genera un código de invitación
• Comparten metas y presupuestos

🔗 **Unirme a Grupo Existente**
• Si tu pareja ya creó un grupo
• Necesitas el código de invitación

👤 **Continuar Solo**
• Usar el bot individualmente
• Podrás unirte a un grupo después
"""
    
    update.message.reply_text(msg, reply_markup=reply_markup)
    return CHOOSING_REGISTRATION_TYPE

def handle_registration_callback(update: Update, context: CallbackContext):
    """Maneja los callbacks del proceso de registro"""
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "create_family_group":
        query.edit_message_text("""
👨‍👩‍👧‍👦 **Crear Grupo Familiar**

¡Excelente decisión! Crear un grupo familiar te permitirá:

• 📊 Compartir registros de ingresos y gastos
• 🎯 Tener metas de ahorro conjuntas  
• 💡 Presupuestos familiares compartidos
• 📈 Análisis financiero conjunto

**¿Cómo se llamará tu grupo?**

Ejemplos: "Familia García", "Diego y María", "Casa López"
""")
        return TYPING_GROUP_NAME
        
    elif data == "join_family_group":
        query.edit_message_text("""
🔗 **Unirse a Grupo Familiar**

Para unirte a un grupo familiar existente, necesitas el **código de invitación** que tu pareja o familiar te debe proporcionar.

Este código tiene 8 caracteres (letras y números).

**Ejemplo:** ABC12345

**Escribe el código de invitación:**
""")
        return TYPING_INVITATION_CODE
        
    elif data == "continue_solo":
        username = bot_manager.users.get(user_id, {}).get('username', 'Usuario')
        
        # Ir directamente al menú principal
        markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
        
        completion_msg = f"""
✅ **¡Registro Completado!**

¡Bienvenido {username}! Ya puedes comenzar a usar FinBot Duo Avanzado.

🎯 **Puedes empezar por:**
• 💰 Registrar tu primer ingreso
• 🎯 Crear una meta de ahorro
• 💡 Establecer presupuestos

💭 **Recuerda:** Puedes unirte a un grupo familiar más tarde desde ⚙️ Configuración → 👥 Gestión Familiar
"""
        
        query.edit_message_text(completion_msg, reply_markup=None)
        query.message.reply_text("¿Qué te gustaría hacer?", reply_markup=markup)
        return CHOOSING
    
    return CHOOSING_REGISTRATION_TYPE

def receive_group_name(update: Update, context: CallbackContext):
    """Recibe el nombre del grupo familiar y lo crea"""
    group_name = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Validar nombre del grupo
    if len(group_name) < 3 or len(group_name) > 50:
        update.message.reply_text("❌ El nombre del grupo debe tener entre 3 y 50 caracteres. Inténtalo de nuevo:")
        return TYPING_GROUP_NAME
    
    # Crear grupo familiar
    try:
        group_id, invitation_code = bot_manager.create_family_group(user_id, group_name)
        username = bot_manager.users.get(user_id, {}).get('username', 'Usuario')
        
        # Mensaje de éxito con código de invitación
        success_msg = f"""
🎉 **¡Grupo Familiar Creado Exitosamente!**

👨‍👩‍👧‍👦 **Grupo:** {group_name}
👤 **Creador:** {username}
🔗 **Código de Invitación:** `{invitation_code}`

**📋 ¿Cómo invitar a tu pareja?**

1️⃣ Comparte este código: **{invitation_code}**
2️⃣ Tu pareja debe usar el bot con /start
3️⃣ Elegir "🔗 Unirme a Grupo Existente"
4️⃣ Introducir el código de invitación

**💡 Funciones del Grupo:**
• Todos los registros se comparten automáticamente
• Metas de ahorro conjuntas
• Presupuestos familiares
• Análisis financiero conjunto

**⚠️ Importante:** Guarda este código, lo necesitarás para invitar a más miembros.
"""
        
        update.message.reply_text(success_msg)
        
        # Ir al menú principal
        markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text("¡Ya puedes comenzar a usar todas las funciones!", reply_markup=markup)
        
        return CHOOSING
        
    except Exception as e:
        logger.error(f"Error creando grupo familiar: {e}")
        update.message.reply_text("❌ Error al crear el grupo. Inténtalo de nuevo:")
        return TYPING_GROUP_NAME

def receive_invitation_code(update: Update, context: CallbackContext):
    """Recibe el código de invitación y une al usuario al grupo"""
    invitation_code = update.message.text.strip().upper()
    user_id = update.effective_user.id
    
    # Validar formato del código
    if len(invitation_code) != 8:
        update.message.reply_text("❌ El código de invitación debe tener 8 caracteres. Inténtalo de nuevo:")
        return TYPING_INVITATION_CODE
    
    # Intentar unirse al grupo
    success, message = bot_manager.join_family_group(user_id, invitation_code)
    
    if success:
        username = bot_manager.users.get(user_id, {}).get('username', 'Usuario')
        group = bot_manager.get_user_group(user_id)
        
        success_msg = f"""
🎉 **¡Te has unido exitosamente!**

👨‍👩‍👧‍👦 **Grupo:** {group['name']}
👤 **Bienvenido:** {username}
👥 **Miembros:** {', '.join(group['member_usernames'])}

**💡 Ahora puedes:**
• Ver todos los registros familiares
• Crear metas de ahorro conjuntas
• Gestionar presupuestos compartidos
• Analizar finanzas familiares

¡Comienza a registrar tus transacciones!
"""
        
        update.message.reply_text(success_msg)
        
        # Ir al menú principal
        markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text("¿Qué te gustaría hacer?", reply_markup=markup)
        
        return CHOOSING
    else:
        update.message.reply_text(f"❌ {message}\n\nInténtalo de nuevo o contacta a quien te invitó:")
        return TYPING_INVITATION_CODE

def show_spending_trends_callback(query, context):
    """Muestra análisis de tendencias de gasto (versión para callbacks)"""
    user_id = query.from_user.id
    
    try:
        trends = analyzer.get_spending_trends(user_id, months=6)
        
        if not trends:
            query.edit_message_text("📈 No hay suficientes datos para mostrar tendencias.")
            return CHOOSING
        
        msg = "📈 **Análisis de Tendencias de Gasto**\n\n"
        
        # Calcular tendencias por mes
        sorted_months = sorted(trends.keys(), reverse=True)[:6]
        
        for month in sorted_months:
            month_data = trends[month]
            total_month = sum(month_data.values())
            
            month_name = datetime.datetime.strptime(month, "%Y-%m").strftime("%B %Y")
            msg += f"📅 **{month_name}**: ${total_month:,.0f}\n"
            
            # Top 3 categorías del mes
            top_categories = sorted(month_data.items(), key=lambda x: x[1], reverse=True)[:3]
            for cat, amount in top_categories:
                msg += f"   • {cat}: ${amount:,.0f}\n"
            msg += "\n"
        
        query.edit_message_text(msg)
        
        # Mostrar análisis de tendencias
        if len(sorted_months) >= 2:
            current_month_total = sum(trends[sorted_months[0]].values())
            previous_month_total = sum(trends[sorted_months[1]].values())
            
            if current_month_total > previous_month_total:
                change = ((current_month_total - previous_month_total) / previous_month_total) * 100
                trend_msg = f"📊 **Tendencia**: Tus gastos aumentaron {change:.1f}% respecto al mes anterior."
            else:
                change = ((previous_month_total - current_month_total) / previous_month_total) * 100
                trend_msg = f"📊 **Tendencia**: Tus gastos disminuyeron {change:.1f}% respecto al mes anterior. ¡Bien!"
            
            keyboard = [
                [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.message.reply_text(trend_msg, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error en análisis de tendencias: {e}")
        query.edit_message_text("❌ Error al generar análisis de tendencias.")
    
    return CHOOSING

def show_budget_management_callback(query, context):
    """Gestión de presupuestos personalizados (versión para callbacks)"""
    user_id = query.from_user.id
    
    keyboard = [
        [InlineKeyboardButton("💡 Ver Presupuestos", callback_data="view_budgets")],
        [InlineKeyboardButton("➕ Crear Presupuesto", callback_data="create_budget")],
        [InlineKeyboardButton("📊 Análisis de Cumplimiento", callback_data="budget_analysis")],
        [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = """
💡 **Gestión de Presupuestos**

Controla tus gastos con presupuestos personalizados:

• **Ver Presupuestos**: Consulta tus presupuestos actuales
• **Crear Presupuesto**: Establece límites por categoría
• **Análisis**: Ve qué tan bien cumples tus presupuestos
"""
    
    query.edit_message_text(msg, reply_markup=reply_markup)
    return CHOOSING

def show_enhanced_reminders_callback(query, context):
    """Recordatorios mejorados con más opciones (versión para callbacks)"""
    if not sheet:
        query.edit_message_text("❌ Error: No se puede acceder a la base de datos.")
        return CHOOSING
    
    try:
        records = sheet.get_all_records()
        pending_debts = []
        upcoming_paydays = []
        
        today = datetime.datetime.now(TIMEZONE)
        user_id = query.from_user.id
        username = bot_manager.users.get(user_id, {}).get('username')
        
        # Deudas pendientes
        for record in records:
            if (record.get('Tipo') == 'Deuda' and 
                record.get('Estado_Pago') == 'Pendiente' and
                record.get('Usuario') == username):
                
                due_date_str = record.get('Fecha_Vencimiento', '')
                if due_date_str:
                    try:
                        due_date = datetime.datetime.strptime(due_date_str, "%d/%m/%Y")
                        days_until_due = (due_date - today).days
                        
                        if days_until_due <= 15:  # Mostrar deudas con hasta 15 días de anticipación
                            pending_debts.append({
                                'monto': record.get('Monto', 0),
                                'categoria': record.get('Categoria', 'N/A'),
                                'vencimiento': due_date_str,
                                'dias': days_until_due
                            })
                    except ValueError:
                        continue
        
        # Días de pago próximos - Mejorado para fechas completas
        if user_id in bot_manager.payday_dates:
            # Usar fecha completa de pago
            next_payday = bot_manager.get_next_payday(user_id)
            if next_payday:
                days_to_payday = (next_payday - today).days
                
                if days_to_payday <= 7:
                    upcoming_paydays.append({
                        'days': days_to_payday,
                        'date': next_payday.strftime("%d/%m/%Y"),
                        'type': 'complete_date'
                    })
        elif user_id in bot_manager.paydays:
            # Usar día simple de pago (compatibilidad)
            payday = bot_manager.paydays[user_id]
            current_day = today.day
            
            if current_day <= payday:
                days_to_payday = payday - current_day
            else:
                # Próximo mes
                next_month = today.replace(month=today.month+1) if today.month < 12 else today.replace(year=today.year+1, month=1)
                next_payday = next_month.replace(day=payday)
                days_to_payday = (next_payday - today).days
            
            if days_to_payday <= 7:
                upcoming_paydays.append({
                    'days': days_to_payday,
                    'date': f"día {payday}",
                    'type': 'simple_day'
                })
        
        # Generar mensaje
        msg = "🔔 **Recordatorios Inteligentes**\n\n"
        
        if pending_debts:
            msg += "💳 **Deudas Pendientes:**\n"
            for debt in sorted(pending_debts, key=lambda x: x['dias']):
                status_emoji = "🚨" if debt['dias'] <= 0 else "⚠️" if debt['dias'] <= 3 else "📅"
                status_text = "¡VENCIDA!" if debt['dias'] < 0 else f"Vence en {debt['dias']} días" if debt['dias'] > 0 else "¡Vence HOY!"
                
                msg += f"{status_emoji} {debt['categoria']}: ${debt['monto']:,}\n"
                msg += f"   📅 {status_text}\n\n"
        
        if upcoming_paydays:
            msg += "💼 **Próximo Día de Pago:**\n"
            for payday in upcoming_paydays:
                if payday['days'] == 0:
                    msg += "🎉 ¡Tu día de pago es HOY!\n"
                else:
                    if payday['type'] == 'complete_date':
                        msg += f"💰 En {payday['days']} días ({payday['date']})\n"
                    else:
                        msg += f"💰 En {payday['days']} días ({payday['date']})\n"
        
        if not pending_debts and not upcoming_paydays:
            msg += "✅ No tienes recordatorios pendientes.\n¡Todo al día!"
        
        # Consejos inteligentes
        msg += "\n💡 **Consejos:**\n"
        if pending_debts:
            overdue_count = len([d for d in pending_debts if d['dias'] <= 0])
            if overdue_count > 0:
                msg += f"⚠️ Tienes {overdue_count} deuda(s) vencida(s). ¡Atiéndelas pronto!\n"
        
        if upcoming_paydays and pending_debts:
            msg += "💡 Considera programar pagos automáticos para evitar olvidos.\n"
        
        # Información adicional sobre configuración de pago
        if user_id not in bot_manager.payday_dates and user_id not in bot_manager.paydays:
            msg += "\n📅 **Configuración de Pago:**\n"
            msg += "💡 Configura tu fecha de pago en ⚙️ Configuración para recibir recordatorios automáticos.\n"
        
        keyboard = [
            [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error en recordatorios mejorados: {e}")
        query.edit_message_text("❌ Error al obtener recordatorios.")
    
    return CHOOSING

def export_user_data_callback(query, context):
    """Exporta los datos del usuario (versión para callbacks)"""
    user_id = query.from_user.id
    
    if not sheet:
        query.edit_message_text("❌ Error: No se puede acceder a la base de datos.")
        return CHOOSING
    
    try:
        username = bot_manager.users.get(user_id, {}).get('username')
        records = sheet.get_all_records()
        
        # Filtrar registros del usuario
        user_records = [r for r in records if r.get('Usuario') == username]
        
        if not user_records:
            query.edit_message_text("📤 No tienes datos para exportar.")
            return CHOOSING
        
        # Crear resumen para exportar
        export_data = {
            'usuario': username,
            'fecha_exportacion': datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M"),
            'total_registros': len(user_records),
            'registros': user_records
        }
        
        # Generar estadísticas
        total_ingresos = sum(float(r.get('Monto', 0)) for r in user_records if r.get('Tipo') == 'Ingreso')
        total_gastos = sum(float(r.get('Monto', 0)) for r in user_records if r.get('Tipo') == 'Gasto')
        total_deudas = sum(float(r.get('Monto', 0)) for r in user_records if r.get('Tipo') == 'Deuda')
        
        msg = f"""
📤 **Exportación de Datos Completada**

👤 **Usuario**: {username}
📊 **Resumen**:
• Total de registros: {len(user_records)}
• Ingresos totales: ${total_ingresos:,.0f}
• Gastos totales: ${total_gastos:,.0f}
• Deudas totales: ${total_deudas:,.0f}
• Balance general: ${total_ingresos - total_gastos - total_deudas:,.0f}

📋 **Datos disponibles en Google Sheets**
🔗 Puedes acceder a tu hoja completa en Google Sheets para análisis detallado.

💡 **Próximamente**: Exportación en CSV y PDF
"""
        
        keyboard = [
            [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error en exportación: {e}")
        query.edit_message_text("❌ Error al exportar datos.")
    
    return CHOOSING

def show_ai_financial_assistant_callback(query, context):
    """Asistente de IA financiera con consejos personalizados (versión para callbacks)"""
    user_id = query.from_user.id
    
    try:
        # Obtener análisis del mes actual
        monthly_summary = analyzer.get_monthly_summary(user_id)
        
        if not monthly_summary:
            query.edit_message_text("🤖 Necesito más datos tuyos para darte consejos personalizados. ¡Sigue usando el bot!")
            return CHOOSING
        
        # Generar consejos de IA
        msg = "🤖 **Asistente IA Financiera**\n\n"
        msg += "📊 **Análisis de tu situación:**\n"
        
        savings_rate = monthly_summary['savings_rate']
        balance = monthly_summary['balance']
        
        # Análisis de ahorro
        if savings_rate < 5:
            msg += "🚨 **Ahorro Crítico**: Tu tasa de ahorro es muy baja. Te recomiendo:\n"
            msg += "   • Revisar gastos no esenciales\n"
            msg += "   • Establecer un presupuesto estricto\n"
            msg += "   • Considerar ingresos adicionales\n\n"
        elif savings_rate < 15:
            msg += "⚠️ **Ahorro Bajo**: Puedes mejorar tu situación:\n"
            msg += "   • Objetivo: alcanzar 15-20% de ahorro\n"
            msg += "   • Revisa las categorías de mayor gasto\n"
            msg += "   • Automatiza tus ahorros\n\n"
        elif savings_rate < 25:
            msg += "✅ **Buen Ahorro**: Estás en el camino correcto:\n"
            msg += "   • Mantén este ritmo de ahorro\n"
            msg += "   • Considera invertir tus ahorros\n"
            msg += "   • Establece metas específicas\n\n"
        else:
            msg += "🎉 **Excelente Ahorro**: ¡Felicitaciones!\n"
            msg += "   • Tu disciplina financiera es admirable\n"
            msg += "   • Considera diversificar inversiones\n"
            msg += "   • Podrías permitirte algunos gustos\n\n"
        
        # Análisis de gastos por categoría
        if monthly_summary['by_category']:
            top_category = max(monthly_summary['by_category'].items(), key=lambda x: x[1])
            msg += f"💡 **Insight**: Tu mayor gasto es en '{top_category[0]}' (${top_category[1]:,.0f})\n"
            
            if top_category[1] > monthly_summary['total_expenses'] * 0.4:
                msg += "⚠️ Esta categoría representa más del 40% de tus gastos. ¿Puedes optimizarla?\n\n"
        
        # Recomendaciones personalizadas
        msg += "🎯 **Recomendaciones Personalizadas:**\n"
        
        transaction_count = monthly_summary['transaction_count']
        if transaction_count > 30:
            msg += "• Tienes muchas transacciones. Considera consolidar compras.\n"
        elif transaction_count < 10:
            msg += "• Registra más transacciones para mejor seguimiento.\n"
        
        if balance < 0:
            msg += "• 🚨 Estás gastando más de lo que ingresas. ¡Ajusta urgente!\n"
        
        msg += "• Usa las metas de ahorro para motivarte\n"
        msg += "• Revisa tus presupuestos semanalmente\n"
        msg += "• Celebra tus logros financieros\n"
        
        # Opciones de acción
        keyboard = [
            [InlineKeyboardButton("🎯 Crear Meta de Ahorro", callback_data="create_goal")],
            [InlineKeyboardButton("💡 Configurar Presupuesto", callback_data="create_budget")],
            [InlineKeyboardButton("📊 Ver Análisis Completo", callback_data="complete_analysis")],
            [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error en IA financiera: {e}")
        query.edit_message_text("❌ Error en el asistente de IA.")
    
    return CHOOSING

# Funciones auxiliares que faltan para completar el sistema
def receive_amount(update: Update, context: CallbackContext):
    """Recibe el monto de la transacción"""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            update.message.reply_text("❌ Por favor ingresa un monto válido mayor a 0:")
            return TYPING_AMOUNT
        
        context.user_data['amount'] = amount
        action = context.user_data.get('action', 'gasto')
        
        # Seleccionar categoría
        categories = bot_manager.get_user_categories(update.effective_user.id, action)
        if not categories:
            categories = CATEGORIES.get(action, [])
        
        keyboard = [[cat] for cat in categories]
        keyboard.append(['➕ Agregar Categoría Personalizada'])
        
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text(f"📂 Selecciona una categoría para tu {action}:", reply_markup=markup)
        
        return TYPING_CATEGORY
    except ValueError:
        update.message.reply_text("❌ Por favor ingresa solo números. Ejemplo: 15000")
        return TYPING_AMOUNT

def receive_category(update: Update, context: CallbackContext):
    """Recibe la categoría seleccionada"""
    category = update.message.text.strip()
    
    if category == '➕ Agregar Categoría Personalizada':
        update.message.reply_text("✏️ Escribe el nombre de la nueva categoría:")
        return TYPING_CUSTOM_CATEGORY
    
    context.user_data['category'] = category
    update.message.reply_text("📝 Ingresa una descripción (opcional, escribe '-' para omitir):")
    return TYPING_DESCRIPTION

def receive_description(update: Update, context: CallbackContext):
    """Recibe la descripción de la transacción"""
    description = update.message.text.strip()
    if description == '-':
        description = ""
    
    context.user_data['description'] = description
    
    # Si es una deuda, pedir fecha de vencimiento
    if context.user_data.get('action') == 'deuda':
        update.message.reply_text("📅 Ingresa la fecha de vencimiento (DD/MM/YYYY) o '-' para omitir:")
        return TYPING_DUE_DATE
    
    # Finalizar transacción
    return complete_transaction(update, context)

def receive_due_date(update: Update, context: CallbackContext):
    """Recibe la fecha de vencimiento para deudas"""
    due_date = update.message.text.strip()
    if due_date == '-':
        due_date = ""
    
    context.user_data['due_date'] = due_date
    return complete_transaction(update, context)

def complete_transaction(update: Update, context: CallbackContext):
    """Completa la transacción y la guarda"""
    try:
        user_id = context.user_data['user_id']
        action = context.user_data['action']
        amount = context.user_data['amount']
        category = context.user_data['category']
        description = context.user_data.get('description', '')
        due_date = context.user_data.get('due_date', '')
        
        # Registrar la transacción
        success = add_record_to_sheet(
            user_id, action, amount, category, 
            description, due_date, "Completado", context
        )
        
        if success:
            if action == 'deuda' and due_date:
                msg = f"✅ {action.title()} registrada exitosamente!\n\n"
                msg += f"💰 Monto: ${amount:,.0f}\n"
                msg += f"🏷️ Categoría: {category}\n"
                msg += f"📝 Descripción: {description}\n"
                msg += f"📅 Vence: {due_date}"
            else:
                msg = f"✅ {action.title()} registrado exitosamente!\n\n"
                msg += f"💰 Monto: ${amount:,.0f}\n"
                msg += f"🏷️ Categoría: {category}\n"
                msg += f"📝 Descripción: {description}"
            
            update.message.reply_text(msg)
            
            # Mostrar menú principal
            markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
            update.message.reply_text("¿Qué más te gustaría hacer?", reply_markup=markup)
        else:
            update.message.reply_text("❌ Error al registrar la transacción. Inténtalo de nuevo.")
            
    except Exception as e:
        logger.error(f"Error completando transacción: {e}")
        update.message.reply_text("❌ Error al procesar la transacción.")
    
    # Limpiar datos de usuario
    context.user_data.clear()
    return CHOOSING

def receive_custom_category(update: Update, context: CallbackContext):
    """Recibe una categoría personalizada"""
    new_category = update.message.text.strip()
    
    if len(new_category) < 2:
        update.message.reply_text("❌ La categoría debe tener al menos 2 caracteres:")
        return TYPING_CUSTOM_CATEGORY
    
    user_id = update.effective_user.id
    action = context.user_data.get('action', 'gasto')
    
    # Agregar categoría personalizada
    bot_manager.add_custom_category(user_id, action, new_category)
    
    context.user_data['category'] = new_category
    update.message.reply_text(f"✅ Categoría '{new_category}' agregada!\n\n📝 Ingresa una descripción (opcional, escribe '-' para omitir):")
    return TYPING_DESCRIPTION

def receive_budget_amount(update: Update, context: CallbackContext):
    """Recibe el monto del presupuesto"""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            update.message.reply_text("❌ Por favor ingresa un monto válido mayor a 0:")
            return SETTING_BUDGET
        
        user_id = update.effective_user.id
        category = context.user_data.get('budget_category')
        
        if not category:
            update.message.reply_text("❌ Error: No se encontró la categoría. Intenta de nuevo.")
            return CHOOSING
        
        # Guardar presupuesto
        bot_manager.set_budget(user_id, category, amount)
        
        update.message.reply_text(f"✅ Presupuesto configurado!\n\n💡 Categoría: {category}\n💰 Monto: ${amount:,.0f}")
        
        # Mostrar menú principal
        markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text("¿Qué más te gustaría hacer?", reply_markup=markup)
        
        context.user_data.clear()
        return CHOOSING
        
    except ValueError:
        update.message.reply_text("❌ Por favor ingresa solo números. Ejemplo: 50000")
        return SETTING_BUDGET

def receive_goal_name(update: Update, context: CallbackContext):
    """Recibe el nombre de la meta de ahorro"""
    goal_name = update.message.text.strip()
    
    if len(goal_name) < 3:
        update.message.reply_text("❌ El nombre de la meta debe tener al menos 3 caracteres:")
        return SETTING_GOAL
    
    context.user_data['goal_name'] = goal_name
    update.message.reply_text("💰 Ahora ingresa el monto objetivo (solo números):")
    return TYPING_GOAL_AMOUNT

def receive_goal_amount(update: Update, context: CallbackContext):
    """Recibe el monto objetivo de la meta"""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            update.message.reply_text("❌ Por favor ingresa un monto válido mayor a 0:")
            return TYPING_GOAL_AMOUNT
        
        context.user_data['goal_amount'] = amount
        update.message.reply_text("📅 Ingresa la fecha límite (DD/MM/YYYY):")
        return TYPING_GOAL_DATE
        
    except ValueError:
        update.message.reply_text("❌ Por favor ingresa solo números. Ejemplo: 100000")
        return TYPING_GOAL_AMOUNT

def receive_goal_date(update: Update, context: CallbackContext):
    """Recibe la fecha límite de la meta de ahorro"""
    date_text = update.message.text.strip()
    
    try:
        target_date = datetime.datetime.strptime(date_text, "%d/%m/%Y")
        # Hacer que target_date sea timezone-aware
        target_date = TIMEZONE.localize(target_date)
        today = datetime.datetime.now(TIMEZONE)
        
        if target_date <= today:
            update.message.reply_text("❌ La fecha debe ser futura. Ingresa una fecha válida (DD/MM/YYYY):")
            return TYPING_GOAL_DATE
        
        # Crear la meta
        user_id = update.effective_user.id
        goal_name = context.user_data['goal_name']
        goal_amount = context.user_data['goal_amount']
        
        bot_manager.add_goal(user_id, goal_name, goal_amount, date_text)
        
        days_until = (target_date - today).days
        
        msg = f"""
✅ **¡Meta creada exitosamente!**

🎯 **Nombre**: {goal_name}
💰 **Monto objetivo**: ${goal_amount:,.0f}
📅 **Fecha límite**: {date_text}
⏰ **Días restantes**: {days_until}

💡 **Consejos:**
• Ahorra ${goal_amount/days_until:,.0f} diarios
• Configura recordatorios automáticos
• Celebra cada logro parcial

¡Comienza a ahorrar hoy mismo!
"""
        
        update.message.reply_text(msg)
        
        # Mostrar menú principal
        markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
        update.message.reply_text("¿Qué más te gustaría hacer?", reply_markup=markup)
        
        context.user_data.clear()
        return CHOOSING
        
    except ValueError:
        update.message.reply_text("❌ Formato de fecha incorrecto. Usa DD/MM/YYYY (ejemplo: 31/12/2024):")
        return TYPING_GOAL_DATE

def receive_payday_day(update: Update, context: CallbackContext):
    """Recibe el día del mes para el día de pago"""
    try:
        day = int(update.message.text.strip())
        if 1 <= day <= 31:
            context.user_data['payday_day'] = day
            update.message.reply_text("📅 Ahora ingresa el mes (1-12):")
            return TYPING_PAYDAY_MONTH
        else:
            update.message.reply_text("❌ Por favor ingresa un día válido (1-31):")
            return TYPING_PAYDAY_DAY
    except ValueError:
        update.message.reply_text("❌ Por favor ingresa solo números (1-31):")
        return TYPING_PAYDAY_DAY

def receive_payday_month(update: Update, context: CallbackContext):
    """Recibe el mes para el día de pago"""
    try:
        month = int(update.message.text.strip())
        if 1 <= month <= 12:
            user_id = update.effective_user.id
            day = context.user_data['payday_day']
            
            bot_manager.set_payday_date(user_id, day, month)
            
            month_names = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            
            update.message.reply_text(f"✅ Fecha de pago configurada: {day} de {month_names[month-1]}\n¡Te enviaré recordatorios automáticos!")
            
            # Mostrar menú principal
            markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
            update.message.reply_text("¿Qué más te gustaría hacer?", reply_markup=markup)
            
            context.user_data.clear()
            return CHOOSING
        else:
            update.message.reply_text("❌ Por favor ingresa un mes válido (1-12):")
            return TYPING_PAYDAY_MONTH
    except ValueError:
        update.message.reply_text("❌ Por favor ingresa solo números (1-12):")
        return TYPING_PAYDAY_MONTH

def set_payday(update: Update, context: CallbackContext):
    """Configura el día de pago del usuario"""
    try:
        day = int(update.message.text.strip())
        if 1 <= day <= 31:
            user_id = update.effective_user.id
            bot_manager.set_payday(user_id, day)
            update.message.reply_text(f"✅ Día de pago configurado: día {day} de cada mes.\n¡Te enviaré recordatorios automáticos!")
            
            # Mostrar menú principal
            markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
            update.message.reply_text("¿Qué más te gustaría hacer?", reply_markup=markup)
            
            return CHOOSING
        else:
            update.message.reply_text("❌ Por favor ingresa un día válido (1-31):")
            return SETTING_PAYDAY
    except ValueError:
        update.message.reply_text("❌ Por favor ingresa solo números (1-31):")
        return SETTING_PAYDAY

def choose_action(update: Update, context: CallbackContext):
    """Maneja la selección de acciones del menú principal mejorado"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Acciones básicas existentes
    if text == '💰 Registrar Ingreso':
        update.message.reply_text("📥 Ingresa el monto del ingreso (solo números):")
        context.user_data['action'] = 'ingreso'
        context.user_data['user_id'] = user_id
        return TYPING_AMOUNT
        
    elif text == '🛒 Registrar Gasto':
        update.message.reply_text("📤 Ingresa el monto del gasto (solo números):")
        context.user_data['action'] = 'gasto'
        context.user_data['user_id'] = user_id
        return TYPING_AMOUNT
        
    elif text == '💳 Registrar Deuda':
        update.message.reply_text("💳 Ingresa el monto de la deuda (solo números):")
        context.user_data['action'] = 'deuda'
        context.user_data['user_id'] = user_id
        return TYPING_AMOUNT
        
    # Nuevas funcionalidades avanzadas
    elif text == '🎯 Metas de Ahorro':
        return show_savings_goals_menu(update, context)
        
    elif text == '📊 Análisis Completo':
        return show_complete_analysis(update, context)
        
    elif text == '📜 Ver Historial':
        return show_enhanced_history(update, context)
        
    elif text == '💡 Presupuestos':
        return show_budget_management(update, context)
        
    elif text == '📈 Tendencias':
        return show_spending_trends(update, context)
        
    elif text == '🔔 Recordatorios':
        return show_enhanced_reminders(update, context)
        
    elif text == '⚙️ Configuración':
        return show_advanced_settings(update, context)
        
    elif text == '📤 Exportar Datos':
        return export_user_data(update, context)
        
    elif text == '🤖 IA Financiera':
        return show_ai_financial_assistant(update, context)
        
    else:
        update.message.reply_text("❌ Por favor selecciona una opción válida del menú.")
        return CHOOSING

# Funciones para las opciones del menú que faltan
def show_savings_goals_menu(update: Update, context: CallbackContext):
    """Muestra el menú de metas de ahorro"""
    keyboard = [
        [InlineKeyboardButton("🎯 Ver Mis Metas", callback_data="view_goals")],
        [InlineKeyboardButton("➕ Crear Nueva Meta", callback_data="create_goal")],
        [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text("🎯 **Metas de Ahorro**\n\n¿Qué te gustaría hacer?", reply_markup=reply_markup)
    return CHOOSING

def show_complete_analysis(update: Update, context: CallbackContext):
    """Muestra análisis financiero completo"""
    user_id = update.effective_user.id
    
    try:
        monthly_summary = analyzer.get_monthly_summary(user_id)
        
        if not monthly_summary:
            update.message.reply_text("📊 Aún no tienes suficientes datos para análisis. ¡Comienza registrando transacciones!")
            return CHOOSING
        
        msg = f"""
📊 **Análisis Financiero Completo**
📅 **{datetime.datetime.now(TIMEZONE).strftime('%B %Y')}**

💰 **Resumen General:**
• Ingresos: ${monthly_summary['total_income']:,.0f}
• Gastos: ${monthly_summary['total_expenses']:,.0f}
• Balance: ${monthly_summary['balance']:,.0f}
• Tasa de Ahorro: {monthly_summary['savings_rate']:.1f}%

📈 **Análisis por Categorías:**
"""
        
        if monthly_summary['by_category']:
            for category, amount in sorted(monthly_summary['by_category'].items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (amount / monthly_summary['total_expenses']) * 100 if monthly_summary['total_expenses'] > 0 else 0
                msg += f"• {category}: ${amount:,.0f} ({percentage:.1f}%)\n"
        
        keyboard = [
            [InlineKeyboardButton("📈 Ver Tendencias", callback_data="show_trends")],
            [InlineKeyboardButton("💡 Ver Presupuestos", callback_data="view_budgets")],
            [InlineKeyboardButton("🤖 IA Financiera", callback_data="ai_assistant")],
            [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error en análisis completo: {e}")
        update.message.reply_text("❌ Error al generar análisis.")
    
    return CHOOSING

def show_enhanced_history(update: Update, context: CallbackContext):
    """Muestra historial mejorado de transacciones"""
    user_id = update.effective_user.id
    
    if not sheet:
        update.message.reply_text("❌ Error: No se puede acceder a la base de datos.")
        return CHOOSING
    
    try:
        username = bot_manager.users.get(user_id, {}).get('username')
        records = sheet.get_all_records()
        
        # Filtrar registros del usuario (últimos 20)
        user_records = [r for r in records if r.get('Usuario') == username][-20:]
        
        if not user_records:
            update.message.reply_text("📜 No tienes transacciones registradas aún.")
            return CHOOSING
        
        msg = "📜 **Historial Reciente (últimas 20 transacciones)**\n\n"
        
        for record in reversed(user_records):  # Mostrar las más recientes primero
            fecha = record.get('Fecha', 'N/A')
            tipo = record.get('Tipo', '')
            monto = record.get('Monto', 0)
            categoria = record.get('Categoria', '')
            descripcion = record.get('Descripcion', '')
            
            # Emoji según el tipo
            emoji = "💰" if tipo == "Ingreso" else "🛒" if tipo == "Gasto" else "💳"
            
            msg += f"{emoji} **{tipo}** - ${float(monto):,.0f}\n"
            msg += f"   📂 {categoria}\n"
            if descripcion:
                msg += f"   📝 {descripcion}\n"
            msg += f"   📅 {fecha}\n\n"
            
            # Limitar longitud del mensaje
            if len(msg) > 3500:
                msg += "... (más transacciones en Google Sheets)"
                break
        
        keyboard = [
            [InlineKeyboardButton("📊 Ver Análisis", callback_data="complete_analysis")],
            [InlineKeyboardButton("📤 Exportar Datos", callback_data="export_data")],
            [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error en historial: {e}")
        update.message.reply_text("❌ Error al obtener historial.")
    
    return CHOOSING

def show_budget_management(update: Update, context: CallbackContext):
    """Muestra gestión de presupuestos"""
    keyboard = [
        [InlineKeyboardButton("💡 Ver Mis Presupuestos", callback_data="view_budgets")],
        [InlineKeyboardButton("➕ Crear Presupuesto", callback_data="create_budget")],
        [InlineKeyboardButton("📊 Análisis de Presupuesto", callback_data="budget_analysis")],
        [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text("💡 **Gestión de Presupuestos**\n\n¿Qué te gustaría hacer?", reply_markup=reply_markup)
    return CHOOSING

def show_spending_trends(update: Update, context: CallbackContext):
    """Muestra tendencias de gasto"""
    user_id = update.effective_user.id
    
    try:
        trends = analyzer.get_spending_trends(user_id, months=6)
        
        if not trends:
            update.message.reply_text("📈 No hay suficientes datos para mostrar tendencias.")
            return CHOOSING
        
        msg = "📈 **Análisis de Tendencias de Gasto**\n\n"
        
        # Calcular tendencias por mes
        sorted_months = sorted(trends.keys(), reverse=True)[:6]
        
        for month in sorted_months:
            month_data = trends[month]
            total_month = sum(month_data.values())
            
            month_name = datetime.datetime.strptime(month, "%Y-%m").strftime("%B %Y")
            msg += f"📅 **{month_name}**: ${total_month:,.0f}\n"
            
            # Top 3 categorías del mes
            top_categories = sorted(month_data.items(), key=lambda x: x[1], reverse=True)[:3]
            for cat, amount in top_categories:
                msg += f"   • {cat}: ${amount:,.0f}\n"
            msg += "\n"
        
        keyboard = [
            [InlineKeyboardButton("📊 Análisis Completo", callback_data="complete_analysis")],
            [InlineKeyboardButton("🤖 IA Financiera", callback_data="ai_assistant")],
            [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error en tendencias: {e}")
        update.message.reply_text("❌ Error al obtener tendencias.")
    
    return CHOOSING

def show_enhanced_reminders(update: Update, context: CallbackContext):
    """Muestra recordatorios mejorados"""
    keyboard = [
        [InlineKeyboardButton("🔔 Ver Recordatorios", callback_data="view_reminders")],
        [InlineKeyboardButton("📅 Configurar Pago", callback_data="set_payday_date")],
        [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text("🔔 **Sistema de Recordatorios**\n\n¿Qué te gustaría hacer?", reply_markup=reply_markup)
    return CHOOSING

def export_user_data(update: Update, context: CallbackContext):
    """Exporta datos del usuario"""
    keyboard = [
        [InlineKeyboardButton("📤 Exportar Ahora", callback_data="export_data")],
        [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text("📤 **Exportación de Datos**\n\n¿Deseas exportar tus datos financieros?", reply_markup=reply_markup)
    return CHOOSING

def show_ai_financial_assistant(update: Update, context: CallbackContext):
    """Muestra el asistente de IA financiera"""
    keyboard = [
        [InlineKeyboardButton("🤖 Obtener Consejos", callback_data="ai_assistant")],
        [InlineKeyboardButton("📊 Análisis IA", callback_data="complete_analysis")],
        [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text("🤖 **Asistente IA Financiera**\n\n¿Qué te gustaría hacer?", reply_markup=reply_markup)
    return CHOOSING

def create_category_keyboard():
    """Crea teclado para selección de categorías"""
    categories = ['Comida', 'Transporte', 'Entretenimiento', 'Servicios', 'Salud', 'Educación', 'Ropa', 'Hogar', 'Otros']
    keyboard = []
    
    for i in range(0, len(categories), 2):
        row = []
        for j in range(2):
            if i + j < len(categories):
                category = categories[i + j]
                row.append(InlineKeyboardButton(category, callback_data=f"budget_cat_{category}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🏠 Volver", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def show_user_goals(query, context):
    """Muestra las metas del usuario"""
    user_id = query.from_user.id
    goals = bot_manager.goals.get(user_id, [])
    
    if not goals:
        query.edit_message_text("🎯 No tienes metas de ahorro configuradas.\n\n¿Te gustaría crear una?")
        return CHOOSING
    
    msg = "🎯 **Tus Metas de Ahorro:**\n\n"
    
    for i, goal in enumerate(goals, 1):
        progress = (goal.get('saved', 0) / goal['amount']) * 100
        msg += f"{i}. **{goal['name']}**\n"
        msg += f"   💰 Objetivo: ${goal['amount']:,.0f}\n"
        msg += f"   💵 Ahorrado: ${goal.get('saved', 0):,.0f}\n"
        msg += f"   📊 Progreso: {progress:.1f}%\n"
        msg += f"   📅 Fecha límite: {goal['target_date']}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Crear Nueva Meta", callback_data="create_goal")],
        [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(msg, reply_markup=reply_markup)
    return CHOOSING

def show_user_budgets(query, context):
    """Muestra los presupuestos del usuario"""
    user_id = query.from_user.id
    budgets = bot_manager.budgets.get(user_id, {})
    
    if not budgets:
        query.edit_message_text("💡 No tienes presupuestos configurados.\n\n¿Te gustaría crear uno?")
        return CHOOSING
    
    msg = "💡 **Tus Presupuestos:**\n\n"
    
    for category, amount in budgets.items():
        msg += f"📂 **{category}**: ${amount:,.0f}\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Crear Presupuesto", callback_data="create_budget")],
        [InlineKeyboardButton("📊 Análisis de Presupuesto", callback_data="budget_analysis")],
        [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(msg, reply_markup=reply_markup)
    return CHOOSING

def show_complete_analysis_callback(query, context):
    """Versión callback del análisis completo"""
    user_id = query.from_user.id
    
    try:
        monthly_summary = analyzer.get_monthly_summary(user_id)
        
        if not monthly_summary:
            query.edit_message_text("📊 Aún no tienes suficientes datos para análisis.")
            return CHOOSING
        
        msg = f"""
📊 **Análisis Financiero Completo**
📅 **{datetime.datetime.now(TIMEZONE).strftime('%B %Y')}**

💰 **Resumen:**
• Ingresos: ${monthly_summary['total_income']:,.0f}
• Gastos: ${monthly_summary['total_expenses']:,.0f}
• Balance: ${monthly_summary['balance']:,.0f}
• Tasa de Ahorro: {monthly_summary['savings_rate']:.1f}%

📈 **Top Categorías:**
"""
        
        if monthly_summary['by_category']:
            for category, amount in sorted(monthly_summary['by_category'].items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (amount / monthly_summary['total_expenses']) * 100 if monthly_summary['total_expenses'] > 0 else 0
                msg += f"• {category}: ${amount:,.0f} ({percentage:.1f}%)\n"
        
        query.edit_message_text(msg)
        
    except Exception as e:
        logger.error(f"Error en análisis completo callback: {e}")
        query.edit_message_text("❌ Error al generar análisis.")
    
    return CHOOSING

def show_advanced_settings(update: Update, context: CallbackContext):
    """Configuración avanzada del bot con gestión familiar"""
    keyboard = [
        [InlineKeyboardButton("👥 Gestión Familiar", callback_data="family_management")],
        [InlineKeyboardButton("📅 Configurar Fecha de Pago", callback_data="set_payday_date")],
        [InlineKeyboardButton("📅 Configurar Día de Pago", callback_data="set_payday")],
        [InlineKeyboardButton("👥 Ver Usuarios", callback_data="show_users")],
        [InlineKeyboardButton("🔄 Resetear Categorías", callback_data="reset_categories")],
        [InlineKeyboardButton("📊 Estadísticas de Uso", callback_data="usage_stats")],
        [InlineKeyboardButton("🔔 Configurar Notificaciones", callback_data="notification_settings")],
        [InlineKeyboardButton("🏠 Volver al Menú", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_id = update.effective_user.id
    user_info = bot_manager.users.get(user_id, {})
    group = bot_manager.get_user_group(user_id)
    
    # Obtener información de fecha de pago
    payday_info = ""
    if user_id in bot_manager.payday_dates:
        payday_data = bot_manager.payday_dates[user_id]
        next_payday = bot_manager.get_next_payday(user_id)
        if next_payday:
            days_until = (next_payday - datetime.datetime.now(TIMEZONE)).days
            payday_info = f"📅 **Fecha de pago**: {payday_data['day']:02d}/{payday_data['month']:02d}\n"
            payday_info += f"⏰ **Próximo pago**: {next_payday.strftime('%d/%m/%Y')} (en {days_until} días)\n"
    elif user_info.get('payday'):
        payday_info = f"📅 **Día de pago**: {user_info['payday']} de cada mes\n"
    else:
        payday_info = "📅 **Fecha de pago**: No configurada\n"
    
    if group:
        group_info = f"""
👨‍👩‍👧‍👦 **Grupo Familiar:** {group['name']}
👥 **Miembros:** {', '.join(group['member_usernames'])}
🔗 **Código:** {group['invitation_code']}
"""
    else:
        group_info = "👤 **Modo:** Individual\n💡 **Tip:** Crea un grupo para compartir finanzas\n"
    
    msg = f"""
⚙️ **Configuración Avanzada**

👤 **Tu Perfil:**
• Usuario: {user_info.get('username', 'N/A')}
• Registrado: {user_info.get('registered_date', 'N/A'):%d/%m/%Y}

{group_info}

{payday_info}

🎛️ **Opciones disponibles:**
"""
    
    update.message.reply_text(msg, reply_markup=reply_markup)
    return CHOOSING

def button_callback(update: Update, context: CallbackContext):
    """Maneja todos los callbacks de botones inline mejorados"""
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    try:
        # Callbacks básicos existentes
        if data == "back_to_menu":
            # Mostrar menú principal usando query
            markup = ReplyKeyboardMarkup(create_enhanced_main_menu(), one_time_keyboard=True, resize_keyboard=True)
            
            username = bot_manager.users.get(user_id, {}).get('username', query.from_user.first_name)
            group = bot_manager.get_user_group(user_id)
            
            if group:
                welcome_msg = f"""
🤖 **¡Bienvenido de vuelta, {username}!** 

👨‍👩‍👧‍👦 **Grupo Familiar:** {group['name']}
👥 **Miembros:** {', '.join(group['member_usernames'])}

💡 **¿Qué deseas hacer hoy?**
"""
            else:
                welcome_msg = f"""
🤖 **¡Bienvenido de vuelta, {username}!** 

💡 **¿Qué deseas hacer hoy?**
"""
            
            query.message.reply_text(welcome_msg, reply_markup=markup)
            return CHOOSING
        
        # Callbacks para gestión familiar
        elif data == "family_management":
            return show_family_management(query, context)
        
        elif data == "set_payday":
            query.edit_message_text("📅 Ingresa el día del mes en que recibes tu sueldo (1-31):")
            return SETTING_PAYDAY
        
        elif data == "show_users":
            msg = "👥 **Usuarios Registrados:**\n\n"
            for user_id_key, user_info in bot_manager.users.items():
                payday = user_info.get('payday', 'No configurado')
                last_activity = user_info.get('last_activity', 'N/A')
                if isinstance(last_activity, datetime.datetime):
                    last_activity = last_activity.strftime("%d/%m/%Y")
                
                msg += f"👤 **{user_info['username']}** (ID: {user_id_key})\n"
                msg += f"   📅 Día de pago: {payday}\n"
                msg += f"   🕒 Última actividad: {last_activity}\n\n"
            
            query.edit_message_text(msg)
        
        # Otros callbacks existentes...
        elif data == "view_goals":
            return show_user_goals(query, context)
        
        elif data == "create_goal":
            query.edit_message_text("🎯 Escribe el nombre de tu nueva meta de ahorro:")
            context.user_data['creating_goal'] = True
            return SETTING_GOAL
        
        # Callbacks para presupuestos
        elif data == "view_budgets":
            return show_user_budgets(query, context)
        
        elif data == "create_budget":
            query.edit_message_text("💡 Selecciona la categoría para crear un presupuesto:", 
                                   reply_markup=create_category_keyboard())
            return SETTING_BUDGET
        
        # Callbacks para categorías de presupuesto
        elif data.startswith("budget_cat_"):
            category = data.replace("budget_cat_", "")
            context.user_data['budget_category'] = category
            query.edit_message_text(f"💰 Ingresa el monto del presupuesto para '{category}' (solo números):")
            return SETTING_BUDGET
        
        # Callbacks para acciones rápidas
        elif data.startswith("add_"):
            action = data.split("_")[1]
            query.edit_message_text(f"📥 Ingresa el monto del {action} (solo números):")
            context.user_data['action'] = action
            context.user_data['user_id'] = user_id
            return TYPING_AMOUNT
        
        # Otros callbacks
        elif data == "complete_analysis":
            return show_complete_analysis_callback(query, context)
        
        elif data == "show_trends":
            return show_spending_trends_callback(query, context)
        
        elif data == "export_data":
            return export_user_data_callback(query, context)
        
        elif data == "ai_assistant":
            return show_ai_financial_assistant_callback(query, context)
            
        else:
            query.edit_message_text("❌ Opción no reconocida. Usa /start para volver al menú.")
    
    except Exception as e:
        logger.error(f"Error en callback: {e}")
        query.edit_message_text("❌ Error al procesar la acción. Usa /start para reiniciar.")
    
    return CHOOSING

def show_family_management(query, context):
    """Muestra opciones de gestión familiar"""
    user_id = query.from_user.id
    group = bot_manager.get_user_group(user_id)
    
    if group:
        # Usuario ya está en un grupo
        msg = f"""
👨‍👩‍👧‍👦 **Gestión de Grupo Familiar**

📋 **Información del Grupo:**
• **Nombre:** {group['name']}
• **Creador:** {group['creator_username']}
• **Miembros:** {', '.join(group['member_usernames'])}
• **Código de Invitación:** `{group['invitation_code']}`

📅 **Creado:** {group['created_date'].strftime('%d/%m/%Y')}

💡 **¿Qué deseas hacer?**
"""
        
        keyboard = [
            [InlineKeyboardButton("📋 Ver Código de Invitación", callback_data="show_invitation_code")],
            [InlineKeyboardButton("👥 Ver Miembros", callback_data="show_group_members")],
            [InlineKeyboardButton("🏠 Volver", callback_data="back_to_menu")]
        ]
    else:
        # Usuario no está en un grupo
        msg = """
👤 **Gestión Familiar**

Actualmente estás usando el bot de forma individual.

¿Te gustaría compartir tus finanzas con tu pareja o familia?

**Opciones:**

🆕 **Crear Grupo Familiar**
• Genera un código de invitación
• Comparte finanzas con tu pareja
• Análisis conjunto

🔗 **Unirme a Grupo Existente**
• Usa el código de invitación
• Únete al grupo de tu pareja
"""
        
        keyboard = [
            [InlineKeyboardButton("👨‍👩‍👧‍👦 Crear Grupo", callback_data="create_family_group")],
            [InlineKeyboardButton("🔗 Unirme a Grupo", callback_data="join_family_group")],
            [InlineKeyboardButton("🏠 Volver", callback_data="back_to_menu")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(msg, reply_markup=reply_markup)
    return CHOOSING

def cancel(update: Update, context: CallbackContext):
    """Cancela la operación actual"""
    update.message.reply_text("❌ Operación cancelada. Usa /start para volver al menú principal.")
    context.user_data.clear()
    return ConversationHandler.END

def show_quick_stats(update: Update, context: CallbackContext):
    """Muestra estadísticas rápidas del usuario"""
    user_id = update.effective_user.id
    
    try:
        monthly_summary = analyzer.get_monthly_summary(user_id)
        
        if not monthly_summary:
            update.message.reply_text("📊 Aún no tienes suficientes datos. ¡Comienza a registrar transacciones!")
            return
        
        msg = f"""
📊 **Estadísticas Rápidas - {datetime.datetime.now(TIMEZONE).strftime('%B %Y')}**

💰 **Balance**: ${monthly_summary['balance']:,}
📈 **Tasa de Ahorro**: {monthly_summary['savings_rate']:.1f}%
🔢 **Transacciones**: {monthly_summary['transaction_count']}

💡 Usa /start para análisis completo.
"""
        
        update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Error in quick stats: {e}")
        update.message.reply_text("❌ Error al obtener estadísticas.")

def schedule_payday_reminders():
    """Programa los recordatorios de pago diarios"""
    import schedule
    schedule.every().day.at("09:00").do(send_payday_reminders)
    logger.info("Recordatorios de pago programados para las 9:00 AM diariamente")

def send_payday_reminders():
    """Función para enviar recordatorios de pago automáticamente"""
    try:
        for user_id in bot_manager.users.keys():
            if bot_manager.should_send_payday_reminder(user_id):
                reminder_msg = bot_manager.get_payday_reminder_message(user_id)
                if reminder_msg:
                    # Aquí se enviaría el mensaje al usuario
                    # Por ahora solo lo registramos en el log
                    username = bot_manager.users.get(user_id, {}).get('username', 'Usuario')
                    logger.info(f"Recordatorio de pago enviado a {username} (ID: {user_id})")
                    logger.info(f"Mensaje: {reminder_msg[:100]}...")
    except Exception as e:
        logger.error(f"Error enviando recordatorios de pago: {e}")

def run_scheduler():
    """Ejecuta el programador de tareas en segundo plano"""
    import schedule
    while True:
        schedule.run_pending()
        time.sleep(60)  # Revisar cada minuto

def main():
    """Función principal mejorada con sistema de registro"""
    if not BOT_TOKEN:
        logger.error("Token del bot no configurado")
        return
    
    if not ensure_all_sheet_headers():
        logger.warning("No se pudo configurar todas las hojas de Google Sheets")
    
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    
    # Manejador de conversación mejorado con estados de registro
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            # Estados de registro
            TYPING_USERNAME: [MessageHandler(Filters.text & ~Filters.command, receive_username)],
            CHOOSING_REGISTRATION_TYPE: [
                CallbackQueryHandler(handle_registration_callback, 
                                   pattern='^(create_family_group|join_family_group|continue_solo)$')
            ],
            TYPING_GROUP_NAME: [MessageHandler(Filters.text & ~Filters.command, receive_group_name)],
            TYPING_INVITATION_CODE: [MessageHandler(Filters.text & ~Filters.command, receive_invitation_code)],
            
            # Estados principales del bot (existentes)
            CHOOSING: [
                MessageHandler(Filters.text & ~Filters.command, choose_action),
                CallbackQueryHandler(button_callback)
            ],
            TYPING_AMOUNT: [MessageHandler(Filters.text & ~Filters.command, receive_amount)],
            TYPING_CATEGORY: [MessageHandler(Filters.text & ~Filters.command, receive_category)],
            TYPING_CUSTOM_CATEGORY: [MessageHandler(Filters.text & ~Filters.command, receive_custom_category)],
            TYPING_DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, receive_description)],
            TYPING_DUE_DATE: [MessageHandler(Filters.text & ~Filters.command, receive_due_date)],
            SETTING_PAYDAY: [MessageHandler(Filters.text & ~Filters.command, set_payday)],
            TYPING_PAYDAY_DAY: [MessageHandler(Filters.text & ~Filters.command, receive_payday_day)],
            TYPING_PAYDAY_MONTH: [MessageHandler(Filters.text & ~Filters.command, receive_payday_month)],
            SETTING_BUDGET: [MessageHandler(Filters.text & ~Filters.command, receive_budget_amount)],
            SETTING_GOAL: [MessageHandler(Filters.text & ~Filters.command, receive_goal_name)],
            TYPING_GOAL_AMOUNT: [MessageHandler(Filters.text & ~Filters.command, receive_goal_amount)],
            TYPING_GOAL_DATE: [MessageHandler(Filters.text & ~Filters.command, receive_goal_date)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    dp.add_handler(conv_handler)
    dp.add_handler(CallbackQueryHandler(button_callback))
    
    # Comandos mejorados
    dp.add_handler(CommandHandler('help', lambda u, c: u.message.reply_text(
        "🤖 **FinBot Duo Avanzado - Ayuda**\n\n"
        "📋 **Comandos disponibles:**\n"
        "/start - Menú principal\n"
        "/cancel - Cancelar operación actual\n"
        "/help - Mostrar esta ayuda\n"
        "/stats - Estadísticas rápidas\n\n"
        "🎯 **Sistema de Registro y Vinculación:**\n"
        "• 👤 Registro personalizado de usuarios\n"
        "• 👨‍👩‍👧‍👦 Creación de grupos familiares\n"
        "• 🔗 Códigos de invitación para parejas\n"
        "• 📊 Análisis financiero compartido\n\n"
        "🚀 **Funcionalidades Avanzadas:**\n"
        "• 📊 Análisis financiero inteligente\n"
        "• 🎯 Sistema de metas de ahorro\n"
        "• 💡 Presupuestos personalizados\n"
        "• 📈 Análisis de tendencias\n"
        "• 🤖 Asistente IA financiero\n"
        "• 📤 Exportación de datos\n"
        "• 📅 Recordatorios de pago automáticos\n\n"
        "💡 Usa /start para acceder a todas las funciones."
    )))
    
    # Comando de estadísticas rápidas
    dp.add_handler(CommandHandler('stats', lambda u, c: show_quick_stats(u, c)))
    
    # Manejo de errores mejorado
    def error_handler(update, context):
        """Maneja errores del bot"""
        logger.error(f"Error en el bot: {context.error}")
        if update and update.effective_message:
            update.effective_message.reply_text(
                "❌ Ocurrió un error inesperado. Usa /start para reiniciar."
            )
    
    dp.add_error_handler(error_handler)
    
    # Programar recordatorios de pago
    schedule_payday_reminders()
    
    # Iniciar programador en segundo plano
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    logger.info("🤖 FinBot Duo Avanzado iniciado correctamente")
    logger.info(f"🔗 Bot disponible como: @{updater.bot.username}")
    logger.info("👨‍👩‍👧‍👦 Sistema de grupos familiares activo")
    logger.info("🔔 Recordatorios de pago programados y activos")
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
