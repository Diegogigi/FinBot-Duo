#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏦 Bot de Finanzas Familiares - Script de Configuración
======================================================

Este script te ayuda a configurar tu bot de finanzas familiares.
Ejecuta: python setup.py
"""

import os
import sys
import subprocess
import shutil

def print_header():
    """Imprime el header del script"""
    print("=" * 60)
    print("🏦 BOT DE FINANZAS FAMILIARES - CONFIGURACIÓN")
    print("=" * 60)
    print()

def check_python_version():
    """Verifica la versión de Python"""
    print("🔍 Verificando versión de Python...")
    if sys.version_info < (3, 8):
        print("❌ ERROR: Se requiere Python 3.8 o superior")
        print(f"   Versión actual: Python {sys.version}")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} - OK")
    print()

def install_requirements():
    """Instala las dependencias requeridas"""
    print("📦 Instalando dependencias...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencias instaladas correctamente")
    except subprocess.CalledProcessError:
        print("❌ Error al instalar dependencias")
        print("   Intenta ejecutar manualmente: pip install -r requirements.txt")
        return False
    print()
    return True

def create_env_file():
    """Crea el archivo .env desde el ejemplo"""
    print("⚙️ Configurando archivo de variables de entorno...")
    
    if os.path.exists(".env"):
        print("⚠️  El archivo .env ya existe")
        response = input("¿Quieres sobrescribirlo? (s/N): ").lower()
        if response != 's':
            print("✅ Manteniendo archivo .env existente")
            print()
            return True
    
    if os.path.exists("env_example.txt"):
        try:
            shutil.copy("env_example.txt", ".env")
            print("✅ Archivo .env creado desde env_example.txt")
            print("⚠️  RECUERDA: Edita el archivo .env con tus datos reales")
        except Exception as e:
            print(f"❌ Error al crear .env: {e}")
            return False
    else:
        print("❌ No se encontró env_example.txt")
        return False
    
    print()
    return True

def check_credentials():
    """Verifica si existe el archivo de credenciales"""
    print("🔑 Verificando credenciales de Google...")
    
    if os.path.exists("credentials.json"):
        print("✅ Archivo credentials.json encontrado")
    else:
        print("⚠️  Archivo credentials.json NO encontrado")
        print("   📝 NECESITAS:")
        print("      1. Ir a Google Cloud Console")
        print("      2. Activar Google Sheets API y Google Drive API")
        print("      3. Crear credenciales de cuenta de servicio")
        print("      4. Descargar credentials.json y colocarlo aquí")
        print("      5. Compartir tu hoja de Google Sheets con el email de la cuenta de servicio")
    
    print()

def validate_config():
    """Valida la configuración básica"""
    print("✅ Validando configuración...")
    
    issues = []
    
    # Verificar .env
    if not os.path.exists(".env"):
        issues.append("Falta archivo .env")
    
    # Verificar credentials.json
    if not os.path.exists("credentials.json"):
        issues.append("Falta archivo credentials.json")
    
    # Verificar archivos principales
    required_files = ["bot.py", "config.py", "requirements.txt"]
    for file in required_files:
        if not os.path.exists(file):
            issues.append(f"Falta archivo {file}")
    
    if issues:
        print("⚠️  Problemas encontrados:")
        for issue in issues:
            print(f"   - {issue}")
        print()
        return False
    
    print("✅ Configuración básica completa")
    print()
    return True

def show_next_steps():
    """Muestra los próximos pasos"""
    print("🚀 PRÓXIMOS PASOS:")
    print("=" * 40)
    print()
    print("1. 📝 Edita el archivo .env con tus datos:")
    print("   - BOT_TOKEN (de @BotFather)")
    print("   - GOOGLE_SHEETS_NAME")
    print("   - TIMEZONE")
    print()
    print("2. 🔑 Configura Google Sheets API:")
    print("   - Descarga credentials.json")
    print("   - Colócalo en la raíz del proyecto")
    print("   - Comparte tu hoja con el email de la cuenta de servicio")
    print()
    print("3. ▶️  Ejecuta el bot:")
    print("   python bot.py")
    print()
    print("4. 💬 Prueba en Telegram:")
    print("   Busca tu bot y envía /start")
    print()
    print("📚 Para más información, consulta el README.md")
    print()

def main():
    """Función principal"""
    print_header()
    
    # Verificar Python
    check_python_version()
    
    # Instalar dependencias
    if not install_requirements():
        sys.exit(1)
    
    # Crear archivo .env
    if not create_env_file():
        sys.exit(1)
    
    # Verificar credenciales
    check_credentials()
    
    # Validar configuración
    validate_config()
    
    # Mostrar próximos pasos
    show_next_steps()
    
    print("🎉 ¡Configuración completada!")
    print("   ¡Tu bot de finanzas familiares está casi listo!")

if __name__ == "__main__":
    main() 