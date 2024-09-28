from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests
import json
from datetime import datetime

load_dotenv()

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True)
    print(data)
    
    # Extract the intent name and the user question
    intent_name = data['queryResult']['intent']['displayName']
    question = data['queryResult']['queryText']


    accountID = ""
    callID = ""
    callerID = ""
    scenarioID = ""


    # Call ibookRestaurant function to get response payload
    payload = ibookRestaurant_DWI(accountID, callID, callerID, scenarioID)
    
    print(payload)
    
    # Handle the intent based on the payload and question
    if intent_name == 'Default Welcome Intent':
        return respond_based_on_reservation_status(payload)
    
    elif intent_name == 'Yes - Alter Reservation':
        return handle_alter_reservation('yes', payload)
    
    elif intent_name == 'No - Alter Reservation':
        return handle_alter_reservation('no', payload)
    
    elif intent_name == 'Reservation':
        return handle_reservation(data, payload)
    
    elif intent_name == 'Prefered_meal':
        return handle_prefered_meal(data)
    
    elif intent_name == 'Reservation - custom':
        return  jsonify({'fulfillmentText': "Ci sono bambini che necessitano di seggiolone?"})
    
    elif intent_name == 'No-Children' or intent_name == 'yes-children':
        return handle_maxpeople_location(data, payload)
    
    elif intent_name == 'Outdoor-location' or intent_name == 'Indoor-location':
        return check_availability(data, payload)
    
    elif intent_name == 'Collect-Name':
        return confirmation_reservation(data,payload)
    
    elif intent_name == 'Collect_Name_FW':
        return confirmation_reservation_FW(data,payload)

    # Default fallback if intent is not matched
    return jsonify({'fulfillmentText': "Scusa, non l'ho capito."})


def get_sentence(payload, sentence_type):
    sentences = payload.get('sentences', [])
    for sentence in sentences:
        if sentence['type'] == sentence_type:
            return sentence['sentence']
    return None

def respond_based_on_reservation_status(payload):
    customer = payload.get('customer', {})
    reservation_status = payload.get('openReservations', [])
    
    greetings = customer.get('greetings', '')
    title = customer.get('title', '')
    last_name = customer.get('lastName', '')

    # Get the appropriate sentence templates
    book_sentence = get_sentence(payload, 'book')
    is_open_reservation_sentence = get_sentence(payload, 'isOpenReservation')
    # if is_open_reservation_sentence:
    #     is_open_reservation_sentence = is_open_reservation_sentence.replace('{{', '{').replace('}}', '}')
    #     print(is_open_reservation_sentence)
    
    
    if reservation_status:
        
        num_reservations = len(reservation_status)
        
        if num_reservations == 1:
            reservation = reservation_status[0]
            print(reservation)
            
            # Formatting the isOpenReservation sentence with reservation data
            formatted_sentence = is_open_reservation_sentence.format(
                greetings=greetings,
                title=title,
                surname=last_name,
                dwName=reservation.get('dwName', ''),
                dayName=reservation.get('dayName', ''),
                monthName=reservation.get('monthName', ''),
                time=reservation.get('time', ''),
                covers=reservation.get('covers', '')
            )
            response_text = formatted_sentence
            return jsonify({
                "fulfillmentMessages": [
                        {
                            "text": {
                                "text": [
                                    response_text
                                ]
                            }
                        },
                        {
                            "payload": {
                                "richContent": [
                                    [
                                        {
                                            "title": "Choose from below.."
                                        },
                                        {
                                            "options": [
                                                {
                                                    "text": "sì"
                                                },
                                                {
                                                    "text": "no grazie"
                                                }
                                            ],
                                            "type": "chips"
                                        }
                                    ]
                                ]
                            }
                        }
                    ]
            })
        
        else:
            response_text = (
                f"{greetings}, {title} {last_name}, Vedo che ci sono più prenotazioni. Vuoi modificarne una?"
            )
            return jsonify({
                "fulfillmentMessages": [
                        {
                            "text": {
                                "text": [
                                    response_text
                                ]
                            }
                        },
                        {
                            "payload": {
                                "richContent": [
                                    [
                                        {
                                            "title": "Choose from below.."
                                        },
                                        {
                                            "options": [
                                                {
                                                    "text": "si"
                                                },
                                                {
                                                    "text": "no grazie"
                                                }
                                            ],
                                            "type": "chips"
                                        }
                                    ]
                                ]
                            }
                        }
                    ]
            })

    else:
        # No reservations found, provide booking sentence
        response_text = (
            book_sentence or f"{greetings}, {title} {last_name}, when would you like to book your reservation?"
        )

        return jsonify({'fulfillmentText': response_text})
    
    


