import json
import os
import requests
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, UserUtteranceReverted
from google.colab import userdata

# External API keys
DUFFEL_TOKEN = userdata.get('DUFFEL_TOKEN')
CLIMATIQ_KEY = userdata.get('CLIMATIQ_KEY')


# this helps us find the mock data files
def get_mock_path(filename):
    my_folder = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(my_folder, "mock_data", filename)
    return full_path


# lookup table: airport code for different city
city_codes = {
    "paris": "CDG",
    "london": "LHR",
    "berlin": "BER",
    "amsterdam": "AMS",
    "barcelona": "BCN",
    "rome": "FCO",
    "tokyo": "NRT",
    "new york": "JFK",
    "vienna": "VIE",
    "lisbon": "LIS",
    "stockholm": "ARN",
    "copenhagen": "CPH",
    "oslo": "OSL",
    "zurich": "ZRH",
    "prague": "PRG",
    "dublin": "DUB",
    "munich": "MUC",
    "milan": "MXP",
    "madrid": "MAD",
    "helsinki": "HEL",
}

#lookup table: lat/lng coordinates for cities
city_coords = {
    "paris": {"lat": 48.8566, "lng": 2.3522},
    "london": {"lat": 51.5074, "lng": -0.1278},
    "berlin": {"lat": 52.5200, "lng": 13.4050},
    "amsterdam": {"lat": 52.3676, "lng": 4.9041},
    "barcelona": {"lat": 41.3874, "lng": 2.1686},
    "rome": {"lat": 41.9028, "lng": 12.4964},
    "tokyo": {"lat": 35.6762, "lng": 139.6503},
    "new york": {"lat": 40.7128, "lng": -74.0060},
    "vienna": {"lat": 48.2082, "lng": 16.3738},
    "lisbon": {"lat": 38.7223, "lng": -9.1393},
    "stockholm": {"lat": 59.3293, "lng": 18.0686},
    "copenhagen": {"lat": 55.6761, "lng": 12.5683},
    "oslo": {"lat": 59.9139, "lng": 10.7522},
    "zurich": {"lat": 47.3769, "lng": 8.5417},
    "prague": {"lat": 50.0755, "lng": 14.4378},
    "dublin": {"lat": 53.3498, "lng": -6.2603},
    "munich": {"lat": 48.1351, "lng": 11.5820},
    "milan": {"lat": 45.4642, "lng": 9.1900},
    "madrid": {"lat": 40.4168, "lng": -3.7038},
    "helsinki": {"lat": 60.1699, "lng": 24.9384},
}



#search for flights using the Duffel API

