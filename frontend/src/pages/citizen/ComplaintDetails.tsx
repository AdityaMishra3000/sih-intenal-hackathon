import {
  useEffect,
  useState,
} from "react";

import {
  Link,
  useParams,
} from "react-router-dom";

import {
  getComplaint,
} from "../../api/complaints";

import ComplaintStatus from "../../components/complaints/ComplaintStatus";

import type {
  Complaint,
} from "../../types/complaint";

export default function ComplaintDetails() {
  const { id } = useParams();

  const complaintId = Number(id);

  const validId =
    Number.isFinite(complaintId) &&
    complaintId > 0;

  const [complaint, setComplaint] =
    useState<Complaint | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  useEffect(() => {
    if (!validId) {
      return;
    }

    let cancelled = false;

    async function fetchComplaint() {
      try {
        const data =
          await getComplaint(
            complaintId,
          );

        if (cancelled) {
          return;
        }

        setComplaint(data);
        setError("");
        setLoading(false);
      } catch (err) {
        if (cancelled) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load complaint",
        );

        setLoading(false);
      }
    }

    fetchComplaint();

    return () => {
      cancelled = true;
    };
  }, [complaintId, validId]);

  if (!validId) {
    return (
      <div className="mx-auto max-w-3xl p-4 sm:p-6">
        <div className="rounded-xl border border-red-200 bg-red-50 p-5">
          <h1 className="font-semibold text-red-900">
            Invalid complaint ID
          </h1>

          <p className="mt-2 text-sm text-red-700">
            The complaint ID in the URL is invalid.
          </p>

          <Link
            to="/citizen/complaints"
            className="mt-4 inline-block text-sm font-medium text-red-700 hover:underline"
          >
            ← Back to My Complaints
          </Link>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />

          <p className="mt-3 text-sm text-gray-500">
            Loading complaint...
          </p>
        </div>
      </div>
    );
  }

  if (!complaint) {
    return (
      <div className="mx-auto max-w-3xl p-4 sm:p-6">
        <div className="rounded-xl border bg-white p-6 text-center">
          <h1 className="font-semibold text-gray-900">
            Complaint not found
          </h1>

          <p className="mt-2 text-sm text-gray-500">
            {error ||
              "The requested complaint could not be loaded."}
          </p>

          <Link
            to="/citizen/complaints"
            className="mt-4 inline-block text-sm font-medium text-blue-600 hover:underline"
          >
            ← Back to My Complaints
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <Link
        to="/citizen/complaints"
        className="text-sm font-medium text-blue-600 hover:underline"
      >
        ← Back to My Complaints
      </Link>

      {/* Header */}
      <section className="rounded-xl border bg-white p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Complaint #{complaint.id}
            </p>

            <h1 className="mt-2 text-xl font-bold text-gray-900">
              Your Complaint
            </h1>
          </div>

          <ComplaintStatus
            state={complaint.state}
          />
        </div>

        <div className="mt-5 rounded-xl bg-gray-50 p-4">
          <p className="text-sm leading-6 text-gray-800">
            {complaint.text}
          </p>
        </div>

        {complaint.textEn &&
          complaint.textEn.trim() !==
          complaint.text.trim() && (
            <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-4">
              <p className="text-xs font-semibold text-blue-700">
                Normalized Text
              </p>

              <p className="mt-2 text-sm leading-6 text-blue-900">
                {complaint.textEn}
              </p>
            </div>
          )}
      </section>

      {/* Metadata */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <InfoCard
          label="Issue"
          value={
            complaint.issueId
              ? `Issue #${complaint.issueId}`
              : "Not assigned yet"
          }
        />

        <InfoCard
          label="Language"
          value={
            complaint.lang ||
            "Unknown"
          }
        />

        <InfoCard
          label="Channel"
          value={formatLabel(
            complaint.channel,
          )}
        />

        <InfoCard
          label="Submitted"
          value={formatDate(
            complaint.createdAt,
          )}
        />

        <InfoCard
          label="Latitude"
          value={Number(
            complaint.lat,
          ).toFixed(6)}
        />

        <InfoCard
          label="Longitude"
          value={Number(
            complaint.lng,
          ).toFixed(6)}
        />
      </section>

      {/* Processing status */}
      <section className="rounded-xl border bg-white p-5 sm:p-6">
        <h2 className="font-semibold text-gray-900">
          Processing Status
        </h2>

        <div className="mt-4">
          <ComplaintStatus
            state={complaint.state}
          />
        </div>

        <p className="mt-3 text-sm leading-6 text-gray-500">
          Your complaint may continue to be enriched by
          language normalization, classification, embedding
          and duplicate detection services.
        </p>
      </section>

      {/* Duplicate detection */}
      <section className="rounded-xl border bg-white p-5 sm:p-6">
        <h2 className="font-semibold text-gray-900">
          Duplicate Detection
        </h2>

        <p className="mt-1 text-sm text-gray-500">
          AI-generated information about whether this
          complaint resembles an existing report.
        </p>

        {complaint.dedupScore !==
          undefined ? (
          <div className="mt-5">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">
                Similarity score
              </span>

              <span className="font-semibold text-gray-900">
                {Number(
                  complaint.dedupScore,
                ).toFixed(2)}
              </span>
            </div>

            {complaint.dedupReasons?.length >
              0 && (
                <div className="mt-4">
                  <p className="text-sm font-medium text-gray-700">
                    Detection reasons
                  </p>

                  <ul className="mt-2 list-disc pl-5 text-sm text-gray-600">
                    {complaint.dedupReasons.map(
                      (
                        reason,
                        index,
                      ) => (
                        <li
                          key={`${complaint.id}-reason-${index}`}
                        >
                          {reason}
                        </li>
                      ),
                    )}
                  </ul>
                </div>
              )}
          </div>
        ) : (
          <div className="mt-4 rounded-lg bg-gray-50 p-4 text-sm text-gray-500">
            Duplicate analysis is not available yet.
          </div>
        )}
      </section>

      {/* Linked issue */}
      {complaint.issueId && (
        <section className="rounded-xl border bg-white p-5 sm:p-6">
          <h2 className="font-semibold text-gray-900">
            Linked Issue
          </h2>

          <p className="mt-1 text-sm text-gray-500">
            This complaint has been associated with an
            underlying civic issue.
          </p>

          <Link
            to={`/citizen/issues/${complaint.issueId}`}
            className="mt-4 inline-flex rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            View Issue #{complaint.issueId}
          </Link>
        </section>
      )}
    </div>
  );
}

function InfoCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </p>

      <p className="mt-2 font-medium text-gray-900">
        {value}
      </p>
    </div>
  );
}

function formatLabel(
  value: string,
): string {
  if (!value) {
    return "Unknown";
  }

  return value
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase(),
    );
}

function formatDate(
  value: string,
): string {
  if (!value) {
    return "Unknown";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}