import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

// CartoDB Dark Matter GL style - free vector tiles
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

function makeCircleGeoJSON(center, radiusInMeters) {
  if (!center) return null;
  const points = 64;
  const coords = [];
  const km = radiusInMeters / 1000.0;
  
  const lat = center.lat;
  const lng = center.lng;
  
  const latOffset = km / 111.32;
  const lngOffset = km / (111.32 * Math.cos(lat * Math.PI / 180.0));
  
  for (let i = 0; i < points; i++) {
    const angle = (i / points) * (2.0 * Math.PI);
    const cLat = lat + latOffset * Math.sin(angle);
    const cLng = lng + lngOffset * Math.cos(angle);
    coords.push([cLng, cLat]);
  }
  coords.push(coords[0]); // Close polygon
  
  return {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [coords]
      }
    }]
  };
}

export default function MapComponent({ 
  geoJSONData, 
  activeBuildingId, 
  onSelectBuilding, 
  onBoundsChange, 
  onViewportChange,
  radiusActive,
  radiusMeters,
  radiusCenter,
  onMapClick
}) {
  const mapContainer = useRef(null);
  const map = useRef(null);

  // Keep refs up-to-date to prevent stale closures in MapLibre event handlers
  const geoJSONRef = useRef(geoJSONData);
  const activeBuildingIdRef = useRef(activeBuildingId);
  const radiusActiveRef = useRef(radiusActive);
  const onSelectBuildingRef = useRef(onSelectBuilding);
  const onBoundsChangeRef = useRef(onBoundsChange);
  const onViewportChangeRef = useRef(onViewportChange);
  const onMapClickRef = useRef(onMapClick);

  useEffect(() => {
    geoJSONRef.current = geoJSONData;
    activeBuildingIdRef.current = activeBuildingId;
    radiusActiveRef.current = radiusActive;
    onSelectBuildingRef.current = onSelectBuilding;
    onBoundsChangeRef.current = onBoundsChange;
    onViewportChangeRef.current = onViewportChange;
    onMapClickRef.current = onMapClick;
  });

  // 1. Initialize Map
  useEffect(() => {
    if (map.current) return;
    
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE,
      center: [71.4305, 51.1283],
      zoom: 14.5,
      pitch: 45,
      bearing: -15
    });

    map.current.on('load', () => {
      // Add buildings source
      map.current.addSource('buildings', {
        type: 'geojson',
        data: geoJSONRef.current || { type: 'FeatureCollection', features: [] }
      });

      // Add 3D Extrusion Layer
      map.current.addLayer({
        id: 'buildings-3d',
        type: 'fill-extrusion',
        source: 'buildings',
        paint: {
          'fill-extrusion-height': ['get', 'height'],
          'fill-extrusion-base': 0,
          'fill-extrusion-color': [
            'interpolate',
            ['linear'],
            ['get', 'heat_loss_w'],
            10000, '#33cc33',   // Solid Green
            50000, '#ffcc00',   // Amber
            150000, '#ff7300',  // Orange
            250000, '#ff3333'   // Red
          ],
          'fill-extrusion-opacity': 0.85
        }
      });

      // Add selected building highlight layer (Solid Orange highlight)
      map.current.addLayer({
        id: 'buildings-selected',
        type: 'fill-extrusion',
        source: 'buildings',
        paint: {
          'fill-extrusion-height': ['get', 'height'],
          'fill-extrusion-base': 0,
          'fill-extrusion-color': '#ffb366', // Solid light orange
          'fill-extrusion-opacity': 0.95
        },
        filter: ['==', ['get', 'id'], activeBuildingIdRef.current || '']
      });

      // Add selected building outline layer (Neon Cyan glowing outline)
      map.current.addLayer({
        id: 'buildings-selected-outline',
        type: 'line',
        source: 'buildings',
        paint: {
          'line-color': '#00ffff', // Neon Cyan
          'line-width': 3.5,
          'line-blur': 0.5
        },
        filter: ['==', ['get', 'id'], activeBuildingIdRef.current || '']
      });

      // Add radius search circle layer & source
      map.current.addSource('radius-circle', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
      });

      map.current.addLayer({
        id: 'radius-circle-layer',
        type: 'fill',
        source: 'radius-circle',
        paint: {
          'fill-color': '#ff7300', // Orange fill
          'fill-opacity': 0.12
        }
      });

      map.current.addLayer({
        id: 'radius-circle-outline',
        type: 'line',
        source: 'radius-circle',
        paint: {
          'line-color': '#ff7300', // Orange line
          'line-width': 1.5
        }
      });

      // Handle map updates
      map.current.on('move', () => {
        const center = map.current.getCenter();
        if (onViewportChangeRef.current) {
          onViewportChangeRef.current({
            latitude: center.lat,
            longitude: center.lng,
            zoom: map.current.getZoom(),
            pitch: map.current.getPitch(),
            bearing: map.current.getBearing()
          });
        }
      });

      map.current.on('moveend', () => {
        const zoom = map.current.getZoom();
        if (zoom < 14) {
          if (onBoundsChangeRef.current) {
            onBoundsChangeRef.current(null);
          }
          if (map.current.getSource('buildings')) {
            map.current.getSource('buildings').setData({ type: 'FeatureCollection', features: [] });
          }
        } else {
          const boundsObj = map.current.getBounds();
          if (onBoundsChangeRef.current) {
            onBoundsChangeRef.current({
              west: boundsObj.getWest(),
              south: boundsObj.getSouth(),
              east: boundsObj.getEast(),
              north: boundsObj.getNorth()
            });
          }
        }
      });

      // Selection clicks
      map.current.on('click', 'buildings-3d', (e) => {
        if (radiusActiveRef.current) return; // Let map click handle radius
        const feature = e.features[0];
        if (feature && feature.properties?.id && onSelectBuildingRef.current) {
          onSelectBuildingRef.current(feature.properties.id);
        }
      });

      // Generic map click for radial search
      map.current.on('click', (e) => {
        if (radiusActiveRef.current && onMapClickRef.current) {
          onMapClickRef.current({ lngLat: e.lngLat });
        }
      });

      // cursor styles
      map.current.on('mouseenter', 'buildings-3d', () => {
        if (!radiusActiveRef.current) map.current.getCanvas().style.cursor = 'pointer';
      });
      map.current.on('mouseleave', 'buildings-3d', () => {
        if (!radiusActiveRef.current) map.current.getCanvas().style.cursor = '';
      });
    });
  }, []);

  // Update building data source
  useEffect(() => {
    if (map.current && map.current.getSource('buildings') && geoJSONData) {
      map.current.getSource('buildings').setData(geoJSONData);
    }
  }, [geoJSONData]);

  // Update selection highlight
  useEffect(() => {
    if (map.current) {
      if (map.current.getLayer('buildings-selected')) {
        map.current.setFilter('buildings-selected', ['==', ['get', 'id'], activeBuildingId || '']);
      }
      if (map.current.getLayer('buildings-selected-outline')) {
        map.current.setFilter('buildings-selected-outline', ['==', ['get', 'id'], activeBuildingId || '']);
      }
    }
  }, [activeBuildingId]);

  // Update radius search visual boundary
  useEffect(() => {
    if (map.current && map.current.getSource('radius-circle')) {
      if (radiusActive && radiusCenter) {
        const geojson = makeCircleGeoJSON(radiusCenter, radiusMeters);
        map.current.getSource('radius-circle').setData(geojson);
      } else {
        map.current.getSource('radius-circle').setData({ type: 'FeatureCollection', features: [] });
      }
    }
  }, [radiusActive, radiusCenter, radiusMeters]);

  return (
    <div 
      ref={mapContainer} 
      className="map-container-inner" 
      style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }} 
    />
  );
}
