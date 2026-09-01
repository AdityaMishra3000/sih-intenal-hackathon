import type { Complaint } from "../../types/complaint";

interface ComplaintStatusProps {
  state: Complaint["state"];
}

export default function ComplaintStatus({
  state,
}: ComplaintStatusProps) {
  const normalizedState =
    state?.toUpperCase() || "UNKNOWN";

  const styles: Record<string, string> = {
    NEW: "bg-blue-100 text-blue-800",
    PROCESSING:
      "bg-yellow-100 text-yellow-800",
    PROCESSED:
      "bg-green-100 text-green-800",
    LINKED:
      "bg-purple-100 text-purple-800",
    REVIEW:
      "bg-orange-100 text-orange-800",
    RESOLVED:
      "bg-green-100 text-green-800",
    ERROR:
      "bg-red-100 text-red-800",
  };

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${styles[normalizedState] ??
        "bg-gray-100 text-gray-700"
        }`}
    >
      {formatState(normalizedState)}
    </span>
  );
}

function formatState(
  state: string,
): string {
  return state
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    );
}