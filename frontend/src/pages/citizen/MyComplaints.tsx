import {
  useEffect,
  useState,
} from "react";

import ComplaintCard from "../../components/complaints/ComplaintCard";

import {
  getComplaint,
} from "../../api/complaints";

import type {
  Complaint,
} from "../../types/complaint";

export default function MyComplaints() {
  const [complaints, setComplaints] =
    useState<Complaint[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadComplaints() {
      const stored =
        localStorage.getItem(
          "my_complaint_ids",
        );

      if (!stored) {
        if (!cancelled) {
          setLoading(false);
        }

        return;
      }

      let ids: number[];

      try {
        const parsed =
          JSON.parse(stored);

        if (!Array.isArray(parsed)) {
          ids = [];
        } else {
          ids = parsed.filter(
            (value): value is number =>
              typeof value === "number",
          );
        }
      } catch {
        if (!cancelled) {
          setError(
            "Saved complaint history could not be read.",
          );

          setLoading(false);
        }

        return;
      }

      if (ids.length === 0) {
        if (!cancelled) {
          setLoading(false);
        }

        return;
      }

      try {
        const results =
          await Promise.allSettled(
            ids.map((id) =>
              getComplaint(id),
            ),
          );

        const successful: Complaint[] = [];

        for (const result of results) {
          if (result.status === "fulfilled") {
            successful.push(result.value);
          }
        }

        const failedCount =
          results.length -
          successful.length;

        setComplaints(successful);

        if (failedCount > 0) {
          setError(
            `${failedCount} complaint${failedCount === 1
              ? ""
              : "s"
            } could not be loaded.`,
          );
        } else {
          setError("");
        }
      } catch (err) {
        if (cancelled) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load complaints",
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadComplaints();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
      {/* Header */}
      <section>
        <p className="text-sm font-medium text-blue-600">
          Citizen Portal
        </p>

        <h1 className="mt-1 text-2xl font-bold text-gray-900">
          My Complaints
        </h1>

        <p className="mt-1 text-sm leading-6 text-gray-500">
          Track complaints submitted through this browser.
        </p>
      </section>

      {/* Error */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-orange-200 bg-orange-50 p-4 text-sm text-orange-800"
        >
          {error}
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex min-h-64 items-center justify-center rounded-xl border bg-white">
          <div className="text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />

            <p className="mt-3 text-sm text-gray-500">
              Loading complaints...
            </p>
          </div>
        </div>
      ) : complaints.length === 0 ? (
        /* Empty */
        <div className="rounded-xl border border-dashed bg-white p-10 text-center">
          <h2 className="font-semibold text-gray-900">
            No complaints yet
          </h2>

          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-gray-500">
            Complaints submitted from this browser will
            appear here.
          </p>
        </div>
      ) : (
        /* Complaint cards */
        <div className="grid gap-4 md:grid-cols-2">
          {complaints.map(
            (complaint) => (
              <ComplaintCard
                key={complaint.id}
                complaint={complaint}
              />
            ),
          )}
        </div>
      )}
    </div>
  );
}