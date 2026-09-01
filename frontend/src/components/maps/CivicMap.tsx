import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
} from "react-leaflet";

export interface CivicMapMarker {
  id: number | string;
  lat: number;
  lng: number;
  title: string;
  subtitle?: string;
  priority?: string;
}

function markerColor(priority?: string): string {
  if (priority === "P0") return "#dc2626";
  if (priority === "P1") return "#ea580c";
  if (priority === "P2") return "#ca8a04";
  return "#2563eb";
}

export function CivicMap({
  markers,
  className = "h-[400px]",
}: {
  markers: CivicMapMarker[];
  className?: string;
}) {
  const firstMarker = markers[0];
  const center: [number, number] = firstMarker
    ? [firstMarker.lat, firstMarker.lng]
    : [18.5204, 73.8567];
  const zoom = markers.length <= 1 ? 15 : 12;

  return (
    <div className={`overflow-hidden rounded-xl border border-slate-200 shadow-sm ${className}`}>
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom
        className="h-full w-full"
        aria-label="Civic issue location map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {markers.map((marker) => {
          const color = markerColor(marker.priority);
          return (
            <CircleMarker
              key={marker.id}
              center={[marker.lat, marker.lng]}
              radius={10}
              pathOptions={{ color, fillColor: color, fillOpacity: 0.8, weight: 3 }}
            >
              <Popup>
                <div className="min-w-44">
                  <p className="font-semibold text-slate-900">{marker.title}</p>
                  {marker.subtitle && <p className="mt-1 text-sm text-slate-600">{marker.subtitle}</p>}
                  {marker.priority && <p className="mt-2 text-xs font-semibold text-slate-700">{marker.priority} priority</p>}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
