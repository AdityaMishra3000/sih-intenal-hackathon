import { useEffect, useMemo, useState } from "react";

import { getIssues } from "../../api/issues";

import type { Issue } from "../../types/issue";

interface DepartmentSummary {
  name: string;
  totalIssues: number;
  totalReports: number;
  criticalIssues: number;
  resolvedIssues: number;
}

export function AdminDepartments() {
  const [issues, setIssues] =
    useState<Issue[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  useEffect(() => {
    getIssues()
      .then(setIssues)
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load department data",
        );
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const departments =
    useMemo<DepartmentSummary[]>(() => {
      const map =
        new Map<
          string,
          DepartmentSummary
        >();

      for (const issue of issues) {
        const name =
          issue.department ||
          "Unassigned";

        const existing =
          map.get(name);

        if (existing) {
          existing.totalIssues += 1;

          existing.totalReports +=
            issue.reportCount;

          if (
            issue.priorityLabel ===
            "P0"
          ) {
            existing.criticalIssues += 1;
          }

          if (
            issue.status ===
            "RESOLVED"
          ) {
            existing.resolvedIssues += 1;
          }
        } else {
          map.set(name, {
            name,
            totalIssues: 1,
            totalReports:
              issue.reportCount,
            criticalIssues:
              issue.priorityLabel ===
                "P0"
                ? 1
                : 0,
            resolvedIssues:
              issue.status ===
                "RESOLVED"
                ? 1
                : 0,
          });
        }
      }

      return Array.from(
        map.values(),
      ).sort(
        (a, b) =>
          b.totalIssues -
          a.totalIssues,
      );
    }, [issues]);

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <p className="text-sm text-gray-500">
          Loading departments...
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

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-bold text-gray-900">
          Departments
        </h1>

        <p className="mt-1 text-sm text-gray-500">
          Department workload derived from current
          issue data.
        </p>
      </section>

      {departments.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-white p-10 text-center">
          <h3 className="font-semibold">
            No department data
          </h3>

          <p className="mt-1 text-sm text-gray-500">
            No issues have been returned by the
            backend yet.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {departments.map(
            (department) => {
              const resolutionRate =
                department.totalIssues >
                  0
                  ? Math.round(
                    (department.resolvedIssues /
                      department.totalIssues) *
                    100,
                  )
                  : 0;

              return (
                <div
                  key={department.name}
                  className="rounded-xl border bg-white p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="font-semibold text-gray-900">
                        {department.name}
                      </h2>

                      <p className="mt-1 text-xs text-gray-500">
                        Department workload
                      </p>
                    </div>

                    {department.criticalIssues >
                      0 && (
                        <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-800">
                          {
                            department.criticalIssues
                          }{" "}
                          P0
                        </span>
                      )}
                  </div>

                  <div className="mt-5 grid grid-cols-2 gap-3">
                    <Metric
                      label="Issues"
                      value={
                        department.totalIssues
                      }
                    />

                    <Metric
                      label="Reports"
                      value={
                        department.totalReports
                      }
                    />

                    <Metric
                      label="Resolved"
                      value={
                        department.resolvedIssues
                      }
                    />

                    <Metric
                      label="Resolution"
                      value={`${resolutionRate}%`}
                    />
                  </div>
                </div>
              );
            },
          )}
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="rounded-lg bg-gray-50 p-3">
      <p className="text-xs text-gray-500">
        {label}
      </p>

      <p className="mt-1 text-xl font-bold text-gray-900">
        {value}
      </p>
    </div>
  );
}