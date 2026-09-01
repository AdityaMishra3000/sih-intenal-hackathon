import { Link } from "react-router-dom";
import { Button } from "../../components/common/Button";
import { useAuth } from "../../hooks/useAuth";

export function CitizenDashboard() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm text-gray-500">
          Welcome back
        </p>

        <h1 className="text-2xl font-bold text-gray-900">
          {user?.name}
        </h1>
      </section>

      <section className="rounded-2xl bg-blue-600 p-6 text-white">
        <h2 className="text-xl font-bold">
          Report a civic issue
        </h2>

        <p className="mt-2 max-w-xl text-sm text-blue-100">
          Submit a complaint with its location and
          supporting evidence. Our system will route
          it to the appropriate department.
        </p>

        <Link
          to="/citizen/complaints/new"
          className="mt-5 inline-block"
        >
          <Button variant="secondary">
            Make a Complaint
          </Button>
        </Link>
      </section>

      <div className="grid gap-4 sm:grid-cols-3">
        <Link
          to="/citizen/complaints"
          className="rounded-xl border bg-white p-5 hover:border-blue-300"
        >
          <h3 className="font-semibold">
            My Complaints
          </h3>

          <p className="mt-2 text-sm text-gray-500">
            Track all submitted complaints
          </p>
        </Link>

        <div className="rounded-xl border bg-white p-5">
          <h3 className="font-semibold">
            Complaint Status
          </h3>

          <p className="mt-2 text-sm text-gray-500">
            Follow department actions and resolution
          </p>
        </div>

        <div className="rounded-xl border bg-white p-5">
          <h3 className="font-semibold">
            Duplicate Protection
          </h3>

          <p className="mt-2 text-sm text-gray-500">
            Similar reports can be linked to existing
            civic incidents
          </p>
        </div>
      </div>
    </div>
  );
}