class ActionSearchFlights(Action):

    def name(self) -> Text:
        return "action_search_flights"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # get the destination the user said
        destination = tracker.get_slot("destination")
        travel_dates = tracker.get_slot("travel_dates")

        # check we actually have a destination
        if destination is None:
            dispatcher.utter_message(text="Which city do you want to go?")
            return []

        # look up for the airport code of the destination city
        dest_code = city_codes.get(destination.lower())

        # if airport code is not known, show mock data
        if dest_code is None:
            dispatcher.utter_message(text="I do not currently have flight info for that city. Here are some sample flights for your reference:"))
            self.show_mock_flights(dispatcher)
            return []

        # flights go from Berlin
        origin_code = "BER"

        # get the date - use a default if the user didn't say
        travel_date = "2026-08-01"
        if travel_dates is not None:
            travel_date = travel_dates.split(" ")[0]

        # call the Duffel API to search for flights
        print("Calling Duffel flight search API...")
        try:
            my_headers = {
                "Authorization": "Bearer " + DUFFEL_TOKEN,
                "Duffel-Version": "v2",
                "Content-Type": "application/json",
            }

            # build the search request
            my_payload = {
                "data": {
                    "slices": [
                        {
                            "origin": origin_code,
                            "destination": dest_code,
                            "departure_date": travel_date,
                        }
                    ],
                    "passengers": [{"type": "adult"}],
                    "cabin_class": "economy",
                }
            }

             #sending the request to Duffel API
            response = requests.post(
                "https://api.duffel.com/air/offer_requests",
                json=my_payload,
                headers=my_headers,
                params={"return_offers": "true"}, #return_offers=true means we get the flight offers back right away
                timeout=15,
            )

            api_result = response.json()

            #checking if info about flights are received from Duffel
            if "data" in api_result and "offers" in api_result["data"]:
                offers_list = api_result["data"]["offers"]

                if len(offers_list) > 0:
                    message = "Here are some flights I found:\n\n"

                    # show the first 3 results
                    for i in range(min(3, len(offers_list))):
                        one_offer = offers_list[i]
                        airline = one_offer["owner"]["name"]
                        price = one_offer["total_amount"]
                        currency = one_offer["total_currency"]
                        departs = one_offer["slices"][0]["segments"][0]["departing_at"]
                        num_stops = len(one_offer["slices"][0]["segments"]) - 1

                        message = message + "Flight " + str(i + 1) + ": " + airline + "\n"
                        message = message + "   Route: " + origin_code + " to " + dest_code + "\n"
                        message = message + "   Price: " + str(price) + " " + currency + "\n"
                        message = message + "   Departs: " + str(departs) + "\n"
                        if num_stops == 0:
                            message = message + "   Direct flight\n\n"
                        else:
                            message = message + "   Stops: " + str(num_stops) + "\n\n"

                    dispatcher.utter_message(text=message)
                    return []
                else:
                    print("Duffel returned no offers for this route")
            else:
                print("Unexpected response from Duffel:", api_result)

        except Exception as e:
            print("Duffel API call failed: " + str(e))

        # if the API didn't work, fall back to mock data
        dispatcher.utter_message(text="I couldn't connect to the live flight search. Here are some sample options:")
        self.show_mock_flights(dispatcher)
        return []

    def show_mock_flights(self, dispatcher):
        try:
            mock_file = get_mock_path("flights.json")
            with open(mock_file, "r") as f:
                data = json.load(f)

            message = "Sample flights:\n\n"
            for i in range(min(3, len(data["flights"]))):
                flight = data["flights"][i]
                message = message + "Flight " + str(i + 1) + ": " + flight["airline"] + "\n"
                message = message + "   Route: " + flight["route"] + "\n"
                message = message + "   Price: " + str(flight["price"]) + " EUR\n"
                message = message + "   Duration: " + flight["duration"] + "\n"
                message = message + "   CO2: " + str(flight["co2_kg"]) + " kg\n\n"

            dispatcher.utter_message(text=message)
        except Exception as e:
            print("Could not load mock flights: " + str(e))
            dispatcher.utter_message(text="Sorry I couldn't load any flight data at the moment.")



