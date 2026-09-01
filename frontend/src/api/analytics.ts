import { apiRequest } from "./client";
import type { Hotspot } from "../types/analytics";

interface BackendHotspot {
  center_lat?: number;
  center_lng?: number;
  lat?: number;
  lng?: number;
  issue_count?: number;
  total_reports?: number;
  mean_priority?: number;
  z_score?: number;
  trend_pct?: number;
  category?: string;
  ward?: string;
}

export async function getHotspots(): Promise<Hotspot[]> {
  const response = await apiRequest<BackendHotspot[]>(
    "/analytics/hotspots",
  );
  return response.map((hotspot) => ({
    lat: hotspot.center_lat ?? hotspot.lat ?? 0,
    lng: hotspot.center_lng ?? hotspot.lng ?? 0,
    count: hotspot.issue_count ?? 0,
    totalReports: hotspot.total_reports ?? 0,
    meanPriority: hotspot.mean_priority ?? 0,
    zScore: hotspot.z_score ?? 0,
    trendPercent: hotspot.trend_pct ?? 0,
    category: hotspot.category,
    ward: hotspot.ward,
  }));
}

export async function getStats() {
  return apiRequest(
    "/analytics/stats",
  );
}
