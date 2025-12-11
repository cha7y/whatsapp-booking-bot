# app.py - Glavni Flask server
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# MongoDB konekcija
MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI)
db = client['booking_system']
reservations = db['reservations']
clients = db['clients']

# Bot state storage (u memoriji - za produkciju koristi Redis)
user_sessions = {}

# Konfiguracija biznisa (primjer - kasnije iz DB)
BUSINESS_CONFIG = {
    'name': 'Frizerski Salon Elegance',
    'services': ['Šišanje', 'Farbanje', 'Feniranje', 'Manikura'],
    'working_hours': '09:00-20:00',
    'available_slots': ['09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '17:00']
}

def get_user_session(phone_number):
    """Dohvati ili kreiraj session za korisnika"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'step': 'initial',
            'data': {}
        }
    return user_sessions[phone_number]

def process_message(phone_number, message):
    """Glavna logika za obradu poruka"""
    session = get_user_session(phone_number)
    step = session['step']
    data = session['data']
    msg = message.lower().strip()
    
    # KORAK 1: Početak
    if step == 'initial':
        if 'rezerv' in msg or 'termin' in msg:
            session['step'] = 'service'
            services_list = '\n'.join([f"{i+1}. {s}" for i, s in enumerate(BUSINESS_CONFIG['services'])])
            return f"Odlično! Nudimo sljedeće usluge:\n\n{services_list}\n\nOdaberite broj usluge (1-4):"
        elif 'radno' in msg or 'vrijeme' in msg:
            return f"Naše radno vrijeme je {BUSINESS_CONFIG['working_hours']}, radnim danima i subotom."
        else:
            return 'Pozdrav! 👋\n\nZa rezervaciju napišite "rezervacija" ili "termin".\nZa radno vrijeme napišite "radno vrijeme".'
    
    # KORAK 2: Odabir usluge
    elif step == 'service':
        try:
            service_num = int(msg)
            if 1 <= service_num <= len(BUSINESS_CONFIG['services']):
                selected_service = BUSINESS_CONFIG['services'][service_num - 1]
                data['service'] = selected_service
                session['step'] = 'date'
                return f"✅ Odabrali ste: {selected_service}\n\nZa koji datum želite rezervirati?\n(npr. 15.12.2024 ili 'sutra')"
        except ValueError:
            pass
        return "Molim odaberite broj usluge (1-4)."
    
    # KORAK 3: Datum
    elif step == 'date':
        if msg == 'sutra' or msg == 'danas' or '.' in message:
            data['date'] = message
            session['step'] = 'time'
            slots_list = '\n'.join([f"{i+1}. {s}" for i, s in enumerate(BUSINESS_CONFIG['available_slots'])])
            return f"✅ Datum: {message}\n\nDostupni termini:\n\n{slots_list}\n\nOdaberite broj (1-7):"
        return "Molim unesite datum (npr. 15.12.2024 ili 'sutra')."
    
    # KORAK 4: Vrijeme
    elif step == 'time':
        try:
            time_num = int(msg)
            if 1 <= time_num <= len(BUSINESS_CONFIG['available_slots']):
                selected_time = BUSINESS_CONFIG['available_slots'][time_num - 1]
                data['time'] = selected_time
                session['step'] = 'name'
                return f"✅ Vrijeme: {selected_time}\n\nKako se zovete?"
        except ValueError:
            pass
        return "Molim odaberite broj termina (1-7)."
    
    # KORAK 5: Ime
    elif step == 'name':
        if len(message.strip()) >= 2:
            data['name'] = message.strip()
            session['step'] = 'phone'
            return f"✅ Ime: {message}\n\nMolim unesite vaš broj telefona:"
        return "Molim unesite vaše ime."
    
    # KORAK 6: Telefon
    elif step == 'phone':
        phone_clean = message.replace(' ', '').replace('+', '')
        if phone_clean.isdigit() and len(phone_clean) >= 9:
            data['phone'] = message.strip()
            session['step'] = 'confirm'
            
            summary = f"""✅ PREGLED REZERVACIJE:

🏪 {BUSINESS_CONFIG['name']}
💇 Usluga: {data['service']}
📅 Datum: {data['date']}
🕐 Vrijeme: {data['time']}
👤 Ime: {data['name']}
📞 Telefon: {data['phone']}

Potvrdite rezervaciju: 'DA' ili 'NE'"""
            return summary
        return "Molim unesite ispravan broj telefona."
    
    # KORAK 7: Potvrda
    elif step == 'confirm':
        if msg in ['da', 'yes', 'potvrdi']:
            # Spremi u bazu
            reservation = {
                'business': BUSINESS_CONFIG['name'],
                'service': data['service'],
                'date': data['date'],
                'time': data['time'],
                'client_name': data['name'],
                'client_phone': data['phone'],
                'whatsapp_number': phone_number,
                'status': 'confirmed',
                'created_at': datetime.utcnow()
            }
            reservations.insert_one(reservation)
            
            # Reset session
            session['step'] = 'initial'
            session['data'] = {}
            
            return "🎉 REZERVACIJA POTVRĐENA!\n\nDobit ćete SMS potvrdu.\nHvala što koristite naše usluge!\n\nZa novu rezervaciju napišite 'rezervacija'."
        
        elif msg in ['ne', 'no', 'odustani']:
            session['step'] = 'initial'
            session['data'] = {}
            return "❌ Rezervacija otkazana.\n\nZa novu rezervaciju napišite 'rezervacija'."
        
        return "Molim odgovorite sa 'DA' ili 'NE'."
    
    return "Nisam razumio. Za rezervaciju napišite 'rezervacija'."

@app.route('/webhook', methods=['POST'])
def webhook():
    """Twilio webhook endpoint"""
    incoming_msg = request.values.get('Body', '')
    sender = request.values.get('From', '')
    
    # Obradi poruku
    response_text = process_message(sender, incoming_msg)
    
    # Twilio odgovor
    resp = MessagingResponse()
    resp.message(response_text)
    
    return str(resp)

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'message': 'WhatsApp Booking Bot is running'}

@app.route('/')
def home():
    """Home page"""
    return '''
    <h1>WhatsApp Booking Bot</h1>
    <p>Bot je aktivan i radi!</p>
    <p>Webhook URL: /webhook</p>
    <p>Health check: /health</p>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)