#search for eco-friendly hotels using Duffel hotel API
class ActionSearchHotels(Action):

    def name(self) -> Text:
        return "action_search_hotels"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        #get the destination and travel date info from the user
        destination = tracker.get_slot("destination")
        travel_dates = tracker.get_slot("travel_dates")

        if destination is None:
            dispatcher.utter_message(text="Where are you looking for a hotel? Tell me the city.")
            return []

        #get the location coordinates for the mentioned city
        coords = city_coords.get(destination.lower())

        #if coordinates are not available, use the mock data
        if coords is None:
            dispatcher.utter_message(text="I don't have hotel data for that city. Here are some eco-friendly options:")
            self.show_mock_hotels(dispatcher, destination)
            return []

        # work out check-in and check-out dates
        check_in = "2026-08-01"
        check_out = "2026-08-05"
        if travel_dates is not None:
            #try to get both dates from the slot value
            parts = travel_dates.replace(" to ", " ").replace(" - ", " ").split()
            if len(parts) >= 1:
                check_in = parts[0]
            if len(parts) >= 2:
                check_out = parts[-1]

        # call the Duffel stays search API
        print("Calling Duffel hotel search API...")
        try:
            my_headers = {
                "Authorization": "Bearer " + DUFFEL_TOKEN,
                "Duffel-Version": "v2",
                "Content-Type": "application/json",
            }

            # the Duffel stays search needs location coordinates and dates
            my_payload = {
                "data": {
                    "rooms": 1,
                    "guests": [{"type": "adult"}],
                    "check_in_date": check_in,
                    "check_out_date": check_out,
                    "location": {
                        "radius": 5,
                        "geographic_coordinates": {
                            "latitude": coords["lat"],
                            "longitude": coords["lng"],
                        },
                    },
                }
            }

            response = requests.post(
                "https://api.duffel.com/stays/search",
                json=my_payload,
                headers=my_headers,
                timeout=15,
            )

            api_result = response.json()

            #Returning list of hotels from Duffel 
            if "data" in api_result and isinstance(api_result["data"], list) and len(api_result["data"]) > 0:
                hotels_list = api_result["data"]
                message = "Here are some hotels I found in " + destination + ":\n\n"

                for i in range(min(3, len(hotels_list))):
                    one_hotel = hotels_list[i]
                    hotel_name = one_hotel["accommodation"]["name"]
                    cheapest = one_hotel.get("cheapest_rate_total_amount", "N/A")
                    currency = one_hotel.get("cheapest_rate_currency", "")

                    message = message + "Hotel " + str(i + 1) + ": " + hotel_name + "\n"
                    message = message + "   From: " + str(cheapest) + " " + currency + " per night\n\n"

                dispatcher.utter_message(text=message)
                return []
            else:
                print("Duffel returned no hotels for this location")

        except Exception as e:
            print("Duffel hotel API call failed: " + str(e))

        #in case API doesn't work, show mock hotel data 
        dispatcher.utter_message(text="Sorry I couldn't connect to the live hotel search right now. Here are some eco-friendly options:")
        self.show_mock_hotels(dispatcher, destination)
        return []

    def show_mock_hotels(self, dispatcher, destination):
        try:
            mock_file = get_mock_path("hotels.json")
            with open(mock_file, "r") as f:
                all_hotels = json.load(f)

            # try to find hotels for the right city
            matched = []
            for hotel in all_hotels:
                if destination.lower() in hotel["destination"].lower():
                    matched.append(hotel)

            # if nothing matched, just show the first 3
            if len(matched) == 0:
                matched = all_hotels[:3]

            message = "Eco-friendly hotels in " + destination + ":\n\n"
            for hotel in matched:
                features = hotel["sustainability_features"][0] + ", " + hotel["sustainability_features"][1]
                message = message + "Hotel: " + hotel["name"] + " (" + str(hotel["stars"]) + " stars)\n"
                message = message + "   Certification: " + hotel["eco_certification"] + "\n"
                message = message + "   Price: " + str(hotel["price_per_night"]) + " EUR per night\n"
                message = message + "   Green features: " + features + "\n\n"

            dispatcher.utter_message(text=message)
        except Exception as e:
            print("Could not load mock hotels: " + str(e))
            dispatcher.utter_message(text="Sorry I couldn't load any hotel data right now.")



#calculate carbon footprint using Climatiq API

