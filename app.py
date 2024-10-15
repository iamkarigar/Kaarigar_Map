import os
import requests
from flask import Flask, request, jsonify
from flask_smorest import abort
from dotenv import load_dotenv
import googlemaps
from haversine import haversine, Unit

load_dotenv()

app = Flask(__name__)
Google_Maps_KEY = os.getenv('Google_Maps_KEY')

API_URL = "https://karigar-server-new.onrender.com/api/v1/labor/getAllLabors"
url="https://karigar-server-new.onrender.com/api/v1/merchent/getAllMerchents"

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Directions not found. Please check the locations and try again."}), 404

# Fetch workers data from API
def fetch_workers_from_api():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()  # Raise an exception for HTTP errors
        workers_data = response.json()
        if workers_data['success']:
            workers = []
            client1 = googlemaps.Client(key=Google_Maps_KEY)
            for worker in workers_data['labors']:
                is_available = worker.get('avalablity_status', False) is True
                if is_available:
                    location = worker.get('location')
                    worker_coords = None
                    # Use existing latitude and longitude if available
                    if location and 'latitude' in location and 'longitude' in location:
                        worker_coords = (location['latitude'], location['longitude'])
                    else:
                        # Geocode the worker's address if location is missing
                        worker_address = f"{worker['address']['addressLine']}, {worker['address']['city']}, {worker['address']['state']},{worker['address']['pincode']}"
                        geocode_results = client1.geocode(worker_address)
                        
                        if geocode_results:
                            worker_coords = (
                                geocode_results[0]['geometry']['location']['lat'],
                                geocode_results[0]['geometry']['location']['lng']
                            )
                        else:
                            # Skip worker if geocoding fails
                            continue
                    
                    # Append the worker with either the existing or geocoded coordinates
                    if worker_coords:
                        workers.append({
                            'name': worker['name'],
                            'service_category': worker['designation'],
                            'location': worker_coords,
                            'ratePerHour': worker['ratePerHour'],
                            'phone': worker['mobile_number'],
                            'address': worker['address']
                        })
            return workers
        else:
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching workers from API: {e}")
        return []

def fetch_merchants_from_api():
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        merchants_data = response.json()
        if merchants_data['success']:
            merchants = []
            client1 = googlemaps.Client(key=Google_Maps_KEY)
            for merchant in merchants_data['merchants']:
                if 'buisnessAddress' in merchant:
                    try:
                        merchant_address = f"{merchant['buisnessAddress']['addressLine']}, {merchant['buisnessAddress']['city']}, {merchant['buisnessAddress']['state']} {merchant['buisnessAddress']['pincode']}"
                        print(f"Geocoding merchant {merchant['name']} with address: {merchant_address}")

                        # Geocode the merchant address
                        geocode_results = client1.geocode(merchant_address)
                        if geocode_results:
                            merchant_coords = (
                                geocode_results[0]['geometry']['location']['lat'],
                                geocode_results[0]['geometry']['location']['lng']
                            )
                            print(f"Geocoding successful for {merchant['name']}, Coordinates: {merchant_coords}")
                        else:
                            print(f"Geocoding failed for merchant {merchant['name']} at address: {merchant_address}")
                            continue

                        # Append the merchant with the geocoded coordinates
                        merchants.append({
                            'name': merchant['name'],
                            'location': merchant_coords,
                            'address': merchant['buisnessAddress']
                        })
                    except KeyError as ke:
                        print(f"Missing address details for merchant {merchant['name']}: {ke}")
                else:
                    print("does not have a buisnessAddress.")
            return merchants
        else:
            print("API request was not successful.")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching merchants from API: {e}")
        return []



@app.post("/nearby_workers")
def get_nearby_workers():
    user_data = request.get_json()
    if 'location' not in user_data or 'service_category' not in user_data:
        abort(404, message="Bad Request. User's location and service category are required.")
    
    # Geocode the user's location
    client1 = googlemaps.Client(key=Google_Maps_KEY)
    geocode_results = client1.geocode(user_data['location'])
    if not geocode_results:
        abort(404, "Geocode results not found.")
    
    user_coords = (
        geocode_results[0]['geometry']['location']['lat'], 
        geocode_results[0]['geometry']['location']['lng']
    )
    
    # Fetch workers data from the API
    workers = fetch_workers_from_api()
    nearby_workers = []

    for worker in workers:
        if worker['service_category'] == user_data['service_category']:
            # Calculate the distance between the user and the worker
            worker_coords = worker['location']
            distance = haversine(user_coords, worker_coords, unit=Unit.KILOMETERS)
            
            if distance <= 10:  # Example threshold for nearby workers (10 km)
                worker['distance'] = distance
                nearby_workers.append(worker)

    return {'nearby_workers': nearby_workers}



@app.post("/navigation")
def get_directions():
    user_data = request.get_json()
    if 'start_point' not in user_data or 'end_point' not in user_data:
        abort(404, description="Bad Request. 'start_point' and 'end_point' are required.")
    
    gmaps = googlemaps.Client(key=Google_Maps_KEY)

    # Assume start_pos is directly provided as latitude and longitude
    start_pos = user_data['start_point']  # Expecting a dictionary with 'lat' and 'lng' keys
    if not isinstance(start_pos, dict) or 'lat' not in start_pos or 'lng' not in start_pos:
        abort(404, description="Bad Request. 'start_point' must be a dictionary with 'lat' and 'lng' keys.")
    
    # Geocode the end_point
    end_pos = gmaps.geocode(user_data['end_point'])
    if not end_pos:
        abort(404)
    end_pos = (end_pos[0]['geometry']['location']['lat'], end_pos[0]['geometry']['location']['lng'])

    def get_distance(starting, ending):
        try:
            distance = geodesic(starting, ending).kilometers
            return distance
        except Exception as e:
            print(f"Error calculating distance: {e}")
            return None
    
    distance = get_distance((start_pos['lat'], start_pos['lng']), end_pos)
    
    def track_person(start, end):
        try:
            directions_result = gmaps.directions(
                origin=(start[0], start[1]),
                destination=(end[0], end[1]),
                mode='walking',
                departure_time='now'
            )
            if directions_result:
                return directions_result
            else:
                raise Exception("No directions found.")
        except Exception as e:
            print(f"Error in tracking person: {e}")
            return None
    
    direction = track_person((start_pos['lat'], start_pos['lng']), end_pos)
    if direction is None:
        abort(404, description="Directions not found. Please check the locations and try again.")
    
    return {'distance': distance, 'directions': direction}

@app.post('/nearby_merchants')
def nearby_merchants():
    user_data = request.get_json()
    if 'location' not in user_data:
        abort(404, message="Bad Request. User's location and service category are required.")
    client1 = googlemaps.Client(key=Google_Maps_KEY)
    geocode_results = client1.geocode(user_data['location'])
    if not geocode_results:
        print("Geocode results not found for user's location.")
        return []

    user_coords = (
        geocode_results[0]['geometry']['location']['lat'],
        geocode_results[0]['geometry']['location']['lng']
    )

    # Fetch merchants from API
    merchants = fetch_merchants_from_api()
    nearby_merchants = []
    for merchant in merchants:
        merchant_coords = merchant['location']
        distance = haversine(user_coords, merchant_coords, unit=Unit.KILOMETERS)
        if distance <= 10:  # Only include merchants within 10 kilometers
            merchant['distance'] = distance
            nearby_merchants.append(merchant)
    return {"nearby_merchants":nearby_merchants}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
