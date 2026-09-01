import {
  useState,
  type ReactNode,
} from "react";

import { AuthContext } from "./auth-context";

import type {
  User,
  UserRole,
} from "./auth-types";

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] =
    useState<User | null>(() => {
      const stored =
        localStorage.getItem("demo_user");

      if (!stored) {
        return null;
      }

      try {
        return JSON.parse(stored) as User;
      } catch {
        localStorage.removeItem("demo_user");
        return null;
      }
    });

  // Temporary frontend-only authentication.
  // Replace with FastAPI authentication later.
  const loading = false;

  async function signIn(
    email: string,
    _password: string,
    role: UserRole,
  ): Promise<User> {
    const demoUser: User = {
      id: `demo-${role}`,
      name:
        role === "admin"
          ? "Authority Officer"
          : "Citizen",
      email,
      role,
    };

    localStorage.setItem(
      "demo_user",
      JSON.stringify(demoUser),
    );

    setUser(demoUser);

    return demoUser;
  }

  function signOut() {
    localStorage.removeItem("demo_user");
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        signIn,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}