class ActionCalculateCarbon(Action):

    def name(self) -> Text:
        return "action_calculate_carbon"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        destination = tracker.get_slot("destination")

        if destination is None:
            dispatcher.utter_message(text="Tell me the destination to calculate the carbon footprint.")
            return []

        #list of roughly estimated distances from Berlin in km - used if the API is unavailable
        distances = {
            "paris": 400,
            "london": 950,
            "berlin": 0,
            "amsterdam": 400,
            "barcelona": 1150,
            "rome": 1550,
            "tokyo": 11270,
            "new york": 5670,
            "vienna": 1290,
            "lisbon": 1510,
            "stockholm": 1230,
            "copenhagen": 950,
            "oslo": 1090,
            "zurich": 880,
            "prague": 1030,
        }

        #get the distance for this city (default to 1000 km if not in the list)
        distance = distances.get(destination.lower(), 1000)

        #try to call Climatiq for accurate numbers
        try:
            climatiq_url = "https://api.climatiq.io/estimate"
            my_headers = {
                "Authorization": "Bearer " + CLIMATIQ_KEY,
                "Content-Type": "application/json",
            }

            #asking Climatiq for the flight carbon emission info
            flight_body = {
                "emission_factor": {
                    "activity_id": "passenger_flight-route_type_domestic-aircraft_type_na-distance_na-class_na-rf_included",
                    "source": "BEIS",
                    "region": "GB",
                    "year": 2023,
                    "source_lca_activity": "upstream-fuel_combustion",
                    "data_version": "^6"
                },
                "parameters": {
                    "distance": distance,
                    "distance_unit": "km"
                }
            }

            flight_response = requests.post(climatiq_url, headers=my_headers, json=flight_body)
            flight_data = flight_response.json()
            flight_co2 = flight_data.get("co2e", distance * 0.255)

            #asking Climatiq for the train carbon emission info
            train_body = {
                "emission_factor": {
                    "activity_id": "passenger_train-route_type_international_rail-fuel_source_na",
                    "source": "BEIS",
                    "region": "GB",
                    "year": 2023,
                    "source_lca_activity": "upstream-fuel_combustion",
                    "data_version": "^6"
                },
                "parameters": {
                    "distance": distance,
                    "distance_unit": "km"
                }
            }

            train_response = requests.post(climatiq_url, headers=my_headers, json=train_body)
            train_data = train_response.json()
            train_co2 = train_data.get("co2e", distance * 0.041)

            # build the message with the results
            message = "Carbon footprint for travelling to " + destination + " (" + str(distance) + " km):\n\n"
            message = message + "Flying:  " + str(round(flight_co2, 1)) + " kg CO2\n"
            message = message + "Train:   " + str(round(train_co2, 1)) + " kg CO2\n"
            message = message + "Car:     " + str(round(distance * 0.171, 1)) + " kg CO2\n"
            message = message + "Bus:     " + str(round(distance * 0.089, 1)) + " kg CO2\n\n"

            if flight_co2 > 100:
                message = message + "Flying has a HIGH carbon impact on this route.\n"
                message = message + "Train or bus are much greener options!"

            dispatcher.utter_message(text=message)
            return []

        except Exception as e:
            print("Climatiq API failed: " + str(e))
            # just use the rough estimates instead
            return self.use_estimates(dispatcher, destination, distance)

    def use_estimates(self, dispatcher, destination, distance):
        # these are average CO2 numbers per km per person from BEIS data
        flight_co2 = round(distance * 0.255, 1)
        train_co2 = round(distance * 0.041, 1)
        car_co2 = round(distance * 0.171, 1)
        bus_co2 = round(distance * 0.089, 1)

        message = "Estimated carbon footprint for " + destination + " (" + str(distance) + " km):\n\n"
        message = message + "Flying:  " + str(flight_co2) + " kg CO2\n"
        message = message + "Train:   " + str(train_co2) + " kg CO2\n"
        message = message + "Car:     " + str(car_co2) + " kg CO2\n"
        message = message + "Bus:     " + str(bus_co2) + " kg CO2\n\n"

        if flight_co2 > 100:
            message = message + "Flying has a HIGH carbon impact on this route.\n"
            message = message + "Train or bus are much greener options!"

        dispatcher.utter_message(text=message)
        return []



#recommendation of the best options based on a scoring formula

class ActionRecommendOptions(Action):

    def name(self) -> Text:
        return "action_recommend_options"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        destination = tracker.get_slot("destination")
        budget = tracker.get_slot("budget")
        sustainability = tracker.get_slot("sustainability_preference")

        if destination is None:
            dispatcher.utter_message(text="I need a destination to make recommendations.")
            return []

        #asking how much the user cares about the environment to distribute the sustainability preference weight and price weight.
        if sustainability is not None and sustainability.lower() in ["high", "eco-friendly", "green", "sustainable"]:
            carbon_weight = 0.7
            price_weight = 0.3
        elif sustainability is not None and sustainability.lower() in ["low", "not a priority"]:
            carbon_weight = 0.3
            price_weight = 0.7
        else:
            carbon_weight = 0.5
            price_weight = 0.5

        try:
            # load the flight mock data to score
            mock_file = get_mock_path("flights.json")
            with open(mock_file, "r") as f:
                flights_data = json.load(f)

            scored_list = []
            for flight in flights_data["flights"]:
                #score out of 1 - lower price and lower carbon = higher score and vice versa
                price_score = 1 - (flight["price"] / 1000)
                carbon_score = 1 - (flight["co2_kg"] / 500)
                total_score = (carbon_weight * carbon_score) + (price_weight * price_score)

                #decide on a colour label for the emission level
                if flight["co2_kg"] < 50:
                    colour = "LOW EMISSION"
                elif flight["co2_kg"] < 150:
                    colour = "MODERATE EMISSION"
                else:
                    colour = "HIGH EMISSION"

                scored_list.append({
                    "name": flight["airline"] + " - " + flight["route"],
                    "price": flight["price"],
                    "co2": flight["co2_kg"],
                    "score": total_score,
                    "colour": colour,
                    "duration": flight["duration"],
                })

            # sort so the best option comes first
            scored_list.sort(key=lambda x: x["score"], reverse=True)

            message = "Here are my top recommendations for you:\n"
            message = message + "(Scoring: " + str(int(carbon_weight * 100)) + "% sustainability, "
            message = message + str(int(price_weight * 100)) + "% price)\n\n"

            for i in range(min(3, len(scored_list))):
                option = scored_list[i]
                if i == 0:
                    message = message + "Best option: " + option["name"] + "\n"
                else:
                    message = message + "Option " + str(i + 1) + ": " + option["name"] + "\n"
                message = message + "   " + option["colour"] + "\n"
                message = message + "   Price: " + str(option["price"]) + " EUR\n"
                message = message + "   CO2: " + str(option["co2"]) + " kg\n"
                message = message + "   Duration: " + option["duration"] + "\n"
                message = message + "   Score: " + str(round(option["score"], 2)) + "\n\n"

            message = message + "Would you like more details or shall I connect you with a travel advisor?"

            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "More Details", "payload": "/ask_eco_trip"},
                    {"title": "Talk to Advisor", "payload": "/request_human_advisor"},
                    {"title": "Thank You", "payload": "/thank_you"},
                ]
            )

        except Exception as e:
            print("Error in recommend options: " + str(e))
            dispatcher.utter_message(text="Sorry I couldn't generate recommendations right now. Would you like to talk to a human advisor?")

        return []


