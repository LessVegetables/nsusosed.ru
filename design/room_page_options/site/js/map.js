// Maps (Leaflet + OpenStreetMap tiles) and the one piece of privacy math on the site.
//
// An apartment is never stored as a point. The host finds their building, and THIS file, in
// the host's browser, replaces it with a circle whose center is moved off the real spot. Only
// that circle is sent to the server; the real point never leaves the page.

import * as L from '/vendor/leaflet/leaflet-src.esm.js';

export const AKADEMGORODOK = { lat: 54.8437, lon: 83.0907 };
const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATTRIBUTION = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** A map inside `host` (an element with class "map"). */
export function createMap(host, { lat, lon, zoom = 14 } = { ...AKADEMGORODOK }) {
  const map = L.map(host, { scrollWheelZoom: false, attributionControl: true }).setView([lat, lon], zoom);
  map.attributionControl.setPrefix(false);
  L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(map);
  // The page layout may settle after the map is created (fonts, hidden panels).
  setTimeout(() => map.invalidateSize(), 0);
  return map;
}

/** A pin the person can drag. `onMove({lat, lon})` fires when they let go. */
export function addPin(map, { lat, lon }, onMove) {
  const icon = L.divIcon({ className: '', html: '<div class="map-pin"></div>', iconSize: [28, 28], iconAnchor: [14, 34] });
  const marker = L.marker([lat, lon], { icon, draggable: Boolean(onMove), keyboard: true, autoPan: true }).addTo(map);
  if (onMove) {
    marker.on('dragend', () => { const p = marker.getLatLng(); onMove({ lat: p.lat, lon: p.lng }); });
    map.on('click', (e) => { marker.setLatLng(e.latlng); onMove({ lat: e.latlng.lat, lon: e.latlng.lng }); });
  }
  return marker;
}

/** The approximate area of an apartment. Returns the layer so it can be replaced. */
export function addArea(map, { lat, lon, radius_m: radius }) {
  const circle = L.circle([lat, lon], {
    radius, color: css('--edge') || '#000', weight: 3, fillColor: css('--accent') || '#ff8fab', fillOpacity: 0.45,
  }).addTo(map);
  // Leave the neighborhood around the circle in view, so it reads as "somewhere around here".
  map.fitBounds(circle.getBounds().pad(0.5));
  return circle;
}

const randomBetween = (min, max) => min + Math.random() * (max - min);

/**
 * Hide a real point inside a circle.
 *   radius: 300–500 m;
 *   center: moved 30–90% of the radius away from the real point, in a random direction —
 * so the real spot is always somewhere inside the circle, never at its center and never on
 * its edge. Each call rolls again; the host can reroll until they like the result.
 */
export function obfuscate({ lat, lon }) {
  const radius = Math.round(randomBetween(300, 500));
  const distance = radius * randomBetween(0.3, 0.9);
  const bearing = randomBetween(0, 2 * Math.PI);
  const metersPerDegreeLat = 111_320;
  const metersPerDegreeLon = metersPerDegreeLat * Math.cos((lat * Math.PI) / 180);
  return {
    lat: lat + (distance * Math.cos(bearing)) / metersPerDegreeLat,
    lon: lon + (distance * Math.sin(bearing)) / metersPerDegreeLon,
    radius_m: radius,
  };
}
