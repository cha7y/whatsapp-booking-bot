# app.py - WhatsApp Bot sa pametnom dostupnošću
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# MongoDB konekcija
MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI)
db = client['booking_systems']  # SA "S" NA KRAJU!
reservations = db['reservations']
clients_db = db['clients']

# User sessions
user_sessions = {}

def get_business_config(business_id):
    """Dohvati konfiguraciju biznisa"""
    return clients_db.find_one({'business_id': business_id})

def get_all_businesses():
    """Dohvati SVE biznise"""
    try:
        all_clients = list(clients_db.find({}))
        print(f"Found {len(all_clients)} businesses in database")
        for client_doc in all_clients:
            print(f"  - {client_doc.get('name')} (active: {client_doc.get('active')})")
        return all_clients
    except Exception as e:
        print(f"ERROR fetching businesses: {e}")
        return []

def get_available_slots(business_id, date_str):
    """Dohvati slobodne termine za datum"""
    business = get_business_config(business_id)
    if not business:
        return []
    
    all_slots = business.get('available_slots', [])
    
    # Dohvati zauzete termine
    existing = list(reservations.find({
        'business_id': business_id,
        'date': date_str,
        'status': {'$in': ['confirmed', 'pending']}
    }))
    
    booked = [res['time'] for res in existing]
    available = [slot for slot in all_slots if slot not in booked]
    
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
    """Glavna logika bota"""
    session = get_user_session(phone_number)
    step = session['step']
    data = session['data']
    msg = message.lower().strip()
    
    print(f"Phone: {phone_number} | Step: {step} | Msg: {msg}")
    
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
            return f"Pozdrav! Za koji biznis zelite rezervirati?\n\n{business_list}\n\nOdaberite broj:"
        
        try:
            business_num = int(msg)
            if 1 <= business_num <= len(businesses):
                selected = businesses[business_num - 1]
                session['business_id'] = selected['business_id']
                session['step'] = 'initial'
                data['business_name'] = selected['name']
                return f"Odabrali ste: {selected['name']}\n\nZa rezervaciju napisite 'termin'."
        except ValueError:
            pass
        
        business_list = '\n'.join([
            f"{i+1}. {b['name']}" for i, b in enumerate(businesses)
        ])
        return f"Odaberite biznis:\n\n{business_list}"
    
    business_config = get_business_config(session['business_id'])
    if not business_config:
        session['step'] = 'select_business'
        return "Greska. Odaberite biznis ponovno."
    
    # KORAK 1: Početak
    if step == 'initial':
        if 'rezerv' in msg or 'termin' in msg:
            session['step'] = 'service'
            services_list = '\n'.join([
                f"{i+1}. {s}" 
                for i, s in enumerate(business_config['services'])
            ])
            return f"{business_config['name']}\n\nUsluge:\n\n{services_list}\n\nOdaberite broj:"
        elif 'radno' in msg:
            return f"Radno vrijeme: {business_config['working_hours']}"
        else:
            return f"Za rezervaciju napisite 'termin'."
    
    # KORAK 2: Usluga
    elif step == 'service':
        try:
            service_num = int(msg)
            if 1 <= service_num <= len(business_config['services']):
                data['service'] = business_config['services'][service_num - 1]
                session['step'] = 'date'
                return f"Usluga: {data['service']}\n\nZa koji datum?\n(npr. 15.12.2024 ili 'sutra')"
        except ValueError:
            pass
        return "Molim odaberite broj usluge."
    
    # KORAK 3: Datum
    elif step == 'date':
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
        
        # Provjeri slobodne termine
        available_slots = get_available_slots(session['business_id'], date_str)
        
        if not available_slots:
            return f"Nazalost, za {date_str} nema slobodnih termina.\n\nPokusajte s drugim datumom."
        
        slots_list = '\n'.join([
            f"{i+1}. {s}" for i, s in enumerate(available_slots)
        ])
        
        data['available_slots'] = available_slots
        
        return f"Datum: {date_str}\n\nSlobodni termini:\n\n{slots_list}\n\nOdaberite broj:"
    
    # KORAK 4: Vrijeme
    elif step == 'time':
        try:
            time_num = int(msg)
            available_slots = data.get('available_slots', [])
            
            if 1 <= time_num <= len(available_slots):
                data['time'] = available_slots[time_num - 1]
                session['step'] = 'name'
                return f"Vrijeme: {data['time']}\n\nKako se zovete?"
        except ValueError:
            pass
        return "Molim odaberite broj termina."
    
    # KORAK 5: Ime
    elif step == 'name':
        if len(message.strip()) >= 2:
            data['name'] = message.strip()
            session['step'] = 'phone'
            return f"Ime: {message}\n\nVas broj telefona:"
        return "Molim unesite vase ime."
    
    # KORAK 6: Telefon
    elif step == 'phone':
        phone_clean = message.replace(' ', '').replace('+', '')
        if phone_clean.isdigit() and len(phone_clean) >= 9:
            data['phone'] = message.strip()
            session['step'] = 'confirm'
            
            summary = f"""PREGLED REZERVACIJE:

{business_config['name']}
{business_config['address']}
{data['service']}
{data['date']}
{data['time']}
{data['name']}
{data['phone']}

Potvrdite: 'DA' ili 'NE'"""
            return summary
        return "Molim unesite ispravan broj."
    
    # KORAK 7: Potvrda
    elif step == 'confirm':
        if msg in ['da', 'yes', 'potvrdi']:
            try:
                # Dvostruka provjera dostupnosti
                available_slots = get_available_slots(session['business_id'], data['date'])
                
                if data['time'] not in available_slots:
                    return f"Termin {data['time']} je upravo zauzet!\n\nOdaberite drugi termin. Napisite 'termin'."
                
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
                print(f"Reservation saved: {result.inserted_id}")
                
                # Reset session
                session['step'] = 'select_business'
                session['business_id'] = None
                session['data'] = {}
                
                return f"POTVRDJENO!\n\nRezervirali ste:\n{data['date']} u {data['time']}\n\n{business_config['name']} ce vas kontaktirati.\n\nZa novu rezervaciju napisite 'termin'."
                
            except Exception as e:
                print(f"Error saving: {e}")
                return "Greska pri spremanju. Pokusajte ponovno."
        
        elif msg in ['ne', 'no', 'odustani']:
            session['step'] = 'select_business'
            session['business_id'] = None
            session['data'] = {}
            return "Otkazano."
        
        return "Odgovorite sa 'DA' ili 'NE'."
    
    return "Napisite 'termin' za rezervaciju."

