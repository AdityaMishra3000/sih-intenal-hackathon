import { apiRequest } from "./client";
import type {
  Issue,
  IssueStatus,
} from "../types/issue";
import {
  mapComplaint,
  type BackendComplaint,
} from "./complaints";

interface BackendIssue {
  id: number;
  category_l1: string;
  category_l2: string;
  lat: number;
  lng: number;
  summary: string;
  report_count: number;
  severity: number;
  priority_score: number;
  priority_label: Issue["priorityLabel"];
  priority_why: string;
  factors: Issue["factors"];
  department: string;
  ward: string;
  status: IssueStatus;
  created_at: string;
  sla_due: string;
  needs_review: number | boolean;
  complaints?: BackendComplaint[];
}

function mapIssue(data: BackendIssue): Issue {
  return {
    id: data.id,
    categoryL1: data.category_l1,
    categoryL2: data.category_l2,
    lat: data.lat,
    lng: data.lng,
    summary: data.summary,
    reportCount: data.report_count,
    severity: data.severity,
    priorityScore: data.priority_score,
    priorityLabel: data.priority_label,
    priorityWhy: data.priority_why,
    factors: data.factors ?? {},
    department: data.department,
    ward: data.ward,
    status: data.status,
    createdAt: data.created_at,
    slaDue: data.sla_due,
    needsReview: Boolean(data.needs_review),
    complaints: data.complaints?.map(mapComplaint),
  };
}

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

  const response = await apiRequest<BackendIssue[]>(
    `/issues${query ? `?${query}` : ""}`,
  );
  return response.map(mapIssue);
}

export async function getIssue(
  issueId: number,
): Promise<Issue> {
  const response = await apiRequest<BackendIssue>(
    `/issues/${issueId}`,
  );
  return mapIssue(response);
}

export async function updateIssueStatus(
  issueId: number,
  status: IssueStatus,
): Promise<Issue> {
  const response = await apiRequest<BackendIssue>(
    `/issues/${issueId}/status`,
    {
      method: "POST",
      body: { status },
    },
  );
  return mapIssue(response);
}

export async function reassignIssue(
  issueId: number,
  department: string,
): Promise<Issue> {
  const response = await apiRequest<BackendIssue>(
    `/issues/${issueId}/reassign`,
    {
      method: "POST",
      body: {
        department,
      },
    },
  );
  return mapIssue(response);
}
