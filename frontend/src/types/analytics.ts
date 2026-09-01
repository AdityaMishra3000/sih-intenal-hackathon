export interface AnalyticsStats {
  totalComplaints: number;
  uniqueIssues: number;
  duplicatesCollapsed: number;
}

export interface Hotspot {
  lat: number;
  lng: number;

  count: number;
  totalReports: number;
  meanPriority: number;

  zScore: number;
  trendPercent: number;

  category?: string;
  ward?: string;
}