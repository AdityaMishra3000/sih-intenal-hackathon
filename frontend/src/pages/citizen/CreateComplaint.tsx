import { useState } from "react";
import type { FormEvent } from "react";

import { useNavigate } from "react-router-dom";

import {
  createComplaint,
} from "../../api/complaints";

export default function CreateComplaint() {
  const navigate =
    useNavigate();

  const [text, setText] =
    useState("");

  const [lat, setLat] =
    useState("");

  const [lng, setLng] =
    useState("");

  const [submitting, setSubmitting] =
    useState(false);

  const [error, setError] =
    useState("");

  const [success, setSuccess] =
    useState("");

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!text.trim()) {
      setError(
        "Please describe your complaint.",
      );
      return;
    }

    const latitude = Number(lat);
    const longitude = Number(lng);

    if (
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude)
    ) {
      setError(
        "Please provide a valid latitude and longitude, or use your current location.",
      );
      return;
    }

    if (
      latitude < -90 ||
      latitude > 90 ||
      longitude < -180 ||
      longitude > 180
    ) {
      setError(
        "The provided coordinates are outside the valid geographic range.",
      );
      return;
    }

    setSubmitting(true);

    try {
      const response =
        await createComplaint({
          text: text.trim(),
          lat: latitude,
          lng: longitude,
          channel: "web",
        });

      /*
       * Temporary frontend-only storage.
       *
       * This will eventually be replaced by
       * GET /complaints/me once authentication
       * is implemented by the backend.
       */
      const existing =
        localStorage.getItem(
          "my_complaint_ids",
        );

      let ids: number[] = [];

      if (existing) {
        try {
          const parsed =
            JSON.parse(existing);

          if (Array.isArray(parsed)) {
            ids = parsed.filter(
              (value): value is number =>
                typeof value === "number",
            );
          }
        } catch {
          ids = [];
        }
      }

      if (
        !ids.includes(
          response.ticket_id,
        )
      ) {
        ids.push(
          response.ticket_id,
        );
      }

      localStorage.setItem(
        "my_complaint_ids",
        JSON.stringify(ids),
      );

      setSuccess(
        `Complaint submitted successfully. Ticket #${response.ticket_id}`,
      );

      setTimeout(() => {
        navigate(
          `/citizen/complaints/${response.ticket_id}`,
        );
      }, 700);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to submit complaint",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function useCurrentLocation() {
    setError("");

    if (!navigator.geolocation) {
      setError(
        "Geolocation is not supported by this browser.",
      );
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLat(
          position.coords.latitude.toString(),
        );

        setLng(
          position.coords.longitude.toString(),
        );
      },
      () => {
        setError(
          "Unable to access your current location. Please enter the coordinates manually.",
        );
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      },
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <section>
        <p className="text-sm font-medium text-blue-600">
          Citizen Portal
        </p>

        <h1 className="mt-1 text-2xl font-bold text-gray-900">
          Make a Complaint
        </h1>

        <p className="mt-2 text-sm leading-6 text-gray-500">
          Describe the civic problem clearly. The AI
          pipeline will classify it, determine priority,
          identify the responsible department and check
          for duplicate reports.
        </p>
      </section>

      <form
        onSubmit={handleSubmit}
        className="space-y-6 rounded-xl border bg-white p-5 sm:p-6"
      >
        {/* Complaint text */}
        <div>
          <label
            htmlFor="complaint"
            className="mb-2 block text-sm font-medium text-gray-700"
          >
            Complaint
          </label>

          <textarea
            id="complaint"
            value={text}
            onChange={(event) =>
              setText(event.target.value)
            }
            placeholder="Example: There has been a large water leak near the main road outside the railway station for the past two days..."
            rows={7}
            maxLength={5000}
            className="w-full resize-y rounded-xl border border-gray-300 px-4 py-3 text-sm leading-6 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          />

          <div className="mt-1 flex justify-between text-xs text-gray-400">
            <span>
              Describe what happened and where.
            </span>

            <span>
              {text.length}/5000
            </span>
          </div>
        </div>

        {/* Location */}
        <div>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <label className="text-sm font-medium text-gray-700">
                Location
              </label>

              <p className="mt-1 text-xs leading-5 text-gray-500">
                Location is used for department routing,
                duplicate detection and geographic hotspot
                analysis.
              </p>
            </div>

            <button
              type="button"
              onClick={
                useCurrentLocation
              }
              className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              Use my location
            </button>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="latitude"
                className="mb-1.5 block text-xs font-medium text-gray-600"
              >
                Latitude
              </label>

              <input
                id="latitude"
                type="number"
                step="any"
                value={lat}
                onChange={(event) =>
                  setLat(
                    event.target.value,
                  )
                }
                placeholder="19.0760"
                className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
            </div>

            <div>
              <label
                htmlFor="longitude"
                className="mb-1.5 block text-xs font-medium text-gray-600"
              >
                Longitude
              </label>

              <input
                id="longitude"
                type="number"
                step="any"
                value={lng}
                onChange={(event) =>
                  setLng(
                    event.target.value,
                  )
                }
                placeholder="72.8777"
                className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
            </div>
          </div>
        </div>

        {/* Messages */}
        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-5 text-red-700"
          >
            {error}
          </div>
        )}

        {success && (
          <div
            role="status"
            className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm leading-5 text-green-700"
          >
            {success}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={
            submitting ||
            !text.trim()
          }
          className="min-h-12 w-full rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting
            ? "Submitting complaint..."
            : "Submit Complaint"}
        </button>
      </form>
    </div>
  );
}