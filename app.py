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
MERCHANT_URL = "https://karigar-server-new.onrender.com/api/v1/merchent/getAllMerchents"  # Renamed for clarity
ARCHITECT_URL="https://karigar-server-new.onrender.com/api/v1/architect/getAllArchitects"

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Directions not found. Please check the locations and try again."}), 404


#Fetch workers data from API
# Fetch workers data from API
def fetch_workers_from_api():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()  # Raise exception for HTTP errors
        workers_data = response.json()
        
        if workers_data.get('success'):
            workers = []
            client1 = googlemaps.Client(key=Google_Maps_KEY)
            
            for worker in workers_data.get('labors', []):
                is_available = worker.get('avalablity_status', False)
                
                if is_available:
                    location = worker.get('location')
                    worker_coords = None
                    
                    # Use existing latitude and longitude if available
                    if location and 'latitude' in location and 'longitude' in location:
                        worker_coords = (location['latitude'], location['longitude'])
                    else:
                        # Geocode the worker's address if location is missing
                        address = worker.get('address', {})
                        worker_address = f"{address.get('addressLine', '')}, {address.get('city', '')}, {address.get('state', '')}, {address.get('pincode', '')}"
                        geocode_results = client1.geocode(worker_address)
                        
                        if geocode_results:
                            worker_coords = (
                                geocode_results[0]['geometry']['location']['lat'],
                                geocode_results[0]['geometry']['location']['lng']
                            )
                        else:
                            # Skip worker if geocoding fails
                            continue
                    
                    # Get the worker's name safely
                    
                    # Append the worker with either the existing or geocoded coordinates
                    if worker_coords:
                        worker_name = worker.get('name')  # No need for default, just check presence
                        if not worker_name:
                            print(f"Warning: 'name' is missing for worker: {worker}")  # Log the worker for debugging
                            continue  # Skip this worker if no 'name' field is found
                    
                        workers.append({
                            'Id':worker.get('_id'),
                            'name': worker_name,  # Use fetched worker name
                            'service_category': worker.get('designation', 'Unknown'),  # Fallback to 'Unknown'
                            'location': worker_coords,
                            'ratePerHour': worker.get('ratePerHour', 'N/A'),  # Fallback to 'N/A'
                            'phone': worker.get('mobile_number', 'N/A'),  # Fallback to 'N/A'
                            'address': worker.get('address', {})  # Fallback to empty dict if missing
                        })
            return workers
        else:
            print("API response was not successful.")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching workers from API: {e}")
        return []


# Fetch architects data from API
def fetch_architects_from_api():
    try:
        response = requests.get(ARCHITECT_URL)
        response.raise_for_status()
        architects_data = response.json()

        # Check if the API response indicates success
        if architects_data.get('success'):
            architects = []
            client1 = googlemaps.Client(key=Google_Maps_KEY)

            # Iterate through 'architects' list from the API response
            for architect in architects_data.get('architects', []):
                is_available = architect.get('avalablity_status', False)

                # Only process available architects
                if is_available:
                    location = architect.get('location', {})
                    architect_coords = None

                    # Check if latitude and longitude are already provided
                    if location.get('latitude') and location.get('longitude'):
                        architect_coords = (location['latitude'], location['longitude'])
                    else:
                        # If coordinates are missing, attempt geocoding
                        address = architect.get('workplaceAddress', {})
                        # Safely construct the address
                        architect_address_parts = [
                            address.get('addressLine', '').strip(),
                            address.get('city', '').strip(),
                            address.get('state', '').strip(),
                            address.get('pincode', '').strip()
                        ]
                        # Filter out empty parts to avoid extra commas
                        architect_address = ', '.join(filter(None, architect_address_parts))

                        geocode_results = client1.geocode(architect_address)

                        if geocode_results:
                            architect_coords = (
                                geocode_results[0]['geometry']['location']['lat'],
                                geocode_results[0]['geometry']['location']['lng']
                            )
                        else:
                            # Skip architect if geocoding fails
                            continue

                    # Get the architect's name safely
                    architect_name = architect.get('name')
                    if not architect_name:
                        print(f"Warning: 'name' is missing for architect: {architect}")
                        continue  # Skip this architect if no 'name' field is found

                    # Append the architect with either the existing or geocoded coordinates
                    if architect_coords:
                        architects.append({
                            'Id': architect.get('_id'),  # Use the unique ID from the architect data
                            'name': architect_name,
                            'service_category': 'Architect',  # Default to 'Architect'
                            'location': architect_coords,
                            'email': architect.get('email', 'N/A'),
                            'phone': architect.get('mobile_number', 'N/A'),
                            'address': {
                                'addressLine': address.get('addressLine', 'N/A'),
                                'city': address.get('city', 'N/A'),
                                'state': address.get('state', 'N/A'),
                                'pincode': address.get('pincode', 'N/A'),
                            },
                            'ratePerHour': architect.get('ratePerHour', 0),  # Include hourly rate if needed
                            'experience': architect.get('experience', 0),  # Include experience if needed,
                            'profileImage':architect.get('profileImage',0),
                            'overall_rating': architect.get('overall_rating', 0),  # Include rating if needed
                        })
            return architects
        else:
            print("API response was not successful.")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching architects from API: {e}")
        return []




