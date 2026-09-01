import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export function AdminLayout() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="border-b bg-gray-950 text-white">
        <div className="mx-auto flex min-h-16 max-w-[1600px] items-center justify-between px-4">
          <Link
            to="/admin"
            className="font-bold"
          >
            CivicResolve Admin
          </Link>

          <div className="flex items-center gap-4">
            <span className="hidden text-sm text-gray-300 sm:block">
              {user?.name}
            </span>

            <button
              type="button"
              onClick={signOut}
              className="text-sm text-red-300"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1600px] md:flex">
        <aside className="hidden min-h-[calc(100vh-4rem)] w-60 border-r bg-white p-4 md:block">
          <nav className="space-y-1">
            <Link
              to="/admin"
              className="block rounded-lg p-3 hover:bg-gray-100"
            >
              Overview
            </Link>

            <Link
              to="/admin/complaints"
              className="block rounded-lg p-3 hover:bg-gray-100"
            >
              Complaints
            </Link>

            <Link
              to="/admin/departments"
              className="block rounded-lg p-3 hover:bg-gray-100"
            >
              Departments
            </Link>
          </nav>
        </aside>

        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}