#transfering the conversation to human advisor when asked by user
class ActionHumanHandover(Action):

    def name(self) -> Text:
        return "action_human_handover"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        #information collected during conversation
        destination = tracker.get_slot("destination")
        travel_dates = tracker.get_slot("travel_dates")
        budget = tracker.get_slot("budget")
        sustainability = tracker.get_slot("sustainability_preference")
        trip_type = tracker.get_slot("trip_type")

        # use "Not specified" if information is missing
        if destination is None:
            destination = "Not specified"
        if travel_dates is None:
            travel_dates = "Not specified"
        if budget is None:
            budget = "Not specified"
        if sustainability is None:
            sustainability = "Not specified"
        if trip_type is None:
            trip_type = "Not specified"

        #get the last few messages to understand the context of the conversation
        recent = []
        for event in tracker.events[-10:]:
            if event.get("event") == "user":
                recent.append("User: " + event.get("text", ""))
            elif event.get("event") == "bot":
                recent.append("Bot: " + event.get("text", "")[:100])

        #handover message
        message = "TRANSFERRING TO HUMAN ADVISOR\n"
        message = message + "=" * 40 + "\n\n"
        message = message + "Conversation Summary:\n"
        message = message + "   Trip Type:   " + trip_type + "\n"
        message = message + "   Destination: " + destination + "\n"
        message = message + "   Dates:       " + travel_dates + "\n"
        message = message + "   Budget:      " + budget + " EUR\n"
        message = message + "   Eco Pref:    " + sustainability + "\n\n"
        message = message + "Recent messages:\n"

        for msg in recent[-5:]:
            message = message + "   " + msg + "\n"

        message = message + "\n" + "=" * 40 + "\n"
        message = message + "A human advisor will review this and get back to you soon.\n"
        message = message + "Thank you for your patience!\n"

        dispatcher.utter_message(text=message)
        return []


#fallback when the bot doesn't understand
class ActionDefaultFallback(Action):

    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

         #counting number of times fallback is trigerred recetntly
        fallback_count = 0
        for event in tracker.events[-6:]:
            if event.get("event") == "action" and event.get("name") == "action_default_fallback":
                fallback_count = fallback_count + 1

        if fallback_count > 1:
            #offering to connect with a human
            dispatcher.utter_message(
                text="I'm still having trouble understanding. Would you like me to connect you with a human travel advisor?",
                buttons=[
                    {"title": "Yes please", "payload": "/request_human_advisor"},
                    {"title": "Let me try again", "payload": "/greet"},
                ]
            )
        else:
            #showing some quick reply buttons to help 
            dispatcher.utter_message(
                text="Sorry I didn't understand that. Did you mean one of these?",
                buttons=[
                    {"title": "Plan a Trip", "payload": "/ask_eco_trip"},
                    {"title": "Check Carbon Footprint", "payload": "carbon_footprint"},
                    {"title": "Find Hotels", "payload": "/ask_accommodation"},
                    {"title": "Talk to an Advisor", "payload": "/request_human_advisor"},
                ]
            )

        return [UserUtteranceReverted()]
