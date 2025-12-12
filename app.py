# app.py - SA PAMETNOM DOSTUPNOŠĆU TERMINA

# DEBUGGING - omogući detaljno logiranje
import logging
logging.basicConfig(level=logging.DEBUG)

from flask import Flask, request, render_template_string
from twilio.twiml.messaging_response import MessagingResponse
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI)
db = client['booking_system']
reservations = db['reservations']
clients_db = db['clients']

user_sessions = {}

def get_business_config(business_id):
    """Dohvati konfiguraciju biznisa"""
    return clients_db.find_one({'business_id': business_id})

def get_all_businesses():
    """Dohvati SVE biznise (ignorira active polje)"""
    all_clients = list(clients_db.find({}))
    print(f"🔍 Found {len(all_clients)} businesses in database")
    for client in all_clients:
        print(f"  - {client.get('name')} (active: {client.get('active')})")
    return all_clients

def get_available_slots(business_id, date_str):
    """
    PAMETNA PROVJERA DOSTUPNOSTI
    Vraća samo slobodne termine za određeni datum
    """
    business = get_business_config(business_id)
    if not business:
        return []
    
    all_slots = business['available_slots']
    
    # Dohvati sve rezervacije za ovaj biznis i datum
    existing_reservations = list(reservations.find({
        'business_id': business_id,
        'date': date_str,
        'status': {'$in': ['confirmed', 'pending']}  # Samo aktivne rezervacije
    }))
    
    # Zauzeti termini
    booked_times = [res['time'] for res in existing_reservations]
    
    # Slobodni termini
    available = [slot for slot in all_slots if slot not in booked_times]
    
    return available

def get_user_session(phone_number):
    """Dohvati ili kreiraj session"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'step': 'select_business',
            'data': {},
            'business_id': None
        }
    return user_sessions[phone_number]

def process_message(phone_number, message):
    """Glavna logika sa dinamičkim terminima"""
    session = get_user_session(phone_number)
    step = session['step']
    data = session['data']
    msg = message.lower().strip()
    
    print(f"📱 {phone_number} | Step: {step} | Msg: {msg}")
    
    # KORAK 0: Odabir biznisa
    if step == 'select_business':
        businesses = get_all_businesses()
        
        if not businesses:
            return "Trenutno nema dostupnih biznisa."
        
        if 'rezerv' in msg or 'termin' in msg or msg == 'start':
            business_list = '\n'.join([
                f"{i+1}. {b['name']} - {b['city']}" 
                for i, b in enumerate(businesses)
            ])
            return f"👋 Za koji biznis želite rezervirati?\n\n{business_list}\n\nOdaberite broj:"
        
        try:
            business_num = int(msg)
            if 1 <= business_num <= len(businesses):
                selected = businesses[business_num - 1]
                session['business_id'] = selected['business_id']
                session['step'] = 'initial'
                data['business_name'] = selected['name']
                return f"✅ {selected['name']}\n\nZa rezervaciju napišite 'termin'."
        except ValueError:
            pass
        
        business_list = '\n'.join([
            f"{i+1}. {b['name']}" for i, b in enumerate(businesses)
        ])
        return f"Odaberite biznis:\n\n{business_list}"
    
    business_config = get_business_config(session['business_id'])
    if not business_config:
        session['step'] = 'select_business'
        return "Greška. Odaberite biznis ponovno."
    
    # KORAK 1: Početak
    if step == 'initial':
        if 'rezerv' in msg or 'termin' in msg:
            session['step'] = 'service'
            services_list = '\n'.join([
                f"{i+1}. {s}" 
                for i, s in enumerate(business_config['services'])
            ])
            return f"🏪 {business_config['name']}\n\nUsluge:\n\n{services_list}\n\nOdaberite broj:"
        elif 'radno' in msg:
            return f"Radno vrijeme: {business_config['working_hours']}"
        else:
            return f"Za rezervaciju u {business_config['name']} napišite 'termin'."
    
    # KORAK 2: Usluga
    elif step == 'service':
        try:
            service_num = int(msg)
            if 1 <= service_num <= len(business_config['services']):
                data['service'] = business_config['services'][service_num - 1]
                session['step'] = 'date'
                return f"✅ Usluga: {data['service']}\n\nZa koji datum?\n(npr. 15.12.2024 ili 'sutra')"
        except ValueError:
            pass
        return "Molim odaberite broj usluge."
    
    # KORAK 3: Datum
    elif step == 'date':
        # Parse datum
        if msg == 'danas':
            date_str = datetime.now().strftime('%d.%m.%Y')
        elif msg == 'sutra':
            date_str = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
        elif '.' in message:
            date_str = message
        else:
            return "Molim unesite datum (npr. 15.12.2024 ili 'sutra')."
        
        data['date'] = date_str
        session['step'] = 'time'
        
        # DINAMIČKA PROVJERA DOSTUPNOSTI! 🎯
        available_slots = get_available_slots(session['business_id'], date_str)
        
        if not available_slots:
            return f"❌ Nažalost, za {date_str} nema slobodnih termina.\n\nPokušajte s drugim datumom."
        
        slots_list = '\n'.join([
            f"{i+1}. {s}" for i, s in enumerate(available_slots)
        ])
        
        # Spremi dostupne slotove u session
        data['available_slots'] = available_slots
        
        return f"✅ Datum: {date_str}\n\n⏰ Slobodni termini:\n\n{slots_list}\n\nOdaberite broj:"
    
    # KORAK 4: Vrijeme
    elif step == 'time':
        try:
            time_num = int(msg)
            available_slots = data.get('available_slots', [])
            
            if 1 <= time_num <= len(available_slots):
                data['time'] = available_slots[time_num - 1]
                session['step'] = 'name'
                return f"✅ Vrijeme: {data['time']}\n\nKako se zovete?"
        except ValueError:
            pass
        return "Molim odaberite broj termina."
    
    # KORAK 5: Ime
    elif step == 'name':
        if len(message.strip()) >= 2:
            data['name'] = message.strip()
            session['step'] = 'phone'
            return f"✅ Ime: {message}\n\nVaš broj telefona:"
        return "Molim unesite vaše ime."
    
    # KORAK 6: Telefon
    elif step == 'phone':
        phone_clean = message.replace(' ', '').replace('+', '')
        if phone_clean.isdigit() and len(phone_clean) >= 9:
            data['phone'] = message.strip()
            session['step'] = 'confirm'
            
            summary = f"""✅ PREGLED REZERVACIJE:

