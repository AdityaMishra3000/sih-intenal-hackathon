import axios from "axios";

export const apiClient = axios.create({
  baseURL:
    import.meta.env.VITE_API_BASE_URL ||
    "http://localhost:8000",

  headers: {
    "Content-Type": "application/json",
  },
});

export interface ApiRequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
}

export async function apiRequest<T>(
  url: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const response =
    await apiClient.request<T>({
      url,

      method:
        options.method ?? "GET",

      data:
        options.body,

      headers:
        options.headers,
    });

  return response.data;
}