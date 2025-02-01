import math
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import folium
import json
import uvicorn
import os

app = FastAPI()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fixed store location
STORE_LAT = 19.075887
STORE_LON = 72.877911

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def compute_mst(points):
    n = len(points)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            dist = haversine(points[i][0], points[i][1], points[j][0], points[j][1])
            edges.append((dist, i, j))
    edges.sort()
    parent = list(range(n))
    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u
    def union(u, v):
        u_root = find(u)
        v_root = find(v)
        if u_root != v_root:
            parent[v_root] = u_root
    mst_sum = 0
    mst_edges = []
    for edge in edges:
        dist, u, v = edge
        if find(u) != find(v):
            union(u, v)
            mst_sum += dist
            mst_edges.append(edge)
            if len(mst_edges) == n - 1:
                break
    return mst_sum

def convert_time_to_minutes(time_str):
    return int(time_str.split(':')[0]) * 60 + int(time_str.split(':')[1])

def tsp_nearest_neighbor(points):
    n = len(points)
    visited = [False] * n
    path = [0]
    visited[0] = True
    current = 0
    for _ in range(n - 1):
        nearest_dist = float('inf')
        nearest_idx = -1
        for i in range(n):
            if not visited[i]:
                dist = haversine(points[current][0], points[current][1], points[i][0], points[i][1])
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_idx = i
        if nearest_idx == -1:
            break
        path.append(nearest_idx)
        visited[nearest_idx] = True
        current = nearest_idx
    path.append(0)
    return path

def check_capacity_constraints(num_shipments, vehicle_capacity):
    min_shipments = math.ceil(vehicle_capacity * 0.5)
    max_shipments = vehicle_capacity
    return min_shipments <= num_shipments <= max_shipments

def optimize_routes(shipments_data):
    shipments = []
    print("-------------------------------------")
    print(type(shipments_data))
    print(shipments_data)

    for shipment in shipments_data:
        start, end = shipment['delivery_timeslot'].split('-')
        shipments.append({
            'id': shipment['shipment_id'],
            'lat': shipment['latitude'],
            'lon': shipment['longitude'],
            'start': convert_time_to_minutes(start.strip()),
            'end': convert_time_to_minutes(end.strip())
        })

    vehicles = [
        {'type': '3W', 'remaining': 50, 'capacity': 5, 'max_radius': 15},
        {'type': '4W-EV', 'remaining': 25, 'capacity': 8, 'max_radius': 20},
        {'type': '4W', 'remaining': float('inf'), 'capacity': 25, 'max_radius': float('inf')}
    ]

    shipments.sort(key=lambda x: x['start'])
    timeslot_groups = {}
    for shipment in shipments:
        key = (shipment['start'], shipment['end'])
        if key not in timeslot_groups:
            timeslot_groups[key] = []
        timeslot_groups[key].append(shipment)

    trips = []

    for (start_time, end_time), group_shipments in timeslot_groups.items():
        current_batch = []
        
        for shipment in group_shipments:
            current_batch.append(shipment)
            
            for vehicle in vehicles:
                if vehicle['remaining'] <= 0:
                    continue
                    
                if check_capacity_constraints(len(current_batch), vehicle['capacity']):
                    points = [(STORE_LAT, STORE_LON)] + [(s['lat'], s['lon']) for s in current_batch]
                    mst_dist = compute_mst(points)
                    
                    if mst_dist <= vehicle['max_radius'] or vehicle['type'] == '4W':
                        trip_time = (mst_dist * 5) + (len(current_batch) * 10)
                        available_time = end_time - start_time
                        
                        if trip_time <= available_time:
                            trips.append({
                                'shipments': current_batch.copy(),
                                'start': start_time,
                                'end': end_time,
                                'mst_dist': mst_dist,
                                'vehicle': vehicle['type'],
                                'vehicle_capacity': vehicle['capacity'],
                                'vehicle_max_radius': vehicle['max_radius']
                            })
                            vehicle['remaining'] -= 1
                            current_batch = []
                            break
        
        if current_batch:
            for vehicle in vehicles:
                if vehicle['remaining'] <= 0:
                    continue
                
                if len(current_batch) <= vehicle['capacity']:
                    points = [(STORE_LAT, STORE_LON)] + [(s['lat'], s['lon']) for s in current_batch]
                    mst_dist = compute_mst(points)
                    
                    if mst_dist <= vehicle['max_radius'] or vehicle['type'] == '4W':
                        trips.append({
                            'shipments': current_batch.copy(),
                            'start': start_time,
                            'end': end_time,
                            'mst_dist': mst_dist,
                            'vehicle': vehicle['type'],
                            'vehicle_capacity': vehicle['capacity'],
                            'vehicle_max_radius': vehicle['max_radius']
                        })
                        vehicle['remaining'] -= 1
                        current_batch = []
                        break

    for trip in trips:
        points = [(STORE_LAT, STORE_LON)] + [(s['lat'], s['lon']) for s in trip['shipments']]
        path = tsp_nearest_neighbor(points)
        shipment_indices = path[1:-1]
        ordered_shipments = [trip['shipments'][i-1] for i in shipment_indices]
        trip['shipments'] = ordered_shipments

    output_data = []
    for idx, trip in enumerate(trips):
        trip_time = (trip['mst_dist'] * 5) + (len(trip['shipments']) * 10)
        available_time = trip['end'] - trip['start']
        time_uti = trip_time / available_time if available_time != 0 else 0
        capacity_uti = len(trip['shipments']) / trip['vehicle_capacity']
        cov_uti = trip['mst_dist'] / trip['vehicle_max_radius'] if trip['vehicle_max_radius'] != float('inf') else 'N/A'
        
        for shipment in trip['shipments']:
            output_data.append({
                'TRIP_ID': f'T{(idx+1):03}_1',
                'Shipment_ID': shipment['id'],
                'Latitude': shipment['lat'],
                'Longitude': shipment['lon'],
                'TIME_SLOT': f"{int(shipment['start']/60):02d}:00-{int(shipment['end']/60):02d}:00",
                'Shipments': len(trip['shipments']),
                'MST_DIST': round(trip['mst_dist'], 2),
                'TRIP_TIME': round(trip_time, 2),
                'Vehicle_Type': trip['vehicle'],
                'CAPACITY_UTI': round(capacity_uti, 2),
                'TIME_UTI': round(time_uti, 2),
                'COV_UTI': round(cov_uti, 2) if isinstance(cov_uti, (int, float)) else cov_uti
            })

    # Save output to CSV for map visualization
    pd.DataFrame(output_data).to_csv("smartroute_output.csv", index=False)
    print(output_data)
    return output_data