# nearby workers code:-
@app.post("/nearby_workers")
def get_nearby_workers():
    user_data = request.get_json()

    # Check for required field 'location'
    if 'location' not in user_data:
        abort(400, description="Bad Request. User's location is required.")

    # Geocode the user's location
    client1 = googlemaps.Client(key=Google_Maps_KEY)
    geocode_results = client1.geocode(user_data['location'])
    
    if not geocode_results:
        abort(404, description="Geocode results not found.")
    
    user_coords = (
        geocode_results[0]['geometry']['location']['lat'],
        geocode_results[0]['geometry']['location']['lng']
    )

    # Fetch workers data from the API
    workers = fetch_workers_from_api()
    nearby_workers = []

    # Check if 'service_category' is provided in user_data
    service_category = user_data.get('service_category')

    # Filter workers based on service category (if provided) and proximity
    for worker in workers:
        worker_coords = worker['location']

        # Calculate the distance between user and worker
        distance = haversine(user_coords, worker_coords, unit=Unit.KILOMETERS)
        
        if distance <= 10:  # Threshold for nearby workers (10 km)
            # If service_category is provided, filter by category
            if service_category:
                if worker['service_category'] == service_category:
                    worker['distance'] = distance
                    nearby_workers.append(worker)
            else:
                # If service_category is not provided, add all workers within distance
                worker['distance'] = distance
                nearby_workers.append(worker)

    return {'nearby_workers': nearby_workers}

# nearby architect code:-
@app.post("/nearby_architects")
def get_nearby_architects():
    user_data = request.get_json()

    # Check for required field 'location'
    if 'location' not in user_data:
        abort(400, description="Bad Request. User's location is required.")

    # Geocode the user's location
    client1 = googlemaps.Client(key=Google_Maps_KEY)
    geocode_results = client1.geocode(user_data['location'])
    
    if not geocode_results:
        abort(404, description="Geocode results not found.")

    user_coords = (
        geocode_results[0]['geometry']['location']['lat'],
        geocode_results[0]['geometry']['location']['lng']
    )

    # Fetch architect data from the API
    architects = fetch_architects_from_api()
    nearby_architects = []

    # Check if architects data is valid
    if not architects:
        abort(404, description="No architects found.")

    # Filter architects based on proximity
    for architect in architects:
        architect_coords = architect['location']
        
        # Ensure architect_coords is a tuple with lat/lng
        if not isinstance(architect_coords, tuple) or len(architect_coords) != 2:
            print(f"Invalid coordinates for architect {architect['Id']}: {architect_coords}")
            continue  # Skip this architect if coordinates are invalid

        # Calculate the distance between user and architect
        distance = haversine(user_coords, architect_coords, unit=Unit.KILOMETERS)
        
        if distance <= 50:  # Threshold for nearby architects (10 km)
            architect['distance'] = distance
            nearby_architects.append(architect)

    if not nearby_architects:
        return {'nearby_architects': [], 'message': 'No nearby architects found.'}

    return {'nearby_architects': nearby_architects}




