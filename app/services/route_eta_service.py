import math

import httpx


class RouteEtaService:
    OSRM_BASE_URL = "https://router.project-osrm.org"
    AVG_SPEED_MPS_FALLBACK = 8.33  # 30 km/h

    @staticmethod
    def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371000.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

    @staticmethod
    def compute_route(
        origen_lat: float,
        origen_lon: float,
        destino_lat: float,
        destino_lon: float,
        profile: str = "foot",
    ) -> dict:
        url = (
            f"{RouteEtaService.OSRM_BASE_URL}/route/v1/{profile}/"
            f"{origen_lon},{origen_lat};{destino_lon},{destino_lat}"
            "?overview=full&geometries=geojson&steps=false"
        )
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
            routes = payload.get("routes") or []
            if not routes:
                raise ValueError("Sin rutas en respuesta OSRM")
            best = routes[0]
            return {
                "distance_meters": float(best.get("distance", 0.0)),
                "duration_seconds": float(best.get("duration", 0.0)),
                "route_geojson": best.get("geometry"),
                "source": "osrm",
            }
        except Exception:
            distance = RouteEtaService._haversine_meters(origen_lat, origen_lon, destino_lat, destino_lon)
            duration = distance / RouteEtaService.AVG_SPEED_MPS_FALLBACK
            return {
                "distance_meters": distance,
                "duration_seconds": duration,
                "route_geojson": None,
                "source": "fallback_haversine",
            }