@app.post("/optimize")
async def optimize_route(request: Request):
    try:
        request_data = await request.json()
        shipments = request_data.get('shipments', [])
        
        if not shipments:
            return JSONResponse(content={'error': 'No shipments data provided'}, status_code=400)
        
        print(f"Received shipments data: {shipments}")
        
        # No need for additional processing here - pass the shipments directly to optimize_routes
        output_data = optimize_routes(shipments)
        return JSONResponse(content=output_data)
        
    except Exception as e:
        return JSONResponse(content={'error': str(e)}, status_code=500)

def load_trips():
    try:
        # Check if file exists and is not empty
        if os.path.exists("smartroute_output.csv") and os.path.getsize("smartroute_output.csv") > 0:
            df = pd.read_csv("smartroute_output.csv")
            return df.to_dict(orient="records")
        else:
            return []
    except Exception as e:
        print(f"Error loading trips: {e}")
        return []

@app.get("/api/trips")
def get_trips():
    return load_trips()

@app.get("/api/map/{trip_id}", response_class=HTMLResponse)
def get_trip_map(trip_id: str):
    trips = load_trips()
    selected_trip = [trip for trip in trips if trip["TRIP_ID"] == trip_id]
    
    if not selected_trip:
        return HTMLResponse(content="<h1>Trip not found</h1>", status_code=404)
    
    # Extract route locations
    store_location = (STORE_LAT, STORE_LON)
    shipment_locations = [(float(trip["Latitude"]), float(trip["Longitude"])) for trip in selected_trip]
    
    # Create Folium map
    m = folium.Map(location=store_location, zoom_start=12)
    folium.Marker(store_location, popup="Store Location", icon=folium.Icon(color="green")).add_to(m)
    
    for loc in shipment_locations:
        folium.Marker(loc, popup="Shipment", icon=folium.Icon(color="blue")).add_to(m)
    
    route_points = [store_location] + shipment_locations + [store_location]
    folium.PolyLine(route_points, color="blue").add_to(m)
    
    # Save map as HTML and return it
    map_html = m._repr_html_()
    return HTMLResponse(content=map_html)


@app.get("/api/all-trips-map", response_class=HTMLResponse)
def get_all_trips_map():
    trips = load_trips()
    
    if not trips:
        return HTMLResponse(content="<h1>No trips found</h1>", status_code=404)
    
    # Store location (fixed)
    store_location = (STORE_LAT, STORE_LON)
    
    # Create Folium map centered on store location
    m = folium.Map(location=store_location, zoom_start=10)
    
    # Add store marker
    folium.Marker(
        store_location, 
        popup="Store Location", 
        icon=folium.Icon(color="green", icon="home")
    ).add_to(m)
    
    # Color palette for different trips
    colors = ['blue', 'red', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue']
    
    # Track used colors
    color_index = 0
    trip_colors = {}
    
    # Add trips to map
    for trip in trips:
        trip_id = trip['TRIP_ID']
        
        # Assign a consistent color to each trip
        if trip_id not in trip_colors:
            trip_colors[trip_id] = colors[color_index % len(colors)]
            color_index += 1
        
        # Create marker for shipment
        folium.Marker(
            location=[float(trip['Latitude']), float(trip['Longitude'])],
            popup=f"Trip: {trip_id}<br>Shipment: {trip['Shipment_ID']}<br>Timeslot: {trip['TIME_SLOT']}",
            icon=folium.Icon(color=trip_colors[trip_id])
        ).add_to(m)
    
    # Group trips by TRIP_ID to draw routes
    trip_routes = {}
    for trip in trips:
        trip_id = trip['TRIP_ID']
        if trip_id not in trip_routes:
            trip_routes[trip_id] = [store_location]
        trip_routes[trip_id].append((float(trip['Latitude']), float(trip['Longitude'])))
    
    # Draw routes for each trip
    for trip_id, route in trip_routes.items():
        route.append(store_location)
        folium.PolyLine(
            route, 
            color=trip_colors.get(trip_id, 'blue'), 
            weight=2, 
            opacity=0.8,
            popup=f"Route for Trip {trip_id}"
        ).add_to(m)
    
    # Save map as HTML and return it
    map_html = m._repr_html_()
    return HTMLResponse(content=map_html)

@app.get("/")
def index():
    return HTMLResponse(content='''
    <h1>SmartRoute Optimization API</h1>
    <p>Send POST request to /optimize with shipments data</p>
    <h2>Example JSON Format:</h2>
    <pre>
{
  "shipments": [
    {
      "shipment_id": "S001",
      "latitude": 19.123456,
      "longitude": 72.987654,
      "delivery_timeslot": "09:00-10:00"
    }
  ]
}
    </pre>
    ''')

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)