# Fetch merchants data from API
def fetch_merchants_from_api():
    try:
        response = requests.get(MERCHANT_URL)  # Corrected URL
        response.raise_for_status()  # Raise exception for HTTP errors
        merchants_data = response.json()
        if merchants_data.get('success'):
            merchants = []
            client1 = googlemaps.Client(key=Google_Maps_KEY)
            for merchant in merchants_data.get('merchants', []):
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
                            'Id':merchant['_id'],
                            'location': merchant_coords,
                            'address': merchant['buisnessAddress'],
                            'buisnessName':merchent.get('buisnessName')
                        })
                    except KeyError as ke:
                        print(f"Missing address details for merchant {merchant['name']}: {ke}")
                else:
                    print(f"Merchant {merchant.get('name', 'Unknown')} does not have a business address.")
            return merchants
        else:
            print("API request was not successful.")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching merchants from API: {e}")
        return []



@app.post("/navigation")
def get_directions():
    user_data = request.get_json()
    if 'start_point' not in user_data or 'end_point' not in user_data:
        abort(400, message="Bad Request. 'start_point' and 'end_point' are required.")
    gmaps = googlemaps.Client(key=Google_Maps_KEY)
    # Assume start_pos is directly provided as latitude and longitude
    start_pos = user_data['start_point']  # Expecting a dictionary with 'lat' and 'lng' keys
    if not isinstance(start_pos, dict) or 'lat' not in start_pos or 'lng' not in start_pos:
        abort(400, message="Bad Request. 'start_point' must be a dictionary with 'lat' and 'lng' keys.")
    # Geocode the end_point
    end_results = gmaps.geocode(user_data['end_point'])
    if not end_results:
        abort(404, message="End point geocode results not found.")
    end_pos = (
        end_results[0]['geometry']['location']['lat'],
        end_results[0]['geometry']['location']['lng']
    )
    def get_distance(starting, ending):
        try:
            distance = haversine(starting, ending, unit=Unit.KILOMETERS)
            return distance
        except Exception as e:
            print(f"Error calculating distance: {e}")
            return None
    distance = get_distance((start_pos['lat'], start_pos['lng']), end_pos)
    def track_person(start, end):
        try:
            directions_result = gmaps.directions(
                origin=start,
                destination=end,
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
        abort(404, message="Directions not found. Please check the locations and try again.")
    return {'distance': distance, 'directions': direction}

@app.post('/nearby_merchants')
def nearby_merchants():
    user_data = request.get_json()
    if 'location' not in user_data:
        abort(400, message="Bad Request. User's location is required.")
    
    client1 = googlemaps.Client(key=Google_Maps_KEY)
    
    # Geocode the user's location
    geocode_results = client1.geocode(user_data['location'])
    if not geocode_results:
        print("Geocode results not found for user's location.")
        abort(404, message="Geocode results not found for user's location.")
    
    user_coords = (
        geocode_results[0]['geometry']['location']['lat'],
        geocode_results[0]['geometry']['location']['lng']
    )

    # Fetch merchants from API
    merchants = fetch_merchants_from_api()
    nearby_merchants = []
    
    for merchant in merchants:
        merchant_coords = merchant['location']
        
        # Calculate the distance between the user and the merchant
        distance = haversine(user_coords, merchant_coords, unit=Unit.KILOMETERS)
        
        if distance <= 10:  # Only include merchants within 10 kilometers
            merchant['distance'] = distance
            nearby_merchants.append(merchant)
    
    if not nearby_merchants:
        print("No merchants found within a 10 km radius.")
    
    return {"nearby_merchants": nearby_merchants}



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
