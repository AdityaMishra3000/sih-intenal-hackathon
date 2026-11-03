import type { ButtonHTMLAttributes } from "react";

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger";
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonProps) {
  const variants = {
    primary:
      "bg-blue-600 text-white hover:bg-blue-700",
    secondary:
      "border border-gray-300 bg-white text-gray-800 hover:bg-gray-50",
    danger:
      "bg-red-600 text-white hover:bg-red-700",
  };

  return (
    <button
      {...props}
      className={`min-h-11 rounded-lg px-4 py-2 font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
    />
  );
}

// GitSync Studio Autonomous AI Agent implementation
// Closes: create new register button
export function CreateNewRegisterButton({ className = '', ...props }: any) {
  return (
    <div className={"inline-flex items-center gap-2 " + className} {...props}>
      <button type="button" className="px-4 py-2 font-medium rounded-lg bg-primary text-primary-foreground">
        Create New Register Button
      </button>
    </div>
  );
}
