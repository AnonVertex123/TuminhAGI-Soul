"use client";

import React, { useEffect, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  CircleMarker,
  Polyline,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Hospital, UserLocation } from "@/lib/emergency";
import { osrmToLeafletLatLngs, fetchDrivingGeometry } from "@/lib/emergency";

function fixLeafletIcons() {
  if (typeof window === "undefined") return;
  delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: string })._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
    iconUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
    shadowUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
  });
}

function FitBounds({
  user,
  hospitals,
}: {
  user: UserLocation;
  hospitals: Hospital[];
}) {
  const map = useMap();
  useEffect(() => {
    const pts: L.LatLngExpression[] = [[user.lat, user.lng]];
    hospitals.slice(0, 3).forEach((h) => pts.push([h.lat, h.lng]));
    if (pts.length === 1) {
      map.setView([user.lat, user.lng], 14);
      return;
    }
    const b = L.latLngBounds(pts);
    map.fitBounds(b, { padding: [28, 28], maxZoom: 15 });
  }, [map, user.lat, user.lng, hospitals]);
  return null;
}

const numberedIcon = (n: number) =>
  L.divIcon({
    className: "tuminh-emergency-marker",
    html: `<div style="background:#DC2626;color:#fff;font-weight:800;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35);font-size:12px;">${n}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });

export default function EmergencyMap({
  user,
  hospitals,
  routeToFirst,
}: {
  user: UserLocation;
  hospitals: Hospital[];
  routeToFirst?: boolean;
}) {
  const [route, setRoute] = React.useState<[number, number][] | null>(null);

  useEffect(() => {
    fixLeafletIcons();
  }, []);

  const firstId = hospitals[0]?.id;
  const firstLat = hospitals[0]?.lat;
  const firstLng = hospitals[0]?.lng;
  useEffect(() => {
    if (!routeToFirst || firstLat == null || firstLng == null) {
      setRoute(null);
      return;
    }
    let cancelled = false;
    (async () => {
      const g = await fetchDrivingGeometry(user.lat, user.lng, firstLat, firstLng);
      if (cancelled || !g?.coordinates?.length) {
        setRoute([[user.lat, user.lng], [firstLat, firstLng]]);
        return;
      }
      setRoute(osrmToLeafletLatLngs(g.coordinates));
    })();
    return () => {
      cancelled = true;
    };
  }, [routeToFirst, user.lat, user.lng, firstId, firstLat, firstLng]);

  const center = useMemo(
    () => [user.lat, user.lng] as [number, number],
    [user.lat, user.lng]
  );

  return (
    <div className="w-full h-[300px] rounded-xl overflow-hidden ring-2 ring-red-500/40 z-0 relative">
      <MapContainer
        center={center}
        zoom={14}
        className="h-full w-full"
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds user={user} hospitals={hospitals} />
        {route && route.length > 1 && (
          <Polyline positions={route} color="#2563EB" weight={4} opacity={0.85} />
        )}
        <CircleMarker
          center={center}
          radius={10}
          pathOptions={{ color: "#1D4ED8", fillColor: "#3B82F6", fillOpacity: 0.9 }}
        >
          <Popup>Bạn đang ở đây</Popup>
        </CircleMarker>
        {hospitals.slice(0, 5).map((h, i) => (
          <Marker key={h.id} position={[h.lat, h.lng]} icon={numberedIcon(i + 1)}>
            <Popup>
              <strong>{h.name}</strong>
              <br />
              {h.distance_km} km — ~{h.duration_drive_min} phút
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
