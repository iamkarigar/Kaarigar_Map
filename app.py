import os
import requests
from pymongo import MongoClient
from flask import Flask ,request
from flask_smorest import abort
from dotenv import load_dotenv
from olamaps import Client
from haversine import haversine, Unit
from geopy.distance import geodesic

load_dotenv()

app = Flask(__name__)
MONGODB_URI = os.getenv('MONGODB_URI')
OLA_MAPS_KEY = os.getenv('OLA_MAPS_KEY')
client = MongoClient(MONGODB_URI)
databases = client.list_database_names()
db = client['test']
labor_collection = db.get_collection('labors')
workers = []
for worker in labor_collection.find():
  if 'location' in worker and 'latitude' in worker['location'] and 'longitude' in worker['location']:

    workers.append({
            'name': worker['name'],
            'service_category': worker['designation'],
            'location': (worker['location']['latitude'], worker['location']['longitude']),
            'ratePerHour': worker['ratePerHour'],
            'phone': worker['phone'],
            'address': worker['address']
        })
    
@app.post("/nearby_workers")
def get_nearby_workers():
  user_data = request.get_json()
  if ('location' not in user_data or 'service_category'
      not in user_data):
      abort(404,message="Bad Request.Users location and service category not found.")
  all_workers= workers
  client1 = Client(api_key = OLA_MAPS_KEY)
  geocode_results = client1.geocode(user_data['location'])
  if not geocode_results:
        abort(404,"Geocode_results Not Found.")

  user_coords = (geocode_results[0]['geometry']['location']['lat'], geocode_results[0]['geometry']['location']['lng'])
  nearby_workers = []
  for worker in all_workers:
        if worker['service_category'] == user_data['service_category']:
            worker_coords = worker['location']
            distance = haversine(user_coords, worker_coords, unit=Unit.KILOMETERS)
            if distance <= 10:  # Example threshold for nearby workers (10 km)
                worker['distance'] = distance
                nearby_workers.append(worker)

  return {'nearby_workers':nearby_workers} 

@app.post("/navigation")
def get_directions():
    user_data = request.get_json()
    if 'start_point' not in user_data or 'end_point' not in user_data:
        abort(404, message="Bad Request. 'start_point' and 'end_point' are required.")
    client2 = Client(api_key=OLA_MAPS_KEY)
    def get_location(address):
        try:
          locations = client2.geocode(address)
          if locations:
              location = locations[0]['geometry']['location']
              return (location['lat'], location['lng'])
          else:
              raise ValueError(f"Could not find location for address: {address}")
        except Exception as e:
            print(f"Error in geocoding {address}: {e}")
            return None
    start_pos = get_location(user_data['start_point'])
    end_pos = get_location(user_data['end_point'])
    if not start_pos:
        abort(404, message=f"Could not find location for start point: {user_data['start_point']}")
    if not end_pos:
        abort(404, message=f"Could not find location for end point: {user_data['end_point']}")

    def get_distance(starting, ending):
        try:
          distance = geodesic(starting, ending).kilometers
          return distance
        except Exception as e:
           print(f"Error calculating distance: {e}")
           return None
    distance = get_distance(start_pos, end_pos)
    def track_person(start, end):
      url = f"https://api.olamaps.io/routing/v1/directions?origin={start[0]},{start[1]}&destination={end[0]},{end[1]}&api_key={OLA_MAPS_KEY}"
      try:
          response = requests.post(url)
          if response.status_code == 200:
              return response.json()
          else:
              raise Exception(f"Error fetching directions: {response.status_code}")
      except Exception as e:
          print(f"Error in tracking person: {e}")
          return None
    direction = track_person(start_pos, end_pos)
    if direction is None:
        abort(500, message="Could not retrieve directions from Ola Maps API.")


    return {'distance':distance, 'directions':direction}
