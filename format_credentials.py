#!/usr/bin/env python3
"""
Script para formatear credenciales de Google Sheets para Railway
"""

import json
import sys

def format_credentials_for_railway(credentials_file):
    """
    Convierte el archivo credentials.json a formato de una línea
    para usarlo como variable de entorno en Railway
    """
    try:
        with open(credentials_file, 'r', encoding='utf-8') as file:
            credentials = json.load(file)
        
        # Convertir a JSON compacto (una línea)
        compact_json = json.dumps(credentials, separators=(',', ':'))
        
        print("="*60)
        print("🔑 CREDENCIALES FORMATEADAS PARA RAILWAY")
        print("="*60)
        print()
        print("📋 Copia esta línea completa y úsala como valor de GOOGLE_CREDENTIALS_JSON:")
        print()
        print(compact_json)
        print()
        print("="*60)
        print("✅ Pasos siguientes:")
        print("1. Ve a tu proyecto en Railway")
        print("2. Ir a Variables de entorno")
        print("3. Agregar: GOOGLE_CREDENTIALS_JSON")
        print("4. Pegar el valor de arriba")
        print("5. Redeploy")
        print("="*60)
        
        # Verificar elementos importantes
        print("\n🔍 VERIFICACIÓN DE CREDENCIALES:")
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        
        for field in required_fields:
            if field in credentials:
                if field == 'client_email':
                    print(f"✅ {field}: {credentials[field]}")
                    print(f"   👆 COMPARTE tu Google Sheets con este email")
                elif field == 'project_id':
                    print(f"✅ {field}: {credentials[field]}")
                else:
                    print(f"✅ {field}: ✓ presente")
            else:
                print(f"❌ {field}: ✗ faltante")
        
        return compact_json
        
    except FileNotFoundError:
        print("❌ Error: No se encontró el archivo credentials.json")
        print("💡 Asegúrate de que el archivo esté en el directorio actual")
        return None
    except json.JSONDecodeError:
        print("❌ Error: El archivo credentials.json no tiene formato JSON válido")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

def validate_google_sheets_setup(credentials):
    """
    Valida que las credenciales estén bien configuradas
    """
    print("\n📋 CHECKLIST DE CONFIGURACIÓN:")
    print("□ 1. Credenciales descargadas de Google Cloud Console")
    print("□ 2. Google Sheets API habilitada")
    print("□ 3. Google Drive API habilitada") 
    print("□ 4. Hoja 'FinanzasFamiliares' creada en Google Sheets")
    print(f"□ 5. Hoja compartida con: {credentials.get('client_email', 'N/A')}")
    print("□ 6. Variable GOOGLE_CREDENTIALS_JSON agregada en Railway")
    print("□ 7. Bot redeployeado en Railway")

if __name__ == "__main__":
    print("🔑 Formateador de Credenciales para Railway")
    print("="*50)
    
    # Usar archivo por defecto o el especificado
    credentials_file = "credentials.json"
    if len(sys.argv) > 1:
        credentials_file = sys.argv[1]
    
    print(f"📂 Buscando archivo: {credentials_file}")
    
    formatted = format_credentials_for_railway(credentials_file)
    
    if formatted:
        # Intentar cargar las credenciales para validación
        try:
            credentials = json.loads(formatted)
            validate_google_sheets_setup(credentials)
        except:
            pass 