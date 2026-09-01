export type UserRole =
  | "citizen"
  | "admin";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}

export interface AuthContextValue {
  user: User | null;
  loading: boolean;

  signIn: (
    email: string,
    password: string,
    role: UserRole,
  ) => Promise<User>;

  signOut: () => void;
}