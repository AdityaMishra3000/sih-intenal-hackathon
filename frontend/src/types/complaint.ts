export interface Complaint {
  id: number;

  text: string;

  lang: string;

  textEn?: string;

  lat: number;

  lng: number;

  createdAt: string;

  channel: string;

  citizenPhone?: string;

  issueId?: number;

  dedupScore?: number;

  dedupReasons: string[];

  state: string;
}

export interface CreateComplaintRequest {
  text: string;

  lat: number;

  lng: number;

  channel?: string;

  citizenPhone?: string;
}

export interface CreateComplaintResponse {
  ticket_id: number;

  decision?: string;

  priority?: string;
}