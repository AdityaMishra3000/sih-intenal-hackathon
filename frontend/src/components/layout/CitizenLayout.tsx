import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export function CitizenLayout() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-4">
          <Link
            to="/citizen"
            className="text-lg font-bold text-blue-600"
          >
            CivicResolve
          </Link>

          <nav className="hidden gap-6 md:flex">
            <Link to="/citizen">Dashboard</Link>
            <Link to="/citizen/complaints">
              My Complaints
            </Link>
            <Link to="/citizen/complaints/new">
              Make Complaint
            </Link>
          </nav>

          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-gray-600 sm:block">
              {user?.name}
            </span>

            <button
              type="button"
              onClick={signOut}
              className="text-sm font-medium text-red-600"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>

      <nav className="fixed bottom-0 left-0 right-0 border-t bg-white md:hidden">
        <div className="grid grid-cols-3 text-center text-xs">
          <Link
            to="/citizen"
            className="p-4"
          >
            Home
          </Link>

          <Link
            to="/citizen/complaints"
            className="p-4"
          >
            Complaints
          </Link>

          <Link
            to="/citizen/complaints/new"
            className="p-4"
          >
            Report
          </Link>
        </div>
      </nav>
    </div>
  );
}