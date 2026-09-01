import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getIssue,
  reassignIssue,
  updateIssueStatus,
} from "../../api/issues";

import {
  unmergeComplaint,
} from "../../api/complaints";
import { CivicMap } from "../../components/maps/CivicMap";

import type {
  Issue,
  IssueStatus,
  PriorityLabel,
} from "../../types/issue";

export default function AdminIssueDetails() {
  const { id } = useParams();

  const issueId = Number(id);
  const validIssueId =
    Number.isFinite(issueId) &&
    issueId > 0;

  const [issue, setIssue] =
    useState<Issue | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const [department, setDepartment] =
    useState("");

  const [updatingStatus, setUpdatingStatus] =
    useState(false);

  const [reassigning, setReassigning] =
    useState(false);

  const [unmergingId, setUnmergingId] =
    useState<number | null>(null);

  useEffect(() => {
    if (!validIssueId) {
      return;
    }

    let cancelled = false;

    async function fetchIssue() {
      try {
        const data =
          await getIssue(issueId);

        if (cancelled) {
          return;
        }

        setIssue(data);
        setDepartment(
          data.department ?? "",
        );
        setError("");
        setLoading(false);
      } catch (err) {
        if (cancelled) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load issue",
        );

        setLoading(false);
      }
    }

    fetchIssue();

    return () => {
      cancelled = true;
    };
  }, [issueId, validIssueId]);

  async function handleStatusChange(
    status: IssueStatus,
  ) {
    if (!issue) {
      return;
    }

    setUpdatingStatus(true);
    setError("");

    try {
      const updated =
        await updateIssueStatus(
          issue.id,
          status,
        );

      setIssue(updated);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to update status",
      );
    } finally {
      setUpdatingStatus(false);
    }
  }

  async function handleReassign() {
    if (
      !issue ||
      !department.trim()
    ) {
      return;
    }

    setReassigning(true);
    setError("");

    try {
      const updated =
        await reassignIssue(
          issue.id,
          department.trim(),
        );

      setIssue(updated);
      setDepartment(
        updated.department ?? department,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to reassign issue",
      );
    } finally {
      setReassigning(false);
    }
  }

  async function handleUnmerge(
    complaintId: number,
  ) {
    if (
      !window.confirm(
        "Unlink this complaint from the current issue?",
      )
    ) {
      return;
    }

    setUnmergingId(complaintId);
    setError("");

    try {
      await unmergeComplaint(
        complaintId,
      );

      /*
       * Reload the issue because the backend
       * may have changed its complaint linkage.
       */
      const updated =
        await getIssue(issueId);

      setIssue(updated);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to unmerge complaint",
      );
    } finally {
      setUnmergingId(null);
    }
  }

  if (!validIssueId) {
    return (
      <div className="mx-auto max-w-3xl py-10">
        <div className="rounded-xl border border-red-200 bg-red-50 p-6">
          <h1 className="font-semibold text-red-900">
            Invalid issue ID
          </h1>

          <p className="mt-2 text-sm text-red-700">
            The issue identifier in the URL is
            invalid.
          </p>

          <Link
            to="/admin/complaints"
            className="mt-4 inline-block text-sm font-medium text-red-800 hover:underline"
          >
            ← Back to Issues
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
            Loading issue...
          </p>
        </div>
      </div>
    );
  }

  if (!issue) {
    return (
      <div className="mx-auto max-w-3xl py-10">
        <div className="rounded-xl border bg-white p-6 text-center">
          <h1 className="font-semibold text-gray-900">
            Issue not found
          </h1>

          <p className="mt-2 text-sm text-gray-500">
            {error ||
              "The requested issue could not be loaded."}
          </p>

          <Link
            to="/admin/complaints"
            className="mt-4 inline-block text-sm font-medium text-blue-600 hover:underline"
          >
            ← Back to Issues
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Navigation */}
      <Link
        to="/admin/complaints"
        className="inline-block text-sm font-medium text-blue-600 hover:underline"
      >
        ← Back to Issues
      </Link>

      {/* Header */}
      <section className="rounded-xl border bg-white p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <p className="text-sm text-gray-500">
              Issue #{issue.id}
            </p>

            <h1 className="mt-1 text-2xl font-bold text-gray-900">
              {issue.summary}
            </h1>

            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                {issue.categoryL1}
              </span>

              {issue.categoryL2 && (
                <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
                  {issue.categoryL2}
                </span>
              )}

              {issue.ward && (
                <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
                  {issue.ward}
                </span>
              )}
            </div>
          </div>

          <PriorityBadge
            priority={issue.priorityLabel}
          />
        </div>
      </section>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Overview */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <InfoCard
          label="Department"
          value={
            issue.department ||
            "Unassigned"
          }
        />

        <InfoCard
          label="Reports"
          value={String(
            issue.reportCount,
          )}
        />

        <InfoCard
          label="Priority Score"
          value={Number(
            issue.priorityScore,
          ).toFixed(2)}
        />

        <InfoCard
          label="Status"
          value={formatStatus(
            issue.status,
          )}
        />
      </section>

      {/* Status management */}
      <section className="rounded-xl border bg-white p-5 sm:p-6">
        <div>
          <h2 className="font-semibold text-gray-900">
            Issue Status
          </h2>

          <p className="mt-1 text-sm text-gray-500">
            Update the operational status of this
            issue.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {(
            [
              "OPEN",
              "ACK",
              "IN_PROGRESS",
              "RESOLVED",
            ] as IssueStatus[]
          ).map((status) => (
            <button
              key={status}
              type="button"
              disabled={updatingStatus}
              onClick={() =>
                handleStatusChange(
                  status,
                )
              }
              className={`min-h-10 rounded-lg border px-4 py-2 text-sm font-medium transition ${issue.status === status
                ? "border-blue-600 bg-blue-600 text-white"
                : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                } disabled:cursor-not-allowed disabled:opacity-50`}
            >
              {formatStatus(status)}
            </button>
          ))}
        </div>
      </section>

      {/* Department */}
      <section className="rounded-xl border bg-white p-5 sm:p-6">
        <div>
          <h2 className="font-semibold text-gray-900">
            Department Assignment
          </h2>

          <p className="mt-1 text-sm text-gray-500">
            Reassign the issue to another department.
          </p>
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <select
            value={department}
            onChange={(event) =>
              setDepartment(
                event.target.value,
              )
            }
            className="min-h-11 flex-1 rounded-lg border border-gray-300 bg-white px-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          >
            <option value="">
              Select department
            </option>

            <option value="Water Supply">
              Water Supply
            </option>

            <option value="Roads & Infrastructure">
              Roads & Infrastructure
            </option>

            <option value="Electricity">
              Electricity
            </option>

            <option value="Sanitation & Waste">
              Sanitation & Waste
            </option>

            <option value="Public Safety">
              Public Safety
            </option>

            <option value="Traffic">
              Traffic
            </option>

            <option value="Street Lighting">
              Street Lighting
            </option>

            <option value="Public Health">
              Public Health
            </option>

            <option value="Other">
              Other
            </option>
          </select>

          <button
            type="button"
            disabled={
              reassigning ||
              !department.trim()
            }
            onClick={handleReassign}
            className="min-h-11 rounded-lg bg-gray-900 px-5 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {reassigning
              ? "Reassigning..."
              : "Reassign"}
          </button>
        </div>
      </section>

      {/* Priority analysis */}
      <section className="rounded-xl border bg-white p-5 sm:p-6">
        <div>
          <h2 className="font-semibold text-gray-900">
            Priority Analysis
          </h2>

          <p className="mt-1 text-sm text-gray-500">
            Explainable factors produced by the priority
            engine.
          </p>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl bg-gray-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Priority
            </p>

            <div className="mt-2">
              <PriorityBadge
                priority={
                  issue.priorityLabel
                }
              />
            </div>
          </div>

          <div className="rounded-xl bg-gray-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Score
            </p>

            <p className="mt-2 text-2xl font-bold text-gray-900">
              {Number(
                issue.priorityScore,
              ).toFixed(2)}
            </p>
          </div>
        </div>

        <div className="mt-5">
          <p className="text-sm font-medium text-gray-700">
            Why this priority?
          </p>

          <p className="mt-2 rounded-lg bg-gray-50 p-4 text-sm leading-6 text-gray-600">
            {issue.priorityWhy ||
              "No priority explanation was provided by the backend."}
          </p>
        </div>

        {issue.factors &&
          Object.keys(issue.factors)
            .length > 0 && (
            <div className="mt-5">
              <p className="text-sm font-medium text-gray-700">
                Factors
              </p>

              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(
                  issue.factors,
                ).map(
                  ([factor, value]) => (
                    <div
                      key={factor}
                      className="rounded-lg border bg-white p-4"
                    >
                      <p className="text-xs text-gray-500">
                        {formatLabel(
                          factor,
                        )}
                      </p>

                      <p className="mt-1 text-lg font-semibold text-gray-900">
                        {typeof value ===
                          "number"
                          ? value.toFixed(
                            2,
                          )
                          : String(value)}
                      </p>
                    </div>
                  ),
                )}
              </div>
            </div>
          )}
      </section>

      {/* Location */}
      <section className="rounded-xl border bg-white p-5 sm:p-6">
        <div>
          <h2 className="font-semibold text-gray-900">
            Location
          </h2>

          <p className="mt-1 text-sm text-gray-500">
            Geographic information associated with the
            issue.
          </p>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <InfoCard
            label="Latitude"
            value={Number(
              issue.lat,
            ).toFixed(6)}
          />

          <InfoCard
            label="Longitude"
            value={Number(
              issue.lng,
            ).toFixed(6)}
          />

          <InfoCard
            label="Ward"
            value={
              issue.ward ||
              "Unknown"
            }
          />
        </div>

        <div className="mt-4">
          <CivicMap
            markers={[{
              id: issue.id,
              lat: issue.lat,
              lng: issue.lng,
              title: issue.summary,
              subtitle: issue.ward,
              priority: issue.priorityLabel,
            }]}
          />
        </div>
      </section>

      {/* Linked complaints */}
      <section className="rounded-xl border bg-white p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold text-gray-900">
              Linked Complaints
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              Individual citizen reports associated with
              this underlying issue.
            </p>
          </div>

          <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
            {issue.complaints?.length ??
              issue.reportCount}{" "}
            reports
          </span>
        </div>

        {!issue.complaints ||
          issue.complaints.length ===
          0 ? (
          <div className="mt-5 rounded-xl bg-gray-50 p-6 text-center">
            <p className="text-sm font-medium text-gray-700">
              Complaint details unavailable
            </p>

            <p className="mt-1 text-xs text-gray-500">
              The backend returned the issue but did not
              include its linked complaint records.
            </p>
          </div>
        ) : (
          <div className="mt-5 space-y-3">
            {issue.complaints.map(
              (complaint) => (
                <div
                  key={complaint.id}
                  className="rounded-xl border p-4"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-gray-900">
                          Complaint #
                          {complaint.id}
                        </p>

                        <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600">
                          {complaint.channel}
                        </span>

                        <span className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">
                          {complaint.lang}
                        </span>
                      </div>

                      <p className="mt-3 text-sm leading-6 text-gray-700">
                        {complaint.text}
                      </p>

                      {complaint.textEn &&
                        complaint.textEn !==
                        complaint.text && (
                          <div className="mt-3 rounded-lg bg-gray-50 p-3">
                            <p className="text-xs font-medium text-gray-500">
                              English normalization
                            </p>

                            <p className="mt-1 text-sm text-gray-700">
                              {
                                complaint.textEn
                              }
                            </p>
                          </div>
                        )}

                      <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-500">
                        <span>
                          Location:{" "}
                          {Number(
                            complaint.lat,
                          ).toFixed(5)}
                          ,{" "}
                          {Number(
                            complaint.lng,
                          ).toFixed(5)}
                        </span>

                        {complaint.dedupScore !==
                          undefined && (
                            <span>
                              Dedup score:{" "}
                              {Number(
                                complaint.dedupScore,
                              ).toFixed(2)}
                            </span>
                          )}

                        {complaint.state && (
                          <span>
                            State:{" "}
                            {complaint.state}
                          </span>
                        )}
                      </div>

                      {complaint
                        .dedupReasons
                        ?.length >
                        0 && (
                          <div className="mt-3">
                            <p className="text-xs font-medium text-gray-500">
                              Duplicate detection
                              reasons
                            </p>

                            <ul className="mt-1 list-disc pl-5 text-xs text-gray-600">
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

                    <button
                      type="button"
                      disabled={
                        unmergingId ===
                        complaint.id
                      }
                      onClick={() =>
                        handleUnmerge(
                          complaint.id,
                        )
                      }
                      className="shrink-0 rounded-lg border border-orange-300 px-3 py-2 text-xs font-medium text-orange-700 hover:bg-orange-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {unmergingId ===
                        complaint.id
                        ? "Unmerging..."
                        : "Unmerge"}
                    </button>
                  </div>
                </div>
              ),
            )}
          </div>
        )}
      </section>
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

      <p className="mt-2 font-semibold text-gray-900">
        {value}
      </p>
    </div>
  );
}

function PriorityBadge({
  priority,
}: {
  priority: PriorityLabel;
}) {
  const styles: Record<
    PriorityLabel,
    string
  > = {
    P0: "bg-red-100 text-red-800",
    P1: "bg-orange-100 text-orange-800",
    P2: "bg-yellow-100 text-yellow-800",
    P3: "bg-green-100 text-green-800",
  };

  const labels: Record<
    PriorityLabel,
    string
  > = {
    P0: "Critical",
    P1: "High",
    P2: "Medium",
    P3: "Low",
  };

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1.5 text-xs font-semibold ${styles[priority]}`}
    >
      {priority} — {labels[priority]}
    </span>
  );
}

function formatStatus(
  status: IssueStatus,
): string {
  switch (status) {
    case "OPEN":
      return "Open";

    case "ACK":
      return "Acknowledged";

    case "IN_PROGRESS":
      return "In Progress";

    case "RESOLVED":
      return "Resolved";

    default:
      return status;
  }
}

function formatLabel(
  value: string,
): string {
  return value
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase(),
    );
}
