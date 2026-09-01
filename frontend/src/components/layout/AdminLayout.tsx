import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export function AdminLayout() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-800 bg-slate-950 text-white shadow-lg shadow-slate-950/10">
        <div className="mx-auto flex min-h-16 max-w-[1600px] items-center justify-between px-4">
          <Link
            to="/admin"
            className="group flex items-center gap-2 font-bold tracking-tight"
          >
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-blue-500 text-sm shadow-lg shadow-blue-500/30">CR</span>
            CivicResolve <span className="text-blue-300">Command Centre</span>
          </Link>

          <div className="flex items-center gap-4">
            <span className="hidden text-sm text-gray-300 sm:block">
              {user?.name}
            </span>

            <button
              type="button"
              onClick={signOut}
              className="rounded-lg px-3 py-2 text-sm text-red-300 transition-colors hover:bg-red-500/10 hover:text-red-200"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1600px] md:flex">
        <aside className="hidden min-h-[calc(100vh-4rem)] w-64 border-r border-slate-200/80 bg-white/80 p-4 backdrop-blur md:block">
          <nav className="space-y-2">
            <Link
              to="/admin"
              className="block rounded-xl px-3 py-3 text-sm font-medium text-slate-600 transition-all duration-200 hover:translate-x-0.5 hover:bg-blue-50 hover:text-blue-700"
            >
              Overview
            </Link>

            <Link
              to="/admin/complaints"
              className="block rounded-xl px-3 py-3 text-sm font-medium text-slate-600 transition-all duration-200 hover:translate-x-0.5 hover:bg-blue-50 hover:text-blue-700"
            >
              Complaints
            </Link>

            <Link
              to="/admin/departments"
              className="block rounded-xl px-3 py-3 text-sm font-medium text-slate-600 transition-all duration-200 hover:translate-x-0.5 hover:bg-blue-50 hover:text-blue-700"
            >
              Departments
            </Link>
          </nav>
        </aside>

        <main className="min-w-0 flex-1 p-4 md:p-6">
          <div className="page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