def handle_alter_reservation(user_input, payload):
    """
    Handle the user's response to whether they want to alter an existing reservation.
    """
    reservation_status = check_existing_reservations(payload)
    
    if user_input.lower() == 'yes':
        if len(reservation_status['reservations']) > 1:
            return jsonify({'fulfillmentText': handle_multiple_reservations(payload)})
        else:
            edit_reservation_sentence = get_sentence(payload, 'editReservation')
            return jsonify({
                'fulfillmentText': edit_reservation_sentence or "Please click the Edit Reservation button in WA message we sent you."
            })
    else:
        book_sentence = get_sentence(payload, 'book')
        return jsonify({
            'fulfillmentText': book_sentence or "Great! When do you want to book?"
        })


def handle_multiple_reservations(payload):
    """
    Handle multiple reservations and provide details to the user.
    """
    open_reservations = payload['openReservations']
    response = "Hai le seguenti riserve:\n"
    
    for idx, reservation in enumerate(open_reservations, start=1):
        response += f"{idx}. Date: {reservation['dwName']}, {reservation['dayName']} {reservation['monthName']}, Time: {reservation['time']}, Covers: {reservation['covers']}\n"
    
    response += "Per modificare una prenotazione, fai clic sul pulsante MODIFICA PRENOTAZIONE nel messaggio WhatsApp che ti abbiamo inviato al momento della prenotazione"
    return response


def check_existing_reservations(payload):
    """
    Check if there are any existing reservations in the payload.
    """
    open_reservations = payload['openReservations']
    
    if open_reservations:
        return {'has_reservations': True, 'reservations': open_reservations}
    else:
        return {'has_reservations': False}

def handle_prefered_meal(data):

    user_date = data['queryResult']['parameters'].get('date')
    user_meal = data['queryResult']['parameters'].get('Meal')
    if user_meal == 'pranzo' or user_meal == 'Cena':
        return {
            "followupEventInput": {
                "name": "required_params",
                "parameters": {"Meal": user_meal ,'date' : user_date},
                "languageCode": "it"
            }
        }

