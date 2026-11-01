import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { formatArea } from '../mapApi.js';
import districtSeed from '../../../data/petaling-district.json';

function popupContent(feature, select) {
  // Uploaded text is never interpreted as HTML by Leaflet.
  const card = document.createElement('div');
  card.className = 'park-popup';
  const category = document.createElement('span');
  category.className = 'category-pill';
  category.textContent = feature.properties.category_name;
  const name = document.createElement('strong');
  name.textContent = feature.properties.name;
  const area = document.createElement('p');
  area.textContent = formatArea(feature.properties.area_size);
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'View green-space details →';
  button.addEventListener('click', () => select(feature));
  card.append(category, name, area, button);
  return card;
}

export default function GreenMap({ greens, boundaries, selectedId, focus, seedVisible, onBounds, onSelect, onDetails,
  origin, radius, onPick, searchView, coverage }) {
  const host = useRef(null), mapRef = useRef(null), greenLayer = useRef(null), radiusLayer = useRef(null);
  const handlers = useRef({ onBounds, onSelect, onDetails, onPick, searchView });
  handlers.current = { onBounds, onSelect, onDetails, onPick, searchView };
  useEffect(() => {
    const map = L.map(host.current, { zoomControl: false, minZoom: 8, maxZoom: 19,
      maxBounds: [[2.1, 100.3], [4.1, 102.7]], maxBoundsViscosity: 0.8,
    });
    const districtBounds = L.geoJSON(districtSeed).getBounds();
    map.fitBounds(districtBounds, { padding: [35, 65] });
    mapRef.current = map;
    L.control.zoom({ position: 'topright' }).addTo(map);
    L.control.scale({ position: 'bottomleft', imperial: false }).addTo(map);
    map.createPane('districts'); map.getPane('districts').style.zIndex = '350';
    map.createPane('coverage'); map.getPane('coverage').style.zIndex = '360';
    // No external tiles, OSM imports, address service, or illustrative roads.
    // Park geometry comes only from the project's public GeoJSON endpoints.
    const update = () => {
      const b = map.getBounds();
      handlers.current.onBounds?.([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(value => value.toFixed(6)).join(','));
    };
    map.on('moveend', update); update();
    const pick = latlng => handlers.current.onPick?.({ latitude: latlng.lat, longitude: latlng.lng,
      label: `${latlng.lat.toFixed(6)}, ${latlng.lng.toFixed(6)}` });
    map.on('click', event => pick(event.latlng));
    map.on('keydown', event => {
      if (event.originalEvent.key === 'Enter' && event.originalEvent.target === host.current && handlers.current.onPick) {
        L.DomEvent.stop(event.originalEvent); pick(map.getCenter());
      }
    });
    let sized = false;
    const resize = new ResizeObserver(() => {
      // A dialog's map initially measures zero; retain its centre when shown.
      map.invalidateSize({ pan: true, debounceMoveend: true });
      if (!sized && host.current.clientWidth && host.current.clientHeight) {
        sized = true;
        if (!handlers.current.searchView) map.fitBounds(districtBounds, { padding: [35, 65] });
      }
    });
    resize.observe(host.current);
    return () => { resize.disconnect(); map.remove(); mapRef.current = null; };
  }, []);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;
    const layer = L.geoJSON(greens, {
      pointToLayer: (feature, latlng) => L.marker(latlng, {
        title: feature.properties.name, alt: feature.properties.name, keyboard: true,
        icon: L.divIcon({ className: 'park-pin', html: '<span></span>', iconSize: [24, 24], iconAnchor: [12, 12] }),
      }),
      style: { color: '#0ba57e', weight: 2, fillColor: '#9cf2c9', fillOpacity: 0.5 },
      onEachFeature: (feature, item) => {
        item.options.bubblingMouseEvents = false;
        item.bindPopup(popupContent(feature, value => handlers.current.onDetails(value)), { maxWidth: 260 });
        item.on('click', () => handlers.current.onSelect(feature));
        item.on('add', () => {
          const element = item.getElement?.();
          if (!element || feature.geometry.type === 'Point') return;
          element.ownerSVGElement?.removeAttribute('aria-hidden');
          element.setAttribute('tabindex', '0'); element.setAttribute('role', 'button');
          element.setAttribute('aria-label', feature.properties.name);
          L.DomEvent.on(element, 'keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') { L.DomEvent.stop(event); item.openPopup(); handlers.current.onSelect(feature); }
          });
        });
      },
    }).addTo(map);
    greenLayer.current = layer;
    return () => { layer.remove(); greenLayer.current = null; };
  }, [greens]);
  useEffect(() => {
    greenLayer.current?.eachLayer(layer => {
      const selected = layer.feature.id === selectedId;
      if (layer.setStyle) layer.setStyle({ color: selected ? '#00664f' : '#0ba57e', weight: selected ? 4 : 2 });
      layer.getElement?.()?.classList.toggle('is-selected', selected);
    });
  }, [selectedId, greens]);
  useEffect(() => {
    if (!mapRef.current) return undefined;
    const layer = L.geoJSON(boundaries, { pane: 'districts', interactive: false,
      style: { color: '#6d9bac', weight: 1.5, dashArray: '6 5', fillColor: '#d3e9e1', fillOpacity: 0.42 },
    }).addTo(mapRef.current);
    return () => layer.remove();
  }, [boundaries]);
  useEffect(() => {
    if (!focus || !mapRef.current) return;
    const bounds = L.geoJSON(focus.feature).getBounds();
    if (bounds.isValid()) mapRef.current.fitBounds(bounds, { maxZoom: 16, padding: [45, 45] });
  }, [focus]);
  useEffect(() => {
    const attribution = 'Petaling boundary: <a href="https://github.com/dosm-malaysia/data-open">DOSM</a> (local seed)';
    if (seedVisible) mapRef.current?.attributionControl.addAttribution(attribution);
    return () => mapRef.current?.attributionControl.removeAttribution(attribution);
  }, [seedVisible]);
  useEffect(() => {
    if (!origin || !mapRef.current) return undefined;
    const location = [origin.latitude, origin.longitude];
    const layers = L.layerGroup();
    if (radius) radiusLayer.current = L.circle(location, { radius, interactive: false, color: '#10b99a', weight: 1.5,
      dashArray: '5 5', fillOpacity: 0.08 }).addTo(layers);
    L.marker(location, { title: 'Starting location', keyboard: false,
      icon: L.divIcon({ className: 'origin-pin', html: '<span></span>', iconSize: [22, 22], iconAnchor: [11, 11] }),
    }).addTo(layers);
    layers.addTo(mapRef.current);
    return () => { radiusLayer.current = null; layers.remove(); };
  }, [origin, radius]);
  useEffect(() => {
    if (!coverage?.length || !mapRef.current) return undefined;
    const features = [...coverage].sort((a, b) => b.properties.radius_m - a.properties.radius_m);
    const layer = L.geoJSON(features, { pane: 'coverage', interactive: false,
      style: feature => ({ color: feature.properties.selected ? '#069c7a' : '#6dcbb4',
        weight: feature.properties.selected ? 1.5 : 0.6,
        fillColor: '#21b88f', fillOpacity: feature.properties.radius_m === 500 ? 0.2 : 0.12 }),
    }).addTo(mapRef.current);
    return () => layer.remove();
  }, [coverage]);
  useEffect(() => {
    if (!searchView || !mapRef.current) return;
    const location = [searchView.latitude, searchView.longitude];
    // Circle bounds depend on the map projection; use the mounted radius layer.
    if (searchView.coverage && coverage?.length) mapRef.current.fitBounds(L.geoJSON(coverage).getBounds(), { padding: [35, 55], maxZoom: 17 });
    else if (searchView.radius_m && radiusLayer.current) mapRef.current.fitBounds(radiusLayer.current.getBounds(), { padding: [40, 55], maxZoom: 17 });
    else mapRef.current.setView(location, 14);
  }, [searchView, coverage]);
  return <div ref={host} className={`leaflet-host ${onPick ? 'location-pick-map' : ''}`}
    aria-label={onPick ? 'Select a location on the map. Use arrow keys to pan, then Enter to select the centre.' : 'Interactive green-space map. Use arrow keys to pan and plus or minus to zoom.'} />;
}
