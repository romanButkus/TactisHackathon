import httpx
import xml.etree.ElementTree as ET

async def get_weather_data(region: str = "Helsinki", bbox: dict = None):
    url = "https://opendata.fmi.fi/wfs"
    
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "getFeature",
        "storedquery_id": "fmi::observations::weather::simple",
        "parameters": "windspeedms,winddir, nn_fmi, t2m,vis,"
    }

    # Use dynamic bbox if provided (e.g., from MapTiler service)
    if bbox:
        # FMI WFS 2.0.0 EPSG:4326 usually expects coordinates as min_lat,min_lon,max_lat,max_lon
        params["bbox"] = f"{bbox['min_lat']},{bbox['min_lng']},{bbox['max_lat']},{bbox['max_lng']}"
    else:
        # If it's not a known region, treat it as a city/place name
        params["place"] = region

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)

    if response.status_code != 200:
        return {"error": f"Failed to fetch data: {response.status_code}"}

    # ... (Rest of your XML parsing code stays exactly the same) ...
    root = ET.fromstring(response.content)
    namespaces = {
        'wfs': 'http://www.opengis.net/wfs/2.0',
        'gml': 'http://www.opengis.net/gml/3.2',
        'BsWfs': 'http://xml.fmi.fi/schema/wfs/2.0'
    }

    observations = []
    for member in root.findall('.//wfs:member', namespaces):
        element = member.find('.//BsWfs:BsWfsElement', namespaces)
        if element is not None:
            pos = element.find('.//gml:pos', namespaces).text.split()
            lat, lon = float(pos[0]), float(pos[1])
            param_name = element.find('BsWfs:ParameterName', namespaces).text
            raw_value = element.find('BsWfs:ParameterValue', namespaces).text
            time = element.find('BsWfs:Time', namespaces).text

            try:
                value = float(raw_value)
            except (ValueError, TypeError):
                value = raw_value

            observations.append({
                "latitude": lat,
                "longitude": lon,
                "parameter": param_name,
                "value": value,
                "time": time
            })

    return observations

#
#if __name__ == "__main__":
#    import asyncio
#    result = asyncio.run(get_weather_data(region="Helsinki"))
#    print(result)
