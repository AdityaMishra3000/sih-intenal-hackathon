import { apiClient } from "./client";

import type {
  Complaint,
  CreateComplaintRequest,
  CreateComplaintResponse,
} from "../types/complaint";

export interface BackendComplaint {
  id: number;

  text: string;

  lang: string;

  text_en?: string | null;

  lat: number;

  lng: number;

  created_at: string;

  channel: string;

  citizen_phone?: string | null;

  issue_id?: number | null;

  dedup_score?: number | null;

  dedup_reasons?: string[] | null;

  state: string;
}

export function mapComplaint(
  data: BackendComplaint,
): Complaint {
  return {
    id: data.id,

    text: data.text,

    lang: data.lang,

    textEn:
      data.text_en ??
      undefined,

    lat: data.lat,

    lng: data.lng,

    createdAt:
      data.created_at,

    channel:
      data.channel,

    citizenPhone:
      data.citizen_phone ??
      undefined,

    issueId:
      data.issue_id ??
      undefined,

    dedupScore:
      data.dedup_score ??
      undefined,

    dedupReasons:
      data.dedup_reasons ??
      [],

    state:
      data.state,
  };
}

export async function createComplaint(
  request: CreateComplaintRequest,
): Promise<CreateComplaintResponse> {
  const response =
    await apiClient.post<CreateComplaintResponse>(
      "/complaints",
      {
        text: request.text,
        lat: request.lat,
        lng: request.lng,
        channel: request.channel,
        citizen_phone: request.citizenPhone,
      },
    );

  return response.data;
}

export async function getComplaint(
  id: number,
): Promise<Complaint> {
  const response =
    await apiClient.get<BackendComplaint>(
      `/complaints/${id}`,
    );

  return mapComplaint(
    response.data,
  );
}

export async function unmergeComplaint(
  complaintId: number,
): Promise<void> {
  await apiClient.post(
    `/complaints/${complaintId}/unmerge`,
  );
}
