import { Navigate, Outlet } from "react-router-dom";

// Assuming you have some way to get the current user's profile/role
// For example, from a context or a custom hook: const { user } = useAuth();
const AdminRoute = ({ user }) => {
  if (!user) {
    // Not logged in? Send them to login.
    return <Navigate to="/sign-in" replace />;
  }

  if (user.role !== "admin") {
    // Logged in but not an admin? Send them to the dashboard.
    return <Navigate to="/dashboard" replace />;
  }

  // If they are an admin, render the child routes!
  return <Outlet />;
};

export default AdminRoute;
