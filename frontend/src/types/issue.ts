import type { Complaint } from "./complaint";

export type PriorityLabel =
  | "P0"
  | "P1"
  | "P2"
  | "P3";

export type IssueStatus =
  | "OPEN"
  | "ACK"
  | "IN_PROGRESS"
  | "RESOLVED";

export interface PriorityFactors {
  severity?: number;
  poi_proximity?: number;
  reports?: number;
  category_base?: number;
  age?: number;

  [key: string]: number | undefined;
}

export interface Issue {
  id: number;

  categoryL1: string;
  categoryL2: string;

  lat: number;
  lng: number;

  summary: string;

  reportCount: number;
  severity: number;

  priorityScore: number;
  priorityLabel: PriorityLabel;

  priorityWhy: string;
  factors: PriorityFactors;

  department: string;
  ward: string;

  status: IssueStatus;

  createdAt: string;
  slaDue: string;

  needsReview: boolean;

  complaints?: Complaint[];
}