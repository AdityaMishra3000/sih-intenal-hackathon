import { apiRequest } from "./client";
import type { Hotspot } from "../types/analytics";

export async function getHotspots(): Promise<Hotspot[]> {
  return apiRequest<Hotspot[]>(
    "/analytics/hotspots",
  );
}

export async function getStats() {
  return apiRequest(
    "/analytics/stats",
  );
}