def handle_reservation(data, payload):
    """
    Handle the reservation intent, checking the user's provided date and meal preference.
    """
    user_date = data['queryResult']['parameters'].get('date')  # User-provided date
    
    session = data.get('session')
    project_id = session.split('/')[1]
    session_id = session.split('/')[3]
    
    

    if user_date:
        user_date = user_date.split('T')[0]
        bookable_days = payload.get('bookableDays', [])
        
        if exceeds_booking_days(user_date, bookable_days):
            tooforth_sentence = get_sentence(payload, 'tooforth')
            return {
                # "fulfillmentText": tooforth_sentence or "Sorry, I'm not authorized to accept bookings this far in advance. Please call 99999 or do you prefer to be called back ASAP?"
            "fulfillmentMessages": [
                        {
                            "text": {
                                "text": [
                                    tooforth_sentence or "Mi spiace, non sono autorizzata a raccogliere una prenotazione così distante: Posso farla richiamare il prima possibile?"
                                ]
                            }
                        },
                        {
                            "payload": {
                                "richContent": [
                                    [
                                        {
                                            "title": "Choose from below.."
                                        },
                                        {
                                            "options": [
                                                {
                                                    "text": "Richiamare"
                                                },
                                                {
                                                    "text": "Esentato/a"
                                                }
                                            ],
                                            "type": "chips"
                                        }
                                    ]
                                ]
                            }
                        }
                    ]
            
            
            
            }
         
        meal_preference = data['queryResult']['parameters'].get('meal')
        if not is_day_open(user_date, bookable_days):
            fulfillment_text = get_fulfillment_text(user_date, bookable_days)
            date = format_date_info(user_date,bookable_days)
            # other_day_sentence = get_sentence(payload, 'fulfillmentText')
            return {
                
                "fulfillmentMessages": [
                        {
                            "text": {
                                "text": [
                                    fulfillment_text or f"Apologies, we're closed on {date}. Would you like to select another date?"
                                ]
                            }
                        },
                        {
                            "payload": {
                                "richContent": [
                                    [
                                        {
                                            "title": "Choose from below.."
                                        },
                                        {
                                            "options": [
                                                {
                                                    "text": "cambiare data"
                                                },
                                                {
                                                    "text": "Esentato/a"
                                                }
                                            ],
                                            "type": "chips"
                                        }
                                    ]
                                ]
                            }
                        }
                    ]
            }
        
        available_meals = get_available_meals(user_date, bookable_days)
        if len(available_meals) > 1:
            meal_options = ', '.join(available_meals)
            date = format_date_info(user_date,bookable_days)
            # Dynamically generate chips based on available meal options
            chips = [{"text": meal} for meal in available_meals]
    
            return {
                # "fulfillmentText": f"We are open for {meal_options} on {date}. Which meal would you prefer?",
                "fulfillmentMessages": [
                    {
                        "text": {
                            "text": [
                                f"Siamo aperti per {meal_options} il {date}. Quale pasto preferiresti?"
                            ]
                        }
                    },
                    {
                        "payload": {
                            "richContent": [
                                [
                                    {
                                        "type": "chips",
                                        "options": chips
                                    }
                                ]
                            ]
                        }
                    }
                ]
            }
        
        if meal_preference and not is_meal_open(user_date, meal_preference, bookable_days):
            other_day_sentence = get_sentence(payload, 'otherDay')
            date = format_date_info(user_date,bookable_days)
            return {

                "fulfillmentMessages": [
                        {
                            "text": {
                                "text": [
                                    other_day_sentence or f"Apologies, we're closed for {meal_preference} on {date}. Would you like to select another date?"
                                ]
                            }
                        },
                        {
                            "payload": {
                                "richContent": [
                                    [
                                        {
                                            "title": "Choose from below.."
                                        },
                                        {
                                            "options": [
                                                {
                                                    "text": "cambiare data"
                                                },
                                                {
                                                    "text": "Esentato/a"
                                                }
                                            ],
                                            "type": "chips"
                                        }
                                    ]
                                ]
                            }
                        }
                    ]
            }
        
        return {
            "followupEventInput": {
                "name": "required_params",
                "parameters": {"date": user_date},
                "languageCode": "it"
            }
        }


def exceeds_booking_days(user_date, bookable_days):
    """
    Check if the user-provided date is within the allowed booking range.
    """
    booking_dates = [day['date'] for day in bookable_days]
    return user_date not in booking_dates


def is_day_open(user_date, bookable_days):
    """
    Check if the provided date is available for booking.
    """
    for day in bookable_days:
        if day['date'] == user_date:
            return day['isDayOpen'] == 1
    return False


def is_meal_open(user_date, meal, bookable_days):
    """
    Check if a specific meal (lunch or dinner) is open for booking on the given date.
    """
    meal_key = f'is{meal.capitalize()}Open'
    for day in bookable_days:
        if day['date'] == user_date:
            return day.get(meal_key, 0) == 1
    return False

def confirmation_reservation(data,payload):
    time_param = data['queryResult']['parameters']['time']
    date = data['queryResult']['parameters']['date']
    user_date = date.split('T')[0] if date else ''
    adult_count = data['queryResult']['parameters'].get('adult_count', 0)
    child_count = data['queryResult']['parameters'].get('child_count', 0)
    phone = payload.get('customer', {}).get("phone")
    person_count = int(adult_count + float(child_count))
    schedule = data['queryResult']['parameters'].get('schedule', '')
    meal = data['queryResult']['parameters'].get('meal', '')
    
    print(meal)
    bookable_days = payload.get('bookableDays', [])
    date = format_date_info(user_date, bookable_days)

    # Extract time from 'time' parameter
    time_str = time_param.split('T')[1][:5] if time_param else ''
    # print(time_str,time_obj)

    return{ 
        "fulfillmentText": f"Prenotazione confermata per {person_count} persone il {date} per {schedule} alle {time_str}. Grazie! Dovresti aver ricevuto un messaggio WhatsApp con tutti i dettagli al seguente numero {phone}."
        }

