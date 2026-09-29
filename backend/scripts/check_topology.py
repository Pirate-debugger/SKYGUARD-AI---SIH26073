from app.simulator.generator import DEFAULT_STATIONS
from app.core.spatial_engine import haversine_km

print(f"=== TOTAL STATIONS: {len(DEFAULT_STATIONS)} ===")
radius = 150.0
k = 4

topology = {}
for s1 in DEFAULT_STATIONS:
    neighbors = []
    for s2 in DEFAULT_STATIONS:
        if s1.station_id == s2.station_id:
            continue
        dist = haversine_km(s1.latitude, s1.longitude, s2.latitude, s2.longitude)
        if dist <= radius:
            neighbors.append((s2.station_id, s2.station_name, dist))
    neighbors.sort(key=lambda x: x[2])
    topology[s1.station_id] = {
        'name': s1.station_name,
        'lat': s1.latitude,
        'lon': s1.longitude,
        'region': s1.region,
        'all_within_radius': neighbors,
        'top_k': neighbors[:k]
    }

zero_neighbor_stations = []
single_neighbor_stations = []

for sid, data in topology.items():
    count = len(data['all_within_radius'])
    print(f"\n{sid} ({data['name']} - {data['region']}): {count} neighbors <= {radius}km")
    for nid, nname, dist in data['top_k']:
        print(f"   -> {nid} ({nname}): {dist:.1f} km")
    if count == 0:
        zero_neighbor_stations.append(sid)
        print("   *** ZERO VALID NEIGHBORS WITHIN 150KM ***")
    elif count == 1:
        single_neighbor_stations.append(sid)

print("\n=== SUMMARY ===")
print(f"Stations with ZERO neighbors (<= {radius}km): {zero_neighbor_stations}")
print(f"Stations with SINGLE neighbor (<= {radius}km): {single_neighbor_stations}")
counts = [len(d['all_within_radius']) for d in topology.values()]
print(f"Neighbor counts min: {min(counts)}, max: {max(counts)}, avg: {sum(counts)/len(counts):.1f}")
