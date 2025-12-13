# app.py - WhatsApp Booking Bot with Admin Panel
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI)
db = client['booking_systems']
reservations = db['reservations']
clients_db = db['clients']

# User sessions
user_sessions = {}

# Admin password - CHANGE THIS!
ADMIN_PASSWORD = "admin2024"

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_business_config(business_id):
    """Get business configuration"""
    return clients_db.find_one({'business_id': business_id})

def get_all_businesses():
    """Get all businesses"""
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
    """Get available time slots for a date"""
    business = get_business_config(business_id)
    if not business:
        return []
    
    all_slots = business.get('available_slots', [])
    
    # Get booked slots
    existing = list(reservations.find({
        'business_id': business_id,
        'date': date_str,
        'status': {'$in': ['confirmed', 'pending']}
    }))
    
    booked = [res['time'] for res in existing]
    available = [slot for slot in all_slots if slot not in booked]
    
    return available

def get_user_session(phone_number):
    """Get or create user session"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'step': 'select_business',
            'data': {},
            'business_id': None
        }
    return user_sessions[phone_number]

def process_message(phone_number, message):
    """Main bot logic"""
    session = get_user_session(phone_number)
    step = session['step']
    data = session['data']
    msg = message.lower().strip()
    
    print(f"Phone: {phone_number} | Step: {step} | Msg: {msg}")
    
    # STEP 0: Select business
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
    
    # STEP 1: Initial
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
    
    # STEP 2: Service
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
    
    # STEP 3: Date
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
        
        # Check available slots
        available_slots = get_available_slots(session['business_id'], date_str)
        
        if not available_slots:
            return f"Nazalost, za {date_str} nema slobodnih termina.\n\nPokusajte s drugim datumom."
        
        slots_list = '\n'.join([
            f"{i+1}. {s}" for i, s in enumerate(available_slots)
        ])
        
        data['available_slots'] = available_slots
        
        return f"Datum: {date_str}\n\nSlobodni termini:\n\n{slots_list}\n\nOdaberite broj:"
    
    # STEP 4: Time
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
    
    # STEP 5: Name
    elif step == 'name':
        if len(message.strip()) >= 2:
            data['name'] = message.strip()
            session['step'] = 'phone'
            return f"Ime: {message}\n\nVas broj telefona:"
        return "Molim unesite vase ime."
    
    # STEP 6: Phone
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
    
    # STEP 7: Confirm
    elif step == 'confirm':
        if msg in ['da', 'yes', 'potvrdi']:
            try:
                # Double check availability
                available_slots = get_available_slots(session['business_id'], data['date'])
                
                if data['time'] not in available_slots:
                    return f"Termin {data['time']} je upravo zauzet!\n\nOdaberite drugi termin. Napisite 'termin'."
                
                # Save reservation
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

# ============================================
# MAIN ROUTES
# ============================================

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
    """Dashboard for salon"""
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
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial; padding: 40px; text-align: center;">
        <h1>WhatsApp Booking Bot</h1>
        <p>Bot je aktivan!</p>
        <h2>Salon Dashboards:</h2>
        {links if links else '<p>Nema biznisa.</p>'}
        <br><br>
        <a href="/admin" style="padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 8px;">Admin Panel</a>
    </body>
    </html>
    '''

# ============================================
# ADMIN PANEL
# ============================================

@app.route('/admin')
def admin_panel():
    """Admin panel"""
    password = request.args.get('password')
    
    if password != ADMIN_PASSWORD:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Login</title>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial; display: flex; justify-content: center; align-items: center; height: 100vh; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; }
                .login-box { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
                h2 { color: #667eea; margin-bottom: 20px; }
                input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 15px; font-size: 14px; box-sizing: border-box; }
                button { width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="login-box">
                <h2>Admin Login</h2>
                <form method="GET">
                    <input type="password" name="password" placeholder="Admin Password" required autofocus>
                    <button type="submit">Login</button>
                </form>
            </div>
        </body>
        </html>
        ''', 401
    
    businesses = list(clients_db.find({}))
    total_res = reservations.count_documents({})
    today = datetime.now().strftime('%d.%m.%Y')
    today_res = reservations.count_documents({'date': today})
    
    rows = ""
    for b in businesses:
        count = reservations.count_documents({'business_id': b['business_id']})
        status = "Aktivan" if b.get('active') else "Neaktivan"
        rows += f"""
        <tr>
            <td><strong>{b['name']}</strong></td>
            <td>{b['city']}</td>
            <td>{b['phone']}</td>
            <td>{count}</td>
            <td>{status}</td>
            <td><a href='/salon/{b["business_id"]}' target='_blank'>View</a></td>
            <td><a href='/admin/delete/{b["business_id"]}?password={password}' onclick='return confirm("Sigurno?")' style='color: red;'>Delete</a></td>
        </tr>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Panel</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial; padding: 20px; background: #f5f5f5; margin: 0; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; }}
            .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }}
            .stat-card {{ background: white; padding: 25px; border-radius: 10px; text-align: center; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            .stat-card h3 {{ margin: 0; font-size: 36px; color: #667eea; }}
            .panel {{ background: white; padding: 30px; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            .btn {{ padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 8px; display: inline-block; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background: #f8f9fa; padding: 15px; text-align: left; border-bottom: 2px solid #ddd; }}
            td {{ padding: 15px; border-bottom: 1px solid #eee; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Admin Panel</h1>
                <p>Upravljanje klijentima i rezervacijama</p>
            </div>
            
            <div class="stats">
                <div class="stat-card"><h3>{len(businesses)}</h3><p>Klijenata</p></div>
                <div class="stat-card"><h3>{len([b for b in businesses if b.get('active')])}</h3><p>Aktivni</p></div>
                <div class="stat-card"><h3>{total_res}</h3><p>Rezervacija</p></div>
                <div class="stat-card"><h3>{today_res}</h3><p>Danas</p></div>
            </div>
            
            <div class="panel">
                <a href="/admin/add?password={password}" class="btn">+ Dodaj klijenta</a>
                <table>
                    <tr><th>Naziv</th><th>Grad</th><th>Telefon</th><th>Rezervacije</th><th>Status</th><th>Dashboard</th><th>Akcije</th></tr>
                    {rows if rows else '<tr><td colspan="7" style="text-align:center;padding:40px;">Nema klijenata</td></tr>'}
                </table>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/admin/add')
def admin_add():
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return "Unauthorized", 401
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dodaj klijenta</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 700px; margin: 0 auto; background: white; padding: 40px; border-radius: 15px; }}
            h1 {{ color: #667eea; }}
            input, select, textarea {{ width: 100%; padding: 12px; margin: 8px 0 20px 0; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }}
            button {{ width: 100%; padding: 14px; background: #667eea; color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; }}
            label {{ font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Dodaj novog klijenta</h1>
            <form method="POST" action="/admin/save?password={password}">
                <label>Business ID:</label>
                <input type="text" name="business_id" required placeholder="salon_novi_zg">
                
                <label>Naziv:</label>
                <input type="text" name="name" required>
                
                <label>Grad:</label>
                <input type="text" name="city" required>
                
                <label>Adresa:</label>
                <input type="text" name="address" required>
                
                <label>Telefon:</label>
                <input type="tel" name="phone" required>
                
                <label>Email:</label>
                <input type="email" name="email">
                
                <label>Usluge (odvojene zarezom):</label>
                <input type="text" name="services" required placeholder="Sisanje, Farbanje">
                
                <label>Radno vrijeme:</label>
                <input type="text" name="working_hours" required placeholder="09:00-20:00">
                
                <label>Termini (odvojeni zarezom):</label>
                <input type="text" name="available_slots" required placeholder="09:00, 10:00, 11:00">
                
                <label>Aktivan:</label>
                <select name="active">
                    <option value="true">Da</option>
                    <option value="false">Ne</option>
                </select>
                
                <button type="submit">Spremi</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.route('/admin/save', methods=['POST'])
def admin_save():
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return "Unauthorized", 401
    
    try:
        data = {
            'business_id': request.form.get('business_id'),
            'name': request.form.get('name'),
            'city': request.form.get('city'),
            'address': request.form.get('address'),
            'phone': request.form.get('phone'),
            'email': request.form.get('email'),
            'services': [s.strip() for s in request.form.get('services').split(',')],
            'working_hours': request.form.get('working_hours'),
            'available_slots': [s.strip() for s in request.form.get('available_slots').split(',')],
            'active': request.form.get('active') == 'true',
            'created_at': datetime.utcnow()
        }
        
        clients_db.insert_one(data)
        return f"<html><head><meta charset='UTF-8'></head><body style='text-align:center;padding:40px;font-family:Arial'><h2>Klijent dodan!</h2><a href='/admin?password={password}'>Nazad na admin</a></body></html>"
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/admin/delete/<business_id>')
def admin_delete(business_id):
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return "Unauthorized", 401
    
    try:
        clients_db.delete_one({'business_id': business_id})
        reservations.delete_many({'business_id': business_id})
        return f"<html><head><meta charset='UTF-8'></head><body style='text-align:center;padding:40px;font-family:Arial'><h2>Klijent obrisan!</h2><a href='/admin?password={password}'>Nazad</a></body></html>"
    except Exception as e:
        return f"Error: {str(e)}", 500

# ============================================
# RUN APP
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)