import { Link } from "react-router-dom";

import type { Complaint } from "../../types/complaint";

interface ComplaintCardProps {
  complaint: Complaint;
}

export default function ComplaintCard({
  complaint,
}: ComplaintCardProps) {
  return (
    <article className="rounded-xl border bg-white p-5 shadow-sm transition hover:shadow-md">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Complaint #{complaint.id}
          </p>

          <h3 className="mt-1 line-clamp-2 text-base font-semibold text-gray-900">
            {complaint.text}
          </h3>
        </div>

        <ComplaintState state={complaint.state} />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Metadata
          label="Channel"
          value={formatChannel(complaint.channel)}
        />

        <Metadata
          label="Language"
          value={complaint.lang || "Unknown"}
        />

        <Metadata
          label="Submitted"
          value={formatDate(complaint.createdAt)}
        />

        <Metadata
          label="Issue"
          value={
            complaint.issueId
              ? `Issue #${complaint.issueId}`
              : "Not assigned"
          }
        />
      </div>

      {complaint.textEn &&
        complaint.textEn.trim() !== complaint.text.trim() && (
          <div className="mt-4 rounded-lg bg-gray-50 p-3">
            <p className="text-xs font-medium text-gray-500">
              Normalized text
            </p>

            <p className="mt-1 text-sm text-gray-700">
              {complaint.textEn}
            </p>
          </div>
        )}

      {complaint.dedupScore !== undefined && (
        <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-medium text-blue-800">
              Duplicate detection
            </p>

            <span className="text-xs font-semibold text-blue-800">
              Score {Number(complaint.dedupScore).toFixed(2)}
            </span>
          </div>

          {complaint.dedupReasons?.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-xs text-blue-700">
              {complaint.dedupReasons.map((reason, index) => (
                <li key={`${complaint.id}-dedup-${index}`}>
                  {reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-3 text-xs text-gray-500">
        <span>
          Location: {Number(complaint.lat).toFixed(5)},{" "}
          {Number(complaint.lng).toFixed(5)}
        </span>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {complaint.issueId ? (
          <Link
            to={`/admin/complaints/${complaint.issueId}`}
            className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            View Issue
          </Link>
        ) : (
          <span className="rounded-lg bg-gray-100 px-3 py-2 text-xs font-medium text-gray-500">
            Awaiting issue assignment
          </span>
        )}
      </div>
    </article>
  );
}

function Metadata({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg bg-gray-50 p-3">
      <p className="text-xs text-gray-500">{label}</p>

      <p className="mt-1 text-sm font-medium text-gray-900">
        {value}
      </p>
    </div>
  );
}

function ComplaintState({
  state,
}: {
  state: string;
}) {
  const normalized = state?.toUpperCase() || "UNKNOWN";

  const styles: Record<string, string> = {
    NEW: "bg-blue-100 text-blue-800",
    PROCESSING: "bg-yellow-100 text-yellow-800",
    PROCESSED: "bg-green-100 text-green-800",
    LINKED: "bg-purple-100 text-purple-800",
    REVIEW: "bg-orange-100 text-orange-800",
    RESOLVED: "bg-green-100 text-green-800",
    ERROR: "bg-red-100 text-red-800",
  };

  return (
    <span
      className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${styles[normalized] ?? "bg-gray-100 text-gray-700"
        }`}
    >
      {formatState(normalized)}
    </span>
  );
}

function formatState(state: string): string {
  return state
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatChannel(channel: string): string {
  if (!channel) {
    return "Unknown";
  }

  return channel
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDate(value: string): string {
  if (!value) {
    return "Unknown";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}