def confirmation_reservation_FW(data,payload):
    time_param = data['queryResult']['parameters']['time']
    date = data['queryResult']['parameters']['date']
    user_date = date.split('T')[0] if date else ''
    adult_count = data['queryResult']['parameters'].get('adult_count', 0)
    child_count = data['queryResult']['parameters'].get('child_count', 0)
    phone = payload.get('customer', {}).get("phone")
    person_count = int(adult_count + float(child_count))
    schedule = data['queryResult']['parameters'].get('schedule', '')
    meal = data['queryResult']['parameters'].get('meal', '')
    
    print(meal)
    bookable_days = payload.get('bookableDays', [])
    date = format_date_info(user_date, bookable_days)

    # Extract time from 'time' parameter
    time_str = time_param.split('T')[1][:5] if time_param else ''
    # print(time_str,time_obj)

    return{ 
        "fulfillmentText": f"Attesa confermata per {person_count} persone il {date} per {schedule} alle {time_str}. Grazie! Dovresti aver ricevuto un messaggio WhatsApp con tutti i dettagli al seguente numero {phone}."
        }


def format_date_info(user_date, bookable_days):
    for day_info in bookable_days:  # Use 'day_info' to avoid conflict with the 'day' key
        if day_info['date'] == user_date:
            day_name = day_info['dayName']  # Day of the week, e.g., "Tuesday"
            day_number = day_info['day']  # Day number, e.g., 17
            month_name = day_info['monthName']  # Month name, e.g., "September"
    
            formatted_date = f"{day_name}, {month_name} {day_number}"
        
            return formatted_date



def get_fulfillment_text(user_date, bookable_days):
    """
    Get the appropriate fulfillment text for the given user date.
    """
    date = format_date_info(user_date,bookable_days)
    for day in bookable_days:
        if day['date'] == user_date:
            if not day['isDayOpen']:
                return day.get('fulfillmentText', f"Ci scusiamo, siamo chiusi il giorno {date}. Desideri selezionare un altro giorno?")
    return None

def get_available_meals(user_date, bookable_days):
    """
    Get a list of available meals (lunch/dinner) for the given date.
    """
    for day in bookable_days:
        if day['date'] == user_date:
            available_meals = []
            if day.get('isLunchOpen', 0) == 1:
                available_meals.append('Pranzo')
            if day.get('isDinnerOpen', 0) == 1:
                available_meals.append('Cena')
            return available_meals
    return []

