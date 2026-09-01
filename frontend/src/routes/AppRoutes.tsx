import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import LoginPage from "../pages/auth/LoginPage";

import CreateComplaint from "../pages/citizen/CreateComplaint";
import MyComplaints from "../pages/citizen/MyComplaints";
import ComplaintDetails from "../pages/citizen/ComplaintDetails";

import { AdminDashboard } from "../pages/admin/AdminDashboard";
import AdminIssues from "../pages/admin/AdminIssues";
import { AdminDepartments } from "../pages/admin/AdminDepartments";
import AdminIssueDetails from "../pages/admin/AdminIssueDetails";

import { CitizenLayout } from "../components/layout/CitizenLayout";
import { AdminLayout } from "../components/layout/AdminLayout";

import { CitizenDashboard } from "../pages/citizen/CitizenDashboard";

export function AppRoutes() {
  return (
    <Routes>
      {/* Root */}
      <Route
        path="/"
        element={
          <Navigate
            to="/login"
            replace
          />
        }
      />

      {/* Authentication */}
      <Route
        path="/login"
        element={<LoginPage />}
      />

      {/* Citizen */}
      <Route
        path="/citizen"
        element={<CitizenLayout />}
      >
        <Route
          index
          element={<CitizenDashboard />}
        />

        <Route
          path="complaints"
          element={<MyComplaints />}
        />

        <Route
          path="complaints/new"
          element={<CreateComplaint />}
        />

        <Route
          path="complaints/:id"
          element={<ComplaintDetails />}
        />
      </Route>

      {/* Authority / Admin */}
      <Route
        path="/admin"
        element={<AdminLayout />}
      >
        <Route
          index
          element={<AdminDashboard />}
        />

        <Route
          path="complaints"
          element={<AdminIssues />}
        />

        <Route
          path="complaints/:id"
          element={<AdminIssueDetails />}
        />

        <Route
          path="departments"
          element={<AdminDepartments />}
        />
      </Route>

      {/* Unknown route */}
      <Route
        path="*"
        element={
          <Navigate
            to="/login"
            replace
          />
        }
      />
    </Routes>
  );
}