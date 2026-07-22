import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { ASTANA_STREETS, ASTANA_LANDMARKS, FALLBACK_BUILDINGS_GEOJSON } from '../../constants/astanaData';

const DARK_MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const LIGHT_MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const ASTANA_CENTER_ANCHOR = [71.4305, 51.1283]; // Baiterek Monument reference origin anchor

export default function MapComponent({ 
  geoJSONData, 
  activeBuildingId, 
  onSelectBuilding, 
  onBoundsChange, 
  onViewportChange,
  roadsGeoJSON,
  mapMode = 'thermal',
  selectedStreet = null,
  onSelectStreet = null,
  cameraPreset = 'aerial_3d',
  theme = 'dark'
}) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const markersRef = useRef([]);

  const geoJSONRef = useRef(geoJSONData);
  const activeBuildingIdRef = useRef(activeBuildingId);
  const onSelectBuildingRef = useRef(onSelectBuilding);
  const onBoundsChangeRef = useRef(onBoundsChange);
  const onViewportChangeRef = useRef(onViewportChange);
  const onSelectStreetRef = useRef(onSelectStreet);

  useEffect(() => {
    geoJSONRef.current = geoJSONData;
    activeBuildingIdRef.current = activeBuildingId;
    onSelectBuildingRef.current = onSelectBuilding;
    onBoundsChangeRef.current = onBoundsChange;
    onViewportChangeRef.current = onViewportChange;
    onSelectStreetRef.current = onSelectStreet;
  });

  // 1. Initialize Map Libre Engine with Unified CRS & Camera Render Matrix Sync
  useEffect(() => {
    if (map.current) return;
    
    const styleUrl = theme === 'light' ? LIGHT_MAP_STYLE : DARK_MAP_STYLE;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: styleUrl,
      center: ASTANA_CENTER_ANCHOR,
      zoom: 13.8,
      pitch: 50,
      bearing: -15,
      preserveDrawingBuffer: true
    });

    map.current.on('load', () => {
      // Standardize scene reference origin anchor using MercatorCoordinate
      const mercatorAnchor = maplibregl.MercatorCoordinate.fromLngLat(ASTANA_CENTER_ANCHOR, 0);

      // Style Ishim River water
      if (map.current.getLayer('water')) {
        map.current.setPaintProperty('water', 'fill-color', theme === 'light' ? '#d4d4d8' : '#18181b');
        map.current.setPaintProperty('water', 'fill-opacity', 0.95);
      }

      // Initial buildings data source (fallback to authentic GeoJSON footprints if API data not available)
      const initialData = (geoJSONRef.current && geoJSONRef.current.features && geoJSONRef.current.features.length > 0)
        ? geoJSONRef.current 
        : FALLBACK_BUILDINGS_GEOJSON;

      map.current.addSource('buildings', {
        type: 'geojson',
        data: initialData
      });

      // 3D Extrusion Layer - Industrial Hard Contrast Palette
      map.current.addLayer({
        id: 'buildings-3d',
        type: 'fill-extrusion',
        source: 'buildings',
        paint: {
          'fill-extrusion-height': ['coalesce', ['get', 'height'], 35],
          'fill-extrusion-base': 0,
          'fill-extrusion-color': [
            'interpolate',
            ['linear'],
            ['coalesce', ['get', 'heat_loss_w'], 50000],
            10000, '#52525b',   // Solid Zinc/Iron
            50000, '#ffaa00',   // High Thermal Amber
            150000, '#ff2a4b',  // Extreme Thermal Crimson
            250000, '#ffffff'   // Maximum Heat White-Hot
          ],
          'fill-extrusion-opacity': 0.92
        }
      });

      // Highlight selected building (Stark Pure White / Black)
      map.current.addLayer({
        id: 'buildings-selected',
        type: 'fill-extrusion',
        source: 'buildings',
        paint: {
          'fill-extrusion-height': ['coalesce', ['get', 'height'], 35],
          'fill-extrusion-base': 0,
          'fill-extrusion-color': theme === 'light' ? '#000000' : '#ffffff',
          'fill-extrusion-opacity': 1.0
        },
        filter: ['==', ['get', 'id'], activeBuildingIdRef.current || '']
      });

      // Roads Source & Layer
      map.current.addSource('roads', {
        type: 'geojson',
        data: roadsGeoJSON || { type: 'FeatureCollection', features: [] }
      });

      // Road Casing Layer (High-contrast under-layer for city-wide vector line continuity)
      map.current.addLayer({
        id: 'roads-casing',
        type: 'line',
        source: 'roads',
        layout: {
          'line-join': 'round',
          'line-cap': 'round',
          'visibility': mapMode === 'thermal' ? 'none' : 'visible'
        },
        paint: {
          'line-color': '#000000',
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            11, 5,
            14, 9,
            17, 16
          ],
          'line-opacity': 0.8
        }
      });

      map.current.addLayer({
        id: 'roads-layer',
        type: 'line',
        source: 'roads',
        layout: {
          'line-join': 'round',
          'line-cap': 'round',
          'visibility': mapMode === 'thermal' ? 'none' : 'visible'
        },
        paint: {
          'line-color': ['coalesce', ['get', 'color'], '#ffffff'],
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            11, 3,
            14, 6,
            17, 12
          ],
          'line-opacity': 0.95
        }
      });

      map.current.addLayer({
        id: 'roads-labels',
        type: 'symbol',
        source: 'roads',
        layout: {
          'text-field': ['get', 'name'],
          'text-size': 11,
          'text-offset': [0, -0.6],
          'symbol-placement': 'line',
          'visibility': mapMode === 'thermal' ? 'none' : 'visible'
        },
        paint: {
          'text-color': theme === 'light' ? '#000000' : '#ffffff',
          'text-halo-color': theme === 'light' ? '#ffffff' : '#000000',
          'text-halo-width': 2.5
        }
      });

      // Technical Pin Markers anchored to precise WGS84 street coordinates
      ASTANA_STREETS.forEach(street => {
        const el = document.createElement('div');
        el.className = 'technical-marker-container';
        el.innerHTML = `
          <div className="technical-marker-badge">
            <div className="marker-dot"></div>
            <span className="marker-text">${street.nameRu}</span>
            <span className="marker-speed">${street.currentSpeed} km/h</span>
          </div>
        `;
        
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          if (onSelectStreetRef.current) {
            onSelectStreetRef.current(street);
          }
        });

        const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
          .setLngLat([street.lng, street.lat])
          .addTo(map.current);

        markersRef.current.push(marker);
      });

      // Landmarks Technical Markers anchored to landmark coordinates
      ASTANA_LANDMARKS.forEach(lm => {
        const el = document.createElement('div');
        el.className = 'technical-landmark-badge';
        el.innerHTML = `
          <div className="lm-icon-tag">LM</div>
          <span className="lm-text">${lm.nameRu}</span>
        `;

        const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
          .setLngLat([lm.lng, lm.lat])
          .addTo(map.current);

        markersRef.current.push(marker);
      });

      // Viewport movement handlers
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
        const boundsObj = map.current.getBounds();
        if (onBoundsChangeRef.current && map.current.getZoom() >= 14) {
          onBoundsChangeRef.current({
            west: boundsObj.getWest(),
            south: boundsObj.getSouth(),
            east: boundsObj.getEast(),
            north: boundsObj.getNorth()
          });
        }
      });

      map.current.on('click', 'buildings-3d', (e) => {
        const feature = e.features[0];
        if (feature && feature.properties?.id && onSelectBuildingRef.current) {
          onSelectBuildingRef.current(feature.properties.id);
        }
      });

      map.current.on('mouseenter', 'buildings-3d', () => {
        if (map.current) map.current.getCanvas().style.cursor = 'pointer';
      });
      map.current.on('mouseleave', 'buildings-3d', () => {
        if (map.current) map.current.getCanvas().style.cursor = '';
      });
    });
  }, []);

  // Dynamic theme basemap switcher
  useEffect(() => {
    if (map.current) {
      const styleUrl = theme === 'light' ? LIGHT_MAP_STYLE : DARK_MAP_STYLE;
      map.current.setStyle(styleUrl);
    }
  }, [theme]);

  // Update building dataset (fallback if empty)
  useEffect(() => {
    if (map.current && map.current.getSource('buildings')) {
      const displayData = (geoJSONData && geoJSONData.features && geoJSONData.features.length > 0)
        ? geoJSONData 
        : FALLBACK_BUILDINGS_GEOJSON;
      map.current.getSource('buildings').setData(displayData);
    }
  }, [geoJSONData]);

  // Update active building highlight filter
  useEffect(() => {
    if (map.current && map.current.getLayer('buildings-selected')) {
      map.current.setFilter('buildings-selected', ['==', ['get', 'id'], activeBuildingId || '']);
    }
  }, [activeBuildingId]);

  // Camera flyTo animation when street is selected
  useEffect(() => {
    if (map.current && selectedStreet) {
      map.current.flyTo({
        center: [selectedStreet.lng, selectedStreet.lat],
        zoom: 16.5,
        pitch: 65,
        bearing: -15,
        duration: 1600,
        essential: true
      });
    }
  }, [selectedStreet]);

  // Camera presets
  useEffect(() => {
    if (map.current) {
      if (cameraPreset === 'aerial_3d') {
        map.current.flyTo({ zoom: 14.5, pitch: 55, bearing: -20, duration: 1200 });
      } else if (cameraPreset === 'street_flyover') {
        map.current.flyTo({ zoom: 16.5, pitch: 65, bearing: -15, duration: 1200 });
      } else if (cameraPreset === 'ground_3d') {
        map.current.flyTo({ zoom: 17.5, pitch: 75, bearing: 10, duration: 1200 });
      } else if (cameraPreset === 'aerial_top') {
        map.current.flyTo({ pitch: 0, bearing: 0, duration: 1000 });
      }
    }
  }, [cameraPreset]);

  // Update roads data
  useEffect(() => {
    if (map.current && map.current.getSource('roads') && roadsGeoJSON) {
      map.current.getSource('roads').setData(roadsGeoJSON);
    }
  }, [roadsGeoJSON]);

  return (
    <div 
      ref={mapContainer} 
      className="map-container-inner" 
      style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }} 
    />
  );
}
