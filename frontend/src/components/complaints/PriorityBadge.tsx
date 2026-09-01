import type { PriorityLabel } from "../../types/issue";

interface PriorityBadgeProps {
  priority: PriorityLabel;
}

export default function PriorityBadge({
  priority,
}: PriorityBadgeProps) {
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
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${styles[priority]}`}
    >
      {priority} — {labels[priority]}
    </span>
  );
}