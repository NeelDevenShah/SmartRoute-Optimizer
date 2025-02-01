import pandas as pd
import math
from itertools import combinations

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
    for dist, u, v in edges:
        if find(u) != find(v):
            union(u, v)
            mst_sum += dist
    return mst_sum

def convert_time_to_minutes(time_str):
    return int(time_str.split(':')[0]) * 60 + int(time_str.split(':')[1])

def check_capacity_constraints(num_shipments, vehicle_capacity):
    return math.ceil(vehicle_capacity * 0.5) <= num_shipments <= vehicle_capacity

# Load data
store_df = pd.read_excel('Data/SmartRoute Optimizer.xlsx', sheet_name='Store Location')
store_lat = store_df['Latitute'].iloc[0]
store_lon = store_df['Longitude'].iloc[0]

shipments_df = pd.read_excel('Data/SmartRoute Optimizer.xlsx', sheet_name='Shipments_Data')
shipments = []
for _, row in shipments_df.iterrows():
    start, end = row['Delivery Timeslot'].split('-')
    shipments.append({
        'id': row['Shipment ID'],
        'lat': row['Latitude'],
        'lon': row['Longitude'],
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
                points = [(store_lat, store_lon)] + [(s['lat'], s['lon']) for s in current_batch]
                mst_dist = compute_mst(points)
                
                last_delivery = points[-1]
                return_dist = haversine(last_delivery[0], last_delivery[1], store_lat, store_lon)
                total_dist = mst_dist + return_dist  # Include return trip distance
                
                if total_dist > vehicle['max_radius']:  # Split trip if distance exceeds max radius
                    if len(current_batch) > 1:  
                        trips.append({
                            'shipments': current_batch[:-1],
                            'start': start_time,
                            'end': end_time,
                            'mst_dist': mst_dist - return_dist,
                            'vehicle': vehicle['type'],
                            'vehicle_capacity': vehicle['capacity'],
                            'vehicle_max_radius': vehicle['max_radius']
                        })
                        vehicle['remaining'] -= 1
                        current_batch = [shipment]  

                if check_capacity_constraints(len(current_batch), vehicle['capacity']):
                    trips.append({
                        'shipments': current_batch.copy(),
                        'start': start_time,
                        'end': end_time,
                        'mst_dist': total_dist,
                        'vehicle': vehicle['type'],
                        'vehicle_capacity': vehicle['capacity'],
                        'vehicle_max_radius': vehicle['max_radius']
                    })
                    vehicle['remaining'] -= 1
                    current_batch = []
                    break

# Ensure no vehicle exceeds its constraints
# Adjust trips dynamically if they exceed vehicle constraints
for trip in trips:
    while trip['mst_dist'] > trip['vehicle_max_radius']:  # If trip exceeds max radius
        if len(trip['shipments']) > 1:  # Only split if we have more than one shipment
            removed_shipment = trip['shipments'].pop()  # Remove last shipment
            points = [(store_lat, store_lon)] + [(s['lat'], s['lon']) for s in trip['shipments']]
            mst_dist = compute_mst(points)  # Recalculate MST distance
            
            last_delivery = points[-1]
            return_dist = haversine(last_delivery[0], last_delivery[1], store_lat, store_lon)
            trip['mst_dist'] = mst_dist + return_dist  # Update distance
            
            # Store removed shipment in a new trip
            new_trip = {
                'shipments': [removed_shipment],
                'start': trip['start'],
                'end': trip['end'],
                'mst_dist': haversine(store_lat, store_lon, removed_shipment['lat'], removed_shipment['lon']) * 2,  # Direct trip
                'vehicle': trip['vehicle'],
                'vehicle_capacity': trip['vehicle_capacity'],
                'vehicle_max_radius': trip['vehicle_max_radius']
            }
            trips.append(new_trip)
        else:
            break  # Stop adjusting if only one shipment remains

# Generate Output
output_data = []
for idx, trip in enumerate(trips):
    trip_time = (trip['mst_dist'] * 5) + (len(trip['shipments']) * 10)
    available_time = trip['end'] - trip['start']
    
    for shipment in trip['shipments']:
        output_data.append({
            'TRIP_ID': f'T{(idx+1):03}_1',
            'Shipment_ID': shipment['id'],
            'TIME_SLOT': f"{int(shipment['start']/60):02d}:00-{int(shipment['end']/60):02d}:00",
            'MST_DIST': round(trip['mst_dist'], 2),
            'TRIP_TIME': round(trip_time, 2),
            'Vehicle_Type': trip['vehicle']
        })

pd.DataFrame(output_data).to_csv('smartroute_output.csv', index=False)
print("Updated output saved to 'smartroute_output.csv'")