def handle_maxpeople_location(req,payload):
    
    
    # Extract adult, child, and max_people count from the request
    adult_count = req.get("queryResult", {}).get("parameters", {}).get("adult_count", 0)
    child_count = req.get("queryResult", {}).get("parameters", {}).get("child_count", 0)
    user_date = req['queryResult']['parameters'].get('date')
    user_date = user_date.split('T')[0]
    user_date = datetime.strptime(user_date, '%Y-%m-%d')
    max_people = payload.get("customer", {}).get("maxBookable", 6)  # Default to 6 if not provided
    locations = payload.get("locations", [])
    # Calculate total people (adults + children)
    total_people = adult_count + float(child_count)

    # Check if the total people exceed the max people allowed
    if total_people > int(max_people):
        # Get the "toomany" response from the payload (if present)
        tooMany = get_sentence(payload, 'tooMany')

        # Return the response in Dialogflow's format
        
    
        return {
               
            "fulfillmentMessages": [
                        {
                            "text": {
                                "text": [
                                    #tooMany or 
                                    "Mi scuso, non sono autorizzato a gestire una prenotazione così grande. Posso chiederti di richiamarti al più presto?"
                                ]
                            }
                        },
                        {
                            "payload": {
                                "richContent": [
                                    [
                                        {
                                            "title": "Choose from below.."
                                        },
                                        {
                                            "options": [
                                                {
                                                    "text": "Richiamare"
                                                },
                                                {
                                                    "text": "Esentato/a"
                                                }
                                            ],
                                            "type": "chips"
                                        }
                                    ]
                                ]
                            }
                        }
                    ]
            
            
            
            }
    else:
        available_locations = []
        for location in locations:
            date_from = datetime.strptime(location['dateFrom'], '%Y-%m-%d')
            date_to = datetime.strptime(location['dateTo'], '%Y-%m-%d')
            if date_from <= user_date <= date_to:
                available_locations.append(location)
        
        if len(available_locations) > 1:
            # Create a list of available location names
            location_names = [location['name'] for location in available_locations]
            # Format the location options into a string
            location_options = ", ".join(location_names)
            chips = [{"text": location} for location in location_names]

            # Ask the user for their preferred location
            return {
                "fulfillmentMessages": [
                    {
                        "text": {
                            "text": [
                                f"Abbiamo {location_options} sedi disponibili per la data selezionata. Quale località preferisci?"
                            ]
                        }
                    },
                    {
                        "payload": {
                        "richContent": [
                                [
                                    {
                                        "type": "chips",
                                        "options": chips
                                    }
                                ]
                            ]
                        }
                    }
                ]
            }
        elif len(available_locations) == 1:
            location_name = available_locations[0]['name']
            chips = [{"text": location_name}, {"text": 'Change date'}]

            return {
                "fulfillmentMessages": [
                    {
                        "text": {
                            "text": [
                                f"Abbiamo la sede {location_name} disponibile per la data selezionata. Vuoi continuare?"
                            ]
                        }
                    },
                    {
                        "payload": {
                            "richContent": [
                                [
                                    {
                                        "type": "chips",
                                        "options": chips
                                    }
                                ]
                            ]
                        }
                    }
                ]
            }
        else:
            # No locations available for the selected date
            return {
                "fulfillmentMessages": [
                    {
                        "text": {
                            "text": [
                                "Non abbiamo alcuna sede disponibile per la data selezionata. Vorresti cambiare la data?"
                            ]
                        }
                    },
                    {
                        "payload": {
                            "richContent": [
                                [
                                    {
                                        "type": "chips",
                                        "options": [{"text": 'Cambia data'}]
                                    }
                                ]
                            ]
                        }
                    }
                ]
            }
        
def get_id_by_name(payload, name, entity_type):
    
    entities = payload.get(entity_type, [])
    for entity in entities:
        if entity['name'].lower() == name.lower():
            return entity.get('mealId') if entity_type == 'meals' else entity.get('locationId')
    return None

def process_time(selected_time_str):
    # Parse the datetime string
    selected_time = datetime.fromisoformat(selected_time_str)
    # Extract and return the formatted time
    return selected_time.strftime('%H:%M')