🏪 {business_config['name']}
📍 {business_config['address']}
💇 {data['service']}
📅 {data['date']}
🕐 {data['time']}
👤 {data['name']}
📞 {data['phone']}

Potvrdite: 'DA' ili 'NE'"""
            return summary
        return "Molim unesite ispravan broj."
    
    # KORAK 7: Potvrda
    elif step == 'confirm':
        if msg in ['da', 'yes', 'potvrdi', 'potvrđujem']:
            try:
                # DVOSTRUKA PROVJERA - prije spremanja provjeravamo jel termin još slobodan!
                available_slots = get_available_slots(session['business_id'], data['date'])
                
                if data['time'] not in available_slots:
                    return f"⚠️ Termin {data['time']} je upravo zauzet!\n\nMolim odaberite drugi termin. Napišite 'termin' za ponovni pokušaj."
                
                # Spremi rezervaciju
                reservation = {
                    'business_id': session['business_id'],
                    'business_name': business_config['name'],
                    'business_phone': business_config['phone'],
                    'business_email': business_config.get('email'),
                    'service': data['service'],
                    'date': data['date'],
                    'time': data['time'],
                    'client_name': data['name'],
                    'client_phone': data['phone'],
                    'whatsapp_number': phone_number,
                    'status': 'confirmed',
                    'created_at': datetime.utcnow()
                }
                
                result = reservations.insert_one(reservation)
                print(f"✅ Reservation saved: {result.inserted_id}")
                
                # TODO: Pošalji notifikaciju salonu!
                
                # Reset session
                session['step'] = 'select_business'
                session['business_id'] = None
                session['data'] = {}
                
                return f"🎉 POTVRĐENO!\n\nRezervirali ste:\n📅 {data['date']} u {data['time']}\n\n{business_config['name']} će vas kontaktirati za potvrdu.\n\nZa novu rezervaciju napišite 'termin'."
                
            except Exception as e:
                print(f"❌ Error: {e}")
                return "Greška pri spremanju. Pokušajte ponovno."
        
        elif msg in ['ne', 'no', 'odustani']:
            session['step'] = 'select_business'
            session['business_id'] = None
            session['data'] = {}
            return "❌ Otkazano."
        
        return "Odgovorite sa 'DA' ili 'NE'."
    
    return "Napišite 'termin' za rezervaciju."

@app.route('/webhook', methods=['POST'])
def webhook():
    """Twilio webhook"""
    incoming_msg = request.values.get('Body', '')
    sender = request.values.get('From', '')
    
    response_text = process_message(sender, incoming_msg)
    
    resp = MessagingResponse()
    resp.message(response_text)
    
    return str(resp)

@app.route('/salon/<business_id>')
def salon_dashboard(business_id):
    """Dashboard za specifičan salon"""
    business = get_business_config(business_id)
    
    if not business:
        return "Salon nije pronađen", 404
    
    # Dohvati sve rezervacije ovog salona
    salon_reservations = list(reservations.find({
        'business_id': business_id
    }).sort('created_at', -1).limit(50))
    
    # Grupiraj po datumu
    reservations_by_date = {}
    for res in salon_reservations:
        date = res['date']
        if date not in reservations_by_date:
            reservations_by_date[date] = []
        reservations_by_date[date].append(res)
    
    # HTML template za salon dashboard
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ business.name }} - Dashboard</title>
        <meta charset="UTF-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                margin: 0;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }
            h1 { color: #667eea; margin-bottom: 10px; }
            .info { color: #666; margin-bottom: 30px; }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
            }
            .stat-card h3 { color: #666; font-size: 14px; margin: 0 0 10px 0; }
            .stat-card p { color: #333; font-size: 32px; font-weight: bold; margin: 0; }
            .date-section {
                margin-bottom: 30px;
                border: 2px solid #e9ecef;
                border-radius: 10px;
                padding: 20px;
            }
            .date-header {
                font-size: 20px;
                font-weight: bold;
                color: #667eea;
                margin-bottom: 15px;
            }
            .reservation {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 10px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .reservation-info strong { display: block; margin-bottom: 5px; }
            .reservation-time {
                background: #667eea;
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
            }
            .empty { text-align: center; padding: 40px; color: #999; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏪 {{ business.name }}</h1>
            <div class="info">
                📍 {{ business.address }}, {{ business.city }}<br>
                📞 {{ business.phone }}
                {% if business.email %} | 📧 {{ business.email }}{% endif %}
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <h3>Ukupno rezervacija</h3>
                    <p>{{ total_reservations }}</p>
                </div>
                <div class="stat-card">
                    <h3>Danas</h3>
                    <p>{{ today_count }}</p>
                </div>
                <div class="stat-card">
                    <h3>Ovaj tjedan</h3>
                    <p>{{ week_count }}</p>
                </div>
            </div>
            
            <h2 style="margin-bottom: 20px;">📅 Rezervacije</h2>
            
            {% if reservations_by_date %}
                {% for date, date_reservations in reservations_by_date.items() %}
                <div class="date-section">
                    <div class="date-header">📅 {{ date }}</div>
                    {% for res in date_reservations %}
                    <div class="reservation">
                        <div class="reservation-info">
                            <strong>{{ res.client_name }}</strong>
                            <span>{{ res.service }}</span><br>
                            <small>📞 {{ res.client_phone }}</small>
                        </div>
                        <div class="reservation-time">🕐 {{ res.time }}</div>
                    </div>
                    {% endfor %}
                </div>
                {% endfor %}
            {% else %}
                <div class="empty">
                    <h3>📭 Nema rezervacija</h3>
                    <p>Rezervacije će se prikazati ovdje</p>
                </div>
            {% endif %}
        </div>
    </body>
    </html>
    """
    
    from jinja2 import Template
    template = Template(html)
    
    # Stats
    total_reservations = len(salon_reservations)
    today = datetime.now().strftime('%d.%m.%Y')
    today_count = len([r for r in salon_reservations if r['date'] == today])
    week_count = len(salon_reservations)  # TODO: Calculate properly
    
    return template.render(
        business=business,
        reservations_by_date=reservations_by_date,
        total_reservations=total_reservations,
        today_count=today_count,
        week_count=week_count
    )

@app.route('/health')
def health():
    return {'status': 'ok', 'message': 'Smart availability bot running'}

@app.route('/')
def home():
    businesses = get_all_businesses()
    business_links = '<br>'.join([
        f'<a href="/salon/{b["business_id"]}">{b["name"]} Dashboard</a>' 
        for b in businesses
    ])
    
    return f'''
    <h1>WhatsApp Booking Bot</h1>
    <p>Bot je aktivan!</p>
    <h2>Salon Dashboards:</h2>
    {business_links if business_links else '<p>Nema biznisa u bazi.</p>'}
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)