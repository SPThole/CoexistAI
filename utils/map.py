import logging
from typing import List, Tuple, Optional
import requests
import folium
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Step 1: Get coordinates from Nominatim (OpenStreetMap API for geocoding) with multiple results
def get_coordinates(location: str, limit: int = 3) -> List[Tuple[str, float, float]]:
    """
    Retrieves geographic coordinates (latitude, longitude) and display names for a given location using the Nominatim API.
    """
    url = f'https://nominatim.openstreetmap.org/search?q={location}&format=json&addressdetails=1&limit={limit}'
    headers = {
        'User-Agent': 'YourAppName/1.0 (your.email@example.com)'  # Replace with your app's name and email
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            probable_locations = [(res['display_name'], float(res['lat']), float(res['lon'])) for res in data]
            logger.info(f"Found {len(probable_locations)} probable locations for '{location}'.")
            return probable_locations
        else:
            logger.warning(f"No data found for location: {location}")
            return []
    except requests.RequestException as e:
        logger.error(f"Request error while getting coordinates for '{location}': {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_coordinates: {e}")
        return []

# Step 2: Get route using OSRM (Open Source Routing Machine)
def get_route(start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> Optional[dict]:
    """
    Retrieves a driving route between two coordinates using the OSRM API.
    """
    start_lat, start_lon = start_coords
    end_lat, end_lon = end_coords
    osrm_url = (
        f'http://router.project-osrm.org/route/v1/driving/'
        f'{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson&steps=true'
    )
    try:
        osrm_response = requests.get(osrm_url, timeout=10)
        osrm_response.raise_for_status()
        osrm_data = osrm_response.json()
        if 'routes' in osrm_data and osrm_data['routes']:
            logger.info("Route found between start and end coordinates.")
            return osrm_data['routes'][0]
        else:
            logger.warning("No route found.")
            return None
    except requests.RequestException as e:
        logger.error(f"Request error while getting route: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_route: {e}")
        return None

# Step 3: Get points of interest (restaurants, cafes, etc.) using Overpass API
def get_pois(
    location: Tuple[float, float],
    radius: int = 500,
    amenities: str = "restaurant|cafe|bar|hotel"
) -> List[Tuple[float, float, str]]:
    """
    Retrieves points of interest (POIs) around a given location using the Overpass API.
    """
    lat, lon = location
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    node
      [amenity~"{amenities}"]
      (around:{radius},{lat},{lon});
    out body;
    """
    try:
        response = requests.get(overpass_url, params={'data': overpass_query}, timeout=20)
        response.raise_for_status()
        data = response.json()
        pois = [
            (element['lat'], element['lon'], element['tags'].get('name', 'Unnamed'))
            for element in data.get('elements', [])
        ]
        logger.info(f"Found {len(pois)} POIs near ({lat}, {lon}).")
        return pois
    except requests.RequestException as e:
        logger.error(f"Request error while getting POIs: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_pois: {e}")
        return []

# Step 4: Create and display the map with route and POIs
def create_map(
    start_coords: Tuple[float, float],
    end_coords: Tuple[float, float],
    route_coords: List[List[float]],
    pois_start: Optional[List[Tuple[float, float, str]]] = None,
    pois_end: Optional[List[Tuple[float, float, str]]] = None
) -> folium.Map:
    """
    Creates a Folium map displaying the route between two locations and POIs around the start and end points.
    """
    m = folium.Map(location=[start_coords[0], start_coords[1]], zoom_start=13)
    folium.Marker(location=[start_coords[0], start_coords[1]], popup="Start").add_to(m)
    folium.Marker(location=[end_coords[0], end_coords[1]], popup="End").add_to(m)
    try:
        folium.PolyLine(
            locations=[[lat, lon] for lon, lat in route_coords],
            color="blue",
            weight=5
        ).add_to(m)
    except Exception as e:
        logger.error(f"Error adding route polyline: {e}")

    if pois_start:
        for lat, lon, name in pois_start:
            folium.Marker(
                location=[lat, lon],
                popup=name,
                icon=folium.Icon(color='green', icon='info-sign')
            ).add_to(m)
    if pois_end:
        for lat, lon, name in pois_end:
            folium.Marker(
                location=[lat, lon],
                popup=name,
                icon=folium.Icon(color='green', icon='info-sign')
            ).add_to(m)
    return m

# Helper function to automatically fix destinations based on probable locations
def auto_fix_destination(location: str, limit: int = 3) -> Optional[Tuple[str, float, float]]:
    """
    Automatically selects a probable location for a given input by retrieving geocoded results.
    """
    probable_locations = get_coordinates(location, limit)
    if probable_locations:
        logger.info(f"Auto-selected location: {probable_locations[0][0]}")
        return probable_locations[0]
    logger.warning(f"Could not auto-fix destination for: {location}")
    return None

# New function to generate directions in a human-readable format
def get_route_directions(route_data: dict) -> str:
    """
    Generates human-readable driving directions from OSRM route data.
    """
    directions = []
    try:
        for leg in route_data.get('legs', []):
            for step in leg.get('steps', []):
                instruction = f"Road Name: {step.get('name', 'same road')}"
                distance = step.get('distance', 0)
                directions.append(f"{instruction} for {distance} meters.")
        logger.info("Generated route directions.")
    except Exception as e:
        logger.error(f"Error generating route directions: {e}")
    return "\n".join(directions)

# Main function to handle all logic and display map
def generate_map(
    start_location: Optional[str] = None,
    end_location: Optional[str] = None,
    pois_radius: int = 500,
    amenities: str = "restaurant|cafe|bar|hotel",
    limit: int = 3,
    task: str = "route_and_pois"
) -> str:
    """
    Generates a map displaying a route between two locations, along with nearby POIs. 
    It also provides human-readable directions for the route.
    Handles cases where start or end can be None.
    """
    try:
        if task == 'location_only':
            locations = ''
            if start_location:
                start_coords = auto_fix_destination(start_location, limit)
                if not start_coords:
                    logger.error("Could not determine start location.")
                    locations += "Could not determine start location. Else rate limit reached. Try to find on internet or be less specific."
                else:
                    locations += f"Start location: {start_coords[0]} (Lat: {start_coords[1]}, Lon: {start_coords[2]})\n"
            if end_location:
                end_coords = auto_fix_destination(end_location, limit)
                if not end_coords:
                    logger.error("Could not determine end location.")
                    locations += "Could not determine end location. Else rate limit reached. Try to find on internet or be less specific."
                else:
                    locations += f"End location: {end_coords[0]} (Lat: {end_coords[1]}, Lon: {end_coords[2]})\n"
            if not start_location and not end_location:
                locations = "No start or end location provided."
            return locations

        elif task == 'route_and_pois':
            err = ''
            start_coords = auto_fix_destination(start_location, limit) if start_location else None
            end_coords = auto_fix_destination(end_location, limit) if end_location else None

            if not start_coords and not end_coords:
                logger.error("Neither start nor end location provided or found.")
                return "Neither start nor end location provided or found. Else rate limit reached"

            if not start_coords:
                logger.error("Could not determine start location.")
                err += "Could not determine start location. Else rate limit reached. Try to find on internet or be less specific. "

            if not end_coords:
                logger.error("Could not determine end location.")
                err += "Could not determine end location. Else rate limit reached. Try to find on internet or be less specific."

            if not start_coords or not end_coords:
                logger.error("Could not determine start or end location.")
                return err.strip()

            route_data = get_route((start_coords[1], start_coords[2]), (end_coords[1], end_coords[2]))
            if not route_data:
                logger.error("No route data found.")
                return "No route data found. Else rate limit reached"

            route_coords = route_data['geometry']['coordinates']
            pois_start = get_pois((start_coords[1], start_coords[2]), radius=pois_radius, amenities=amenities)
            pois_end = get_pois((end_coords[1], end_coords[2]), radius=pois_radius, amenities=amenities)
            m = create_map(
                (start_coords[1], start_coords[2]),
                (end_coords[1], end_coords[2]),
                route_coords,
                pois_start,
                pois_end
            )
            
            output_folder = "output"
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            m.save(os.path.join(output_folder, "map_with_route_and_pois.html"))
            logger.info("Map generated and saved as 'map_with_route_and_pois.html'.")
            return get_route_directions(route_data) + f"\n\nPoints of interest around start: {pois_start}, end: {pois_end}. Map saved as 'map_with_route_and_pois.html'." + \
                "start location: " + str(start_coords) + ", end location: " + str(end_coords[0])
    except Exception as e:
        logger.error(f"Error in map functions: {e},Else rate limit reached")
        return f"Error in map functions: {e},Else rate limit reached"