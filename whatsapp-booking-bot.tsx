import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, Calendar, Clock, User, Phone, Store, CheckCircle, X } from 'lucide-react';

export default function WhatsAppBookingDemo() {
  const [messages, setMessages] = useState([
    { type: 'bot', text: 'Pozdrav! 👋 Dobrodošli u sustav rezervacija.\n\nZa rezervaciju termina napišite "rezervacija" ili "termin".\nZa radno vrijeme napišite "radno vrijeme".', time: '10:00' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [currentStep, setCurrentStep] = useState('initial');
  const [bookingData, setBookingData] = useState({});
  const messagesEndRef = useRef(null);

  const businessConfig = {
    name: 'Frizerski Salon Elegance',
    services: ['Šišanje', 'Farbanje', 'Feniranje', 'Manikura'],
    workingHours: '09:00 - 20:00',
    availableSlots: ['09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '17:00']
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addBotMessage = (text, delay = 800) => {
    setTimeout(() => {
      const botMsg = {
        type: 'bot',
        text: text,
        time: new Date().toLocaleTimeString('hr-HR', { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, botMsg]);
    }, delay);
  };

  const handleUserMessage = (userMessage) => {
    const lowerMsg = userMessage.toLowerCase().trim();
    
    console.log('Current step:', currentStep);
    console.log('User message:', userMessage);

    switch (currentStep) {
      case 'initial':
        if (lowerMsg.includes('rezerv') || lowerMsg.includes('termin') || lowerMsg.includes('naruč')) {
          setCurrentStep('service');
          addBotMessage(`Odlično! Nudimo sljedeće usluge:\n\n${businessConfig.services.map((s, i) => `${i + 1}. ${s}`).join('\n')}\n\nOdaberite broj usluge (1-4) ili napišite naziv:`);
        } else if (lowerMsg.includes('radno') || lowerMsg.includes('vrijeme') || lowerMsg.includes('kada')) {
          addBotMessage(`Naše radno vrijeme je ${businessConfig.workingHours}, radnim danima i subotom.`);
        } else {
          addBotMessage('Za rezervaciju termina napišite "rezervacija" ili "termin".\nZa informacije o radnom vremenu napišite "radno vrijeme".');
        }
        break;

      case 'service':
        let selectedService = null;
        
        // Check if number
        const serviceNum = parseInt(lowerMsg);
        if (serviceNum >= 1 && serviceNum <= businessConfig.services.length) {
          selectedService = businessConfig.services[serviceNum - 1];
        } else {
          // Check if service name mentioned
          businessConfig.services.forEach(service => {
            if (lowerMsg.includes(service.toLowerCase())) {
              selectedService = service;
            }
          });
        }

        if (selectedService) {
          setBookingData(prev => ({ ...prev, service: selectedService }));
          setCurrentStep('date');
          addBotMessage(`✅ Odabrali ste: ${selectedService}\n\nZa koji datum želite rezervirati termin?\n(npr. 15.12.2024 ili "sutra")`);
        } else {
          addBotMessage('Molim vas odaberite broj usluge (1-4) ili napišite naziv usluge iz liste.', 500);
        }
        break;

      case 'date':
        const datePattern = /\d{1,2}\.\d{1,2}\.?\d{0,4}/;
        if (datePattern.test(userMessage) || lowerMsg.includes('sutra') || lowerMsg.includes('danas')) {
          setBookingData(prev => ({ ...prev, date: userMessage }));
          setCurrentStep('time');
          addBotMessage(`✅ Datum: ${userMessage}\n\nDostupni termini:\n\n${businessConfig.availableSlots.map((slot, i) => `${i + 1}. ${slot}`).join('\n')}\n\nOdaberite broj (1-7) ili napišite vrijeme:`);
        } else {
          addBotMessage('Molim unesite datum u formatu DD.MM.YYYY (npr. 15.12.2024) ili napišite "sutra".', 500);
        }
        break;

      case 'time':
        let selectedTime = null;
        
        const timeNum = parseInt(lowerMsg);
        if (timeNum >= 1 && timeNum <= businessConfig.availableSlots.length) {
          selectedTime = businessConfig.availableSlots[timeNum - 1];
        } else {
          businessConfig.availableSlots.forEach(slot => {
            if (userMessage.includes(slot)) {
              selectedTime = slot;
            }
          });
        }

        if (selectedTime) {
          setBookingData(prev => ({ ...prev, time: selectedTime }));
          setCurrentStep('name');
          addBotMessage(`✅ Vrijeme: ${selectedTime}\n\nKako se zovete?`, 500);
        } else {
          addBotMessage('Molim odaberite broj termina (1-7) ili napišite vrijeme (npr. 14:00).', 500);
        }
        break;

      case 'name':
        if (userMessage.trim().length >= 2) {
          setBookingData(prev => ({ ...prev, name: userMessage.trim() }));
          setCurrentStep('phone');
          addBotMessage(`✅ Ime: ${userMessage.trim()}\n\nMolim vas unesite vaš broj telefona:`, 500);
        } else {
          addBotMessage('Molim unesite vaše ime (najmanje 2 znaka).', 400);
        }
        break;

      case 'phone':
        const phoneClean = userMessage.replace(/\s/g, '').replace(/\+/g, '');
        if (phoneClean.length >= 9 && /^\d+$/.test(phoneClean)) {
          const finalData = { ...bookingData, phone: userMessage.trim() };
          setBookingData(finalData);
          setCurrentStep('confirm');
          addBotMessage(`✅ PREGLED REZERVACIJE:\n\n🏪 ${businessConfig.name}\n💇 Usluga: ${finalData.service}\n📅 Datum: ${finalData.date}\n🕐 Vrijeme: ${finalData.time}\n👤 Ime: ${finalData.name}\n📞 Telefon: ${finalData.phone}\n\n➡️ Potvrdite rezervaciju:\nNapišite "DA" za potvrdu ili "NE" za odustajanje`, 700);
        } else {
          addBotMessage('Molim unesite ispravan broj telefona (samo brojevi, najmanje 9 znamenki).', 500);
        }
        break;

      case 'confirm':
        if (lowerMsg === 'da' || lowerMsg === 'yes' || lowerMsg === 'potvrđujem' || lowerMsg === 'potvrdi') {
          setCurrentStep('completed');
          addBotMessage('🎉 REZERVACIJA USPJEŠNO POTVRĐENA!\n\n✅ Dobit ćete SMS potvrdu na uneseni broj.\n✅ Ako trebate otkazati, javite se najmanje 24h prije.\n\nHvala što koristite naše usluge!\n\n➡️ Za novu rezervaciju napišite "rezervacija"', 800);
        } else if (lowerMsg === 'ne' || lowerMsg === 'no' || lowerMsg === 'odustani') {
          setCurrentStep('initial');
          setBookingData({});
          addBotMessage('❌ Rezervacija je otkazana.\n\nZa novu rezervaciju napišite "rezervacija".', 600);
        } else {
          addBotMessage('Molim odgovorite sa "DA" za potvrdu ili "NE" za odustajanje.', 400);
        }
        break;

      case 'completed':
        if (lowerMsg.includes('rezerv') || lowerMsg.includes('termin') || lowerMsg.includes('nova')) {
          setCurrentStep('service');
          setBookingData({});
          addBotMessage(`Nova rezervacija!\n\nNudimo sljedeće usluge:\n\n${businessConfig.services.map((s, i) => `${i + 1}. ${s}`).join('\n')}\n\nOdaberite broj usluge (1-4):`, 600);
        } else if (lowerMsg.includes('radno') || lowerMsg.includes('vrijeme')) {
          addBotMessage(`Naše radno vrijeme je ${businessConfig.workingHours}, radnim danima i subotom.\n\nZa novu rezervaciju napišite "rezervacija".`, 500);
        } else {
          addBotMessage('Za novu rezervaciju napišite "rezervacija" ili "termin".', 500);
        }
        break;

      default:
        addBotMessage('Došlo je do greške. Napišite "rezervacija" za ponovni početak.', 500);
        setCurrentStep('initial');
        setBookingData({});
    }
  };

  const sendMessage = () => {
    const trimmedInput = inputValue.trim();
    if (!trimmedInput) return;

    // Add user message
    const userMsg = {
      type: 'user',
      text: trimmedInput,
      time: new Date().toLocaleTimeString('hr-HR', { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInputValue('');

    // Process bot response
    handleUserMessage(trimmedInput);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <MessageCircle className="text-green-600" size={32} />
            <h1 className="text-2xl font-bold text-gray-800">WhatsApp Chatbot - Demo Rezervacija</h1>
          </div>
          <p className="text-gray-600">
            Interaktivni demo sustava za automatske rezervacije putem WhatsApp-a
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Chat Interface */}
          <div className="bg-white rounded-lg shadow-lg overflow-hidden flex flex-col" style={{ height: '600px' }}>
            {/* Chat Header */}
            <div className="bg-green-600 text-white p-4 flex items-center gap-3">
              <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center">
                <Store className="text-green-600" size={24} />
              </div>
              <div>
                <div className="font-semibold">{businessConfig.name}</div>
                <div className="text-xs text-green-100">Online • Bot radi ✓</div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 bg-gray-50 space-y-3">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-xs ${msg.type === 'user' ? 'bg-green-500 text-white' : 'bg-white text-gray-800 border border-gray-200'} rounded-lg p-3 shadow`}>
                    <div className="whitespace-pre-line text-sm">{msg.text}</div>
                    <div className={`text-xs mt-1 ${msg.type === 'user' ? 'text-green-100' : 'text-gray-500'}`}>
                      {msg.time}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t p-4 bg-white">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Napišite poruku..."
                  className="flex-1 border border-gray-300 rounded-full px-4 py-2 focus:outline-none focus:border-green-500"
                  autoFocus
                />
                <button
                  onClick={sendMessage}
                  className="bg-green-600 text-white rounded-full w-10 h-10 flex items-center justify-center hover:bg-green-700 transition"
                >
                  ➤
                </button>
              </div>
              <div className="text-xs text-gray-500 mt-2 text-center">
                Korak: {currentStep === 'initial' ? 'Početak' : currentStep === 'service' ? 'Odabir usluge' : currentStep === 'date' ? 'Unos datuma' : currentStep === 'time' ? 'Odabir vremena' : currentStep === 'name' ? 'Unos imena' : currentStep === 'phone' ? 'Unos telefona' : currentStep === 'confirm' ? 'Potvrda' : 'Završeno'}
              </div>
            </div>
          </div>

          {/* Info Panel */}
          <div className="space-y-6">
            {/* Business Info */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
                <Store className="text-green-600" size={20} />
                Informacije o poslovanju
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <Clock size={16} className="text-gray-500" />
                  <span>Radno vrijeme: {businessConfig.workingHours}</span>
                </div>
                <div className="mt-3">
                  <div className="font-semibold mb-1">Usluge:</div>
                  <ul className="list-disc list-inside text-gray-600">
                    {businessConfig.services.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* Current Booking */}
            {Object.keys(bookingData).length > 0 && (
              <div className="bg-green-50 rounded-lg shadow-lg p-6 border-2 border-green-200">
                <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
                  <Calendar className="text-green-600" size={20} />
                  Trenutna rezervacija
                </h3>
                <div className="space-y-2 text-sm">
                  {bookingData.service && (
                    <div className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-green-600 mt-0.5" />
                      <span><strong>Usluga:</strong> {bookingData.service}</span>
                    </div>
                  )}
                  {bookingData.date && (
                    <div className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-green-600 mt-0.5" />
                      <span><strong>Datum:</strong> {bookingData.date}</span>
                    </div>
                  )}
                  {bookingData.time && (
                    <div className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-green-600 mt-0.5" />
                      <span><strong>Vrijeme:</strong> {bookingData.time}</span>
                    </div>
                  )}
                  {bookingData.name && (
                    <div className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-green-600 mt-0.5" />
                      <span><strong>Ime:</strong> {bookingData.name}</span>
                    </div>
                  )}
                  {bookingData.phone && (
                    <div className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-green-600 mt-0.5" />
                      <span><strong>Telefon:</strong> {bookingData.phone}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Quick Test Guide */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h3 className="font-bold text-lg mb-3 text-blue-900">🚀 Brzi test:</h3>
              <ol className="list-decimal list-inside space-y-2 text-sm text-blue-800">
                <li>Napišite <strong>"rezervacija"</strong></li>
                <li>Napišite broj <strong>"1"</strong> (za šišanje)</li>
                <li>Napišite <strong>"sutra"</strong></li>
                <li>Napišite <strong>"1"</strong> (za 09:00)</li>
                <li>Napišite vaše ime npr. <strong>"Marko"</strong></li>
                <li>Napišite broj npr. <strong>"0911234567"</strong></li>
                <li>Napišite <strong>"da"</strong></li>
              </ol>
            </div>

            {/* Features */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="font-bold text-lg mb-4">Značajke sustava</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-start gap-2">
                  <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                  <span>Automatska obrada rezervacija 24/7</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                  <span>Provjera dostupnih termina u realnom vremenu</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                  <span>SMS potvrda rezervacije</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                  <span>Podrška za više usluga</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                  <span>Integracija s Google Calendar</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}