import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  getIssues,
  updateIssueStatus,
} from "../../api/issues";

import type {
  Issue,
  IssueStatus,
  PriorityLabel,
} from "../../types/issue";

export default function AdminIssues() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [priority, setPriority] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function fetchIssues() {
      try {
        const data = await getIssues({
          priority: priority || undefined,
          dept: department || undefined,
          status: status || undefined,
        });

        if (cancelled) return;

        setIssues(data);
        setError("");
        setLoading(false);
      } catch (err) {
        if (cancelled) return;

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load issues",
        );

        setLoading(false);
      }
    }

    fetchIssues();

    return () => {
      cancelled = true;
    };
  }, [priority, department, status]);

  async function handleStatusChange(
    issueId: number,
    newStatus: IssueStatus,
  ) {
    try {
      const updated = await updateIssueStatus(
        issueId,
        newStatus,
      );

      setIssues((current) =>
        current.map((issue) =>
          issue.id === issueId
            ? updated
            : issue,
        ),
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to update issue status",
      );
    }
  }

  function clearFilters() {
    setPriority("");
    setDepartment("");
    setStatus("");
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <section>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-blue-600">
              Authority
            </p>

            <h1 className="mt-1 text-2xl font-bold text-gray-900">
              Issues
            </h1>

            <p className="mt-1 text-sm text-gray-500">
              Review and manage citizen complaints
              grouped into underlying civic issues.
            </p>
          </div>

          <div className="rounded-lg bg-white px-4 py-3 shadow-sm ring-1 ring-gray-200">
            <p className="text-xs text-gray-500">
              Showing
            </p>

            <p className="text-xl font-bold text-gray-900">
              {issues.length}
            </p>
          </div>
        </div>
      </section>

      {/* Filters */}
      <section className="rounded-xl border bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-gray-900">
              Filters
            </h2>

            <p className="text-xs text-gray-500">
              Narrow issues by priority, department or
              status.
            </p>
          </div>

          {(priority ||
            department ||
            status) && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-sm font-medium text-blue-600 hover:underline"
              >
                Clear filters
              </button>
            )}
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Filter
            label="Priority"
            value={priority}
            onChange={setPriority}
            options={[
              ["", "All priorities"],
              ["P0", "P0 — Critical"],
              ["P1", "P1 — High"],
              ["P2", "P2 — Medium"],
              ["P3", "P3 — Low"],
            ]}
          />

          <Filter
            label="Department"
            value={department}
            onChange={setDepartment}
            options={[
              ["", "All departments"],
              [
                "Water Supply",
                "Water Supply",
              ],
              [
                "Roads & Infrastructure",
                "Roads & Infrastructure",
              ],
              [
                "Electricity",
                "Electricity",
              ],
              [
                "Sanitation & Waste",
                "Sanitation & Waste",
              ],
              [
                "Public Safety",
                "Public Safety",
              ],
              ["Traffic", "Traffic"],
              [
                "Street Lighting",
                "Street Lighting",
              ],
              [
                "Public Health",
                "Public Health",
              ],
            ]}
          />

          <Filter
            label="Status"
            value={status}
            onChange={setStatus}
            options={[
              ["", "All statuses"],
              ["OPEN", "Open"],
              ["ACK", "Acknowledged"],
              [
                "IN_PROGRESS",
                "In Progress",
              ],
              ["RESOLVED", "Resolved"],
            ]}
          />
        </div>
      </section>

      {/* Error */}
      {error && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">
            {error}
          </p>

          <button
            type="button"
            onClick={() => setError("")}
            className="text-sm font-medium text-red-700 hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex min-h-64 items-center justify-center rounded-xl border bg-white">
          <div className="text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />

            <p className="mt-3 text-sm text-gray-500">
              Loading issues...
            </p>
          </div>
        </div>
      ) : issues.length === 0 ? (
        /* Empty state */
        <div className="rounded-xl border border-dashed bg-white p-12 text-center">
          <h3 className="font-semibold text-gray-900">
            No issues found
          </h3>

          <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
            No issues match the current filters.
            Try clearing one or more filters.
          </p>

          {(priority ||
            department ||
            status) && (
              <button
                type="button"
                onClick={clearFilters}
                className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Clear filters
              </button>
            )}
        </div>
      ) : (
        /* Issue table */
        <section className="overflow-hidden rounded-xl border bg-white">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1050px] text-left text-sm">
              <thead className="border-b bg-gray-50">
                <tr>
                  <th className="p-4 font-semibold text-gray-700">
                    Issue
                  </th>

                  <th className="p-4 font-semibold text-gray-700">
                    Department
                  </th>

                  <th className="p-4 font-semibold text-gray-700">
                    Reports
                  </th>

                  <th className="p-4 font-semibold text-gray-700">
                    Priority
                  </th>

                  <th className="p-4 font-semibold text-gray-700">
                    Status
                  </th>

                  <th className="p-4 font-semibold text-gray-700">
                    Review
                  </th>

                  <th className="p-4 font-semibold text-gray-700">
                    Action
                  </th>
                </tr>
              </thead>

              <tbody>
                {issues.map((issue) => (
                  <IssueRow
                    key={issue.id}
                    issue={issue}
                    onStatusChange={
                      handleStatusChange
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function IssueRow({
  issue,
  onStatusChange,
}: {
  issue: Issue;
  onStatusChange: (
    issueId: number,
    status: IssueStatus,
  ) => Promise<void>;
}) {
  return (
    <tr className="border-b last:border-0 hover:bg-gray-50">
      {/* Issue */}
      <td className="max-w-[360px] p-4">
        <Link
          to={`/admin/complaints/${issue.id}`}
          className="block"
        >
          <p className="font-semibold text-gray-900 hover:text-blue-600">
            {issue.summary}
          </p>

          <p className="mt-1 text-xs text-gray-500">
            Issue #{issue.id}
          </p>

          <p className="mt-1 text-xs text-gray-500">
            {issue.categoryL1}

            {issue.categoryL2 &&
              ` / ${issue.categoryL2}`}
          </p>
        </Link>
      </td>

      {/* Department */}
      <td className="p-4">
        <p className="font-medium text-gray-900">
          {issue.department ||
            "Unassigned"}
        </p>

        {issue.ward && (
          <p className="mt-1 text-xs text-gray-500">
            {issue.ward}
          </p>
        )}
      </td>

      {/* Reports */}
      <td className="p-4">
        <div>
          <p className="font-semibold text-gray-900">
            {issue.reportCount}
          </p>

          <p className="text-xs text-gray-500">
            citizen reports
          </p>
        </div>
      </td>

      {/* Priority */}
      <td className="p-4">
        <PriorityBadge
          priority={issue.priorityLabel}
        />

        <p className="mt-2 text-xs text-gray-500">
          Score{" "}
          {Number(
            issue.priorityScore,
          ).toFixed(1)}
        </p>
      </td>

      {/* Status */}
      <td className="p-4">
        <select
          value={issue.status}
          onChange={(event) =>
            onStatusChange(
              issue.id,
              event.target
                .value as IssueStatus,
            )
          }
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs font-medium outline-none focus:border-blue-500"
        >
          <option value="OPEN">
            Open
          </option>

          <option value="ACK">
            Acknowledged
          </option>

          <option value="IN_PROGRESS">
            In Progress
          </option>

          <option value="RESOLVED">
            Resolved
          </option>
        </select>
      </td>

      {/* Review */}
      <td className="p-4">
        {issue.needsReview ? (
          <span className="rounded-full bg-orange-100 px-2.5 py-1 text-xs font-semibold text-orange-800">
            Review
          </span>
        ) : (
          <span className="rounded-full bg-green-100 px-2.5 py-1 text-xs font-semibold text-green-800">
            OK
          </span>
        )}
      </td>

      {/* Action */}
      <td className="p-4">
        <Link
          to={`/admin/complaints/${issue.id}`}
          className="inline-block rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          View
        </Link>
      </td>
    </tr>
  );
}

function Filter({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-gray-700">
        {label}
      </span>

      <select
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
        className="min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
      >
        {options.map(
          ([optionValue, optionLabel]) => (
            <option
              key={optionValue}
              value={optionValue}
            >
              {optionLabel}
            </option>
          ),
        )}
      </select>
    </label>
  );
}

function PriorityBadge({
  priority,
}: {
  priority: PriorityLabel;
}) {
  const labels: Record<
    PriorityLabel,
    string
  > = {
    P0: "Critical",
    P1: "High",
    P2: "Medium",
    P3: "Low",
  };

  const styles: Record<
    PriorityLabel,
    string
  > = {
    P0: "bg-red-100 text-red-800",
    P1: "bg-orange-100 text-orange-800",
    P2: "bg-yellow-100 text-yellow-800",
    P3: "bg-green-100 text-green-800",
  };

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${styles[priority]}`}
    >
      {priority} — {labels[priority]}
    </span>
  );
}