def check_availability(req, payload):
    # Extract required parameters from the request
    user_date = req['queryResult']['parameters'].get('date')
    user_date = user_date.split('T')[0]
    selected_time = req['queryResult']['parameters'].get("time")
    selected_time = process_time(selected_time)
    selected_location = req['queryResult']['parameters'].get("location")
    adult_count = req['queryResult']['parameters'].get("adult_count", 0)
    child_count = req['queryResult']['parameters'].get("child_count", 0)
    selected_meal = req['queryResult']['parameters'].get("Meal")

    locationID = get_id_by_name(payload, selected_location, 'locations')
    mealID = get_id_by_name(payload, selected_meal, 'meals')
    accountID = ""
    payload_ca = ibookRestaurant_CA(accountID, locationID, mealID, user_date, adult_count,child_count)
    
    people_count = adult_count + float(child_count)

    # Convert selected time to seconds (assuming 24-hour format)
    from datetime import datetime
    selected_time_seconds = datetime.strptime(selected_time, "%H:%M").hour * 3600 + datetime.strptime(selected_time, "%H:%M").minute * 60

    # Extract location data from the payload
    locations = payload_ca.get("locations", [])

    if selected_location == "Interno":
        selected_location = "Indoor"
    elif selected_location == "Esterno":
        selected_location = "Outdoor"
    else:
        selected_location

    # Find selected location
    selected_location_data = None
    for loc in locations:
        if loc['locationName'].lower() == selected_location.lower():
            selected_location_data = loc
            break
    if not selected_location_data:
        return {"fulfillmentMessages": [{"text": {"text": ["Località selezionata non disponibile."]}}]}

    # Check slot availability in the selected location
    available_slots = selected_location_data.get("availability", [])
    print (available_slots)
    matching_slots = []
    
    for slot in available_slots:
        slot_start_time = slot['startTime']
        slot_end_time = slot['endTime']
        print(selected_time_seconds)
        if slot_start_time <= selected_time_seconds <= slot_end_time:
            # Check if the slot is sold out or if the people count exceeds the available capacity
            if slot['soldOut'] == 0 and people_count <= slot['totalCovers']:
                matching_slots.append(slot['slotName'] if 'slotName' in slot else slot.get('shiftName', 'No Slot Name'))
                
                return {
                "fulfillmentMessages": [
                    {
                        "text": {
                            "text": ["Ottimo, puoi lasciare il tuo nome, per favore?"]
                        }
                    }
                ]
            }

    
    if not matching_slots:
        # All matching slots are either sold out or people count exceeds the capacity
        # Check if there are alternative slots
        alternative_slots = [slot for slot in available_slots if slot['soldOut'] == 0 and people_count <= slot['totalCovers']]
        print(alternative_slots)
        if not alternative_slots:
            # No available slots, prompt for waiting list
            print("inside")
            return {
                "fulfillmentMessages": [
                    {
                        "text": {"text": ["siamo spiacenti, siamo al completo: ma se vuoi ti mettiamo in Lista d'Attesa?"]}
                    },
                    {
                        "payload": {
                            "richContent": [
                                [{"options": [{"text": "certo"}, {"text": "cambiare data"}], "type": "chips"}]
                            ]
                        }
                    }
                ]
            }
        else:
            # Offer alternative time slots
            print("inside2")
            alt_times = [
                    slot['slotName'] if 'slotName' in slot else slot.get('shiftName', 'No Slot Name')
                    for slot in alternative_slots
                ]

            return {
                "fulfillmentMessages": [
                    {
                        "text": {"text": [f"Siamo spiacenti, l'orario selezionato è al completo. Gli orari disponibili sono: {', '.join(alt_times)}."]}
                    },
                    {
                        "payload": {
                            "richContent": [
                                [{"options": [{"text": time} for time in alt_times], "type": "chips"}]
                            ]
                        }
                    }
                ]
            }
    else:
        # Slot is available for booking
        return {
            "fulfillmentMessages": [
                {
                    "text": {"text": "Grande! Puoi lasciarmi il tuo nome, per favore?"}
                }
            ]
        }





def ibookRestaurant_DWI(accountID, callID, callerID, scenarioID):
    """
    Simulate the API call to fetch the reservation details.
    """
    try:
        url = ""
        payload = json.dumps({
        
        "queryResult": {
            "intent": {
            "displayName": ""
            },
            "queryText": {
            "accountId": accountID,
            "callId": callID,
            "callerId": callerID,
            "scenarioId": scenarioID
            }
        }
        

        })
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=payload)

        # Print the status code and response text for debugging
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")

        # Check if the response is in JSON format
        try:
            return response.json()
        except ValueError:
            print("Response is not in JSON format.")
            return {}

    except Exception as e:
        print(f"Exception: {e}")
        return {}


def ibookRestaurant_CA(accountID, locationID, mealID, Date, Covers,Children):
    """
    Simulate the API call to fetch the reservation details.
    """
    try:
        url = ""
        payload = json.dumps({
            "queryResult": {
                "intent": {
                    "displayName": ""
                },
                "queryText": {
                    "accountId": accountID,
                    "locationId": locationID,
                    "mealId": mealID,
                    "date": Date,
                    "covers": Covers,
                    "children": Children
                }
            }
        }
        )
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=payload)

        # Print the status code and response text for debugging
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")

        # Check if the response is in JSON format
        try:
            return response.json()
        except ValueError:
            print("Response is not in JSON format.")
            return {}

    except Exception as e:
        print(f"Exception: {e}")
        return {}

if __name__ == '__main__':
    app.run(debug=True)
