import { apiRequest } from "./client";
import type {
  Issue,
  IssueStatus,
} from "../types/issue";

export interface IssueFilters {
  priority?: string;
  dept?: string;
  status?: string;
}

export async function getIssues(
  filters: IssueFilters = {},
): Promise<Issue[]> {
  const params = new URLSearchParams();

  if (filters.priority) {
    params.set("priority", filters.priority);
  }

  if (filters.dept) {
    params.set("dept", filters.dept);
  }

  if (filters.status) {
    params.set("status", filters.status);
  }

  const query = params.toString();

  return apiRequest<Issue[]>(
    `/issues${query ? `?${query}` : ""}`,
  );
}

export async function getIssue(
  issueId: number,
): Promise<Issue> {
  return apiRequest<Issue>(
    `/issues/${issueId}`,
  );
}

export async function updateIssueStatus(
  issueId: number,
  status: IssueStatus,
): Promise<Issue> {
  return apiRequest<Issue>(
    `/issues/${issueId}/status`,
    {
      method: "POST",
      body: JSON.stringify({ status }),
    },
  );
}

export async function reassignIssue(
  issueId: number,
  department: string,
): Promise<Issue> {
  return apiRequest<Issue>(
    `/issues/${issueId}/reassign`,
    {
      method: "POST",
      body: JSON.stringify({
        department,
      }),
    },
  );
}