@app.route('/webhook', methods=['POST'])
def webhook():
    """Twilio webhook"""
    try:
        incoming_msg = request.values.get('Body', '').strip()
        sender = request.values.get('From', '').strip()
        
        print(f"Received: {incoming_msg} from {sender}")
        
        response_text = process_message(sender, incoming_msg)
        
        print(f"Response: {response_text[:50]}")
        
        resp = MessagingResponse()
        resp.message(response_text)
        
        return Response(str(resp), mimetype='text/xml')
        
    except Exception as e:
        print(f"ERROR: {e}")
        resp = MessagingResponse()
        resp.message("Bot greska.")
        return Response(str(resp), mimetype='text/xml')

@app.route('/salon/<business_id>')
def salon_dashboard(business_id):
    """Dashboard za salon"""
    business = get_business_config(business_id)
    
    if not business:
        return "Salon nije pronaden", 404
    
    salon_reservations = list(reservations.find({
        'business_id': business_id
    }).sort('created_at', -1).limit(50))
    
    reservations_by_date = {}
    for res in salon_reservations:
        date = res['date']
        if date not in reservations_by_date:
            reservations_by_date[date] = []
        reservations_by_date[date].append(res)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{business['name']} - Dashboard</title>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                margin: 0;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }}
            h1 {{ color: #667eea; }}
            .reservation {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 10px;
                display: flex;
                justify-content: space-between;
            }}
            .time {{ background: #667eea; color: white; padding: 10px 20px; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{business['name']}</h1>
            <p>{business['address']}, {business['city']}</p>
            <p>{business['phone']}</p>
            
            <h2>Rezervacije</h2>
    """
    
    if reservations_by_date:
        for date, date_reservations in reservations_by_date.items():
            html += f"<h3>{date}</h3>"
            for res in date_reservations:
                html += f"""
                <div class="reservation">
                    <div>
                        <strong>{res['client_name']}</strong><br>
                        {res['service']}<br>
                        <small>{res['client_phone']}</small>
                    </div>
                    <div class="time">{res['time']}</div>
                </div>
                """
    else:
        html += "<p>Nema rezervacija</p>"
    
    html += """
        </div>
    </body>
    </html>
    """
    
    return html

@app.route('/health')
def health():
    return {'status': 'ok', 'message': 'Bot running'}

@app.route('/')
def home():
    businesses = get_all_businesses()
    links = '<br>'.join([
        f'<a href="/salon/{b["business_id"]}">{b["name"]} Dashboard</a>' 
        for b in businesses
    ])
    
    return f'''
    <h1>WhatsApp Booking Bot</h1>
    <p>Bot je aktivan!</p>
    <h2>Salon Dashboards:</h2>
    {links if links else '<p>Nema biznisa.</p>'}
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)