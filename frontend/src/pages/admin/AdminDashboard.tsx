import { useEffect, useState } from "react";
import { getStats } from "../../api/analytics";
import { getHotspots } from "../../api/analytics";
import { CivicMap } from "../../components/maps/CivicMap";

interface Stats {
  total_complaints?: number;
  unique_issues?: number;
  duplicates_collapsed?: number;

  totalComplaints?: number;
  uniqueIssues?: number;
  duplicatesCollapsed?: number;

  [key: string]: unknown;
}

interface Hotspot {
  lat: number;
  lng: number;
  count?: number;
  total_reports?: number;
  totalReports?: number;
  mean_priority?: number;
  meanPriority?: number;
  z_score?: number;
  zScore?: number;
  trend_percent?: number;
  trendPercent?: number;
  category?: string;
  ward?: string;
}

export function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      try {
        const [statsData, hotspotData] =
          await Promise.all([
            getStats(),
            getHotspots(),
          ]);

        setStats(statsData as Stats);
        setHotspots(hotspotData);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load dashboard",
        );
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <p className="text-sm text-gray-500">
          Loading dashboard...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  const totalComplaints =
    stats?.total_complaints ??
    stats?.totalComplaints ??
    0;

  const uniqueIssues =
    stats?.unique_issues ??
    stats?.uniqueIssues ??
    0;

  const duplicatesCollapsed =
    stats?.duplicates_collapsed ??
    stats?.duplicatesCollapsed ??
    0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold text-gray-900">
          Authority Dashboard
        </h1>

        <p className="mt-1 text-sm text-gray-500">
          Monitor civic issues, complaint volume,
          duplicates and geographic hotspots.
        </p>
      </section>

      {/* Statistics */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          title="Total Complaints"
          value={totalComplaints}
        />

        <StatCard
          title="Unique Issues"
          value={uniqueIssues}
        />

        <StatCard
          title="Duplicates Collapsed"
          value={duplicatesCollapsed}
        />
      </section>

      {/* Hotspots */}
      <section className="rounded-xl border bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-gray-900">
              Geographic Hotspots
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              Areas with concentrated complaint activity.
            </p>
          </div>

          <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
            {hotspots.length} hotspots
          </span>
        </div>

        <div className="mt-5">
          <CivicMap
            markers={hotspots.map((hotspot, index) => ({
              id: index,
              lat: hotspot.lat,
              lng: hotspot.lng,
              title: hotspot.category ?? "Civic hotspot",
              subtitle: hotspot.ward ?? "Pune",
            }))}
          />
        </div>
      </section>

      {/* Hotspot data preview */}
      {hotspots.length > 0 && (
        <section className="rounded-xl border bg-white p-5">
          <h2 className="font-semibold text-gray-900">
            Hotspot Data
          </h2>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead className="border-b bg-gray-50">
                <tr>
                  <th className="p-3">Location</th>
                  <th className="p-3">Reports</th>
                  <th className="p-3">
                    Mean Priority
                  </th>
                  <th className="p-3">Z-Score</th>
                  <th className="p-3">Trend</th>
                </tr>
              </thead>

              <tbody>
                {hotspots.map(
                  (hotspot, index) => {
                    const reports =
                      hotspot.count ??
                      hotspot.total_reports ??
                      hotspot.totalReports ??
                      0;

                    const priority =
                      hotspot.mean_priority ??
                      hotspot.meanPriority ??
                      0;

                    const zScore =
                      hotspot.z_score ??
                      hotspot.zScore ??
                      0;

                    const trend =
                      hotspot.trend_percent ??
                      hotspot.trendPercent ??
                      0;

                    return (
                      <tr
                        key={`${hotspot.lat}-${hotspot.lng}-${index}`}
                        className="border-b last:border-0"
                      >
                        <td className="p-3">
                          <div>
                            <p className="font-medium">
                              {hotspot.ward ??
                                "Unknown area"}
                            </p>

                            <p className="text-xs text-gray-500">
                              {hotspot.lat.toFixed(5)},{" "}
                              {hotspot.lng.toFixed(5)}
                            </p>
                          </div>
                        </td>

                        <td className="p-3">
                          {reports}
                        </td>

                        <td className="p-3">
                          {Number(priority).toFixed(2)}
                        </td>

                        <td className="p-3">
                          {Number(zScore).toFixed(2)}
                        </td>

                        <td className="p-3">
                          {Number(trend).toFixed(1)}%
                        </td>
                      </tr>
                    );
                  },
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function StatCard({
  title,
  value,
}: {
  title: string;
  value: number;
}) {
  return (
    <div className="rounded-xl border bg-white p-5">
      <p className="text-sm text-gray-500">
        {title}
      </p>

      <p className="mt-2 text-3xl font-bold text-gray-900">
        {value.toLocaleString()}
      </p>
    </div>
  );
}
