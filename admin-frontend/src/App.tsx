import { Routes, Route, Navigate } from 'react-router-dom';
import { App as AntApp } from 'antd';
import ErrorBoundary from './components/ErrorBoundary';
import AuthGuard from './components/AuthGuard';
import MainLayout from './layouts/MainLayout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import UserList from './pages/users/UserList';
import UserDetail from './pages/users/UserDetail';
import MembershipList from './pages/membership/MembershipList';
import CheckinList from './pages/checkins/CheckinList';
import SquadList from './pages/squads/SquadList';
import WishList from './pages/wishes/WishList';
import CapsuleList from './pages/capsules/CapsuleList';
import PetList from './pages/pets/PetList';
import MakeupList from './pages/makeup/MakeupList';
import InsightList from './pages/insights/InsightList';
import AdminList from './pages/admins/AdminList';
import LogList from './pages/logs/LogList';
import SystemConfig from './pages/config/SystemConfig';

export default function App() {
  return (
    <ErrorBoundary>
    <AntApp>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <AuthGuard>
              <MainLayout />
            </AuthGuard>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="users" element={<UserList />} />
          <Route path="users/:userId" element={<UserDetail />} />
          <Route path="membership" element={<MembershipList />} />
          <Route path="checkins" element={<CheckinList />} />
          <Route path="squads" element={<SquadList />} />
          <Route path="wishes" element={<WishList />} />
          <Route path="capsules" element={<CapsuleList />} />
          <Route path="pets" element={<PetList />} />
          <Route path="makeup-cards" element={<MakeupList />} />
          <Route path="insights" element={<InsightList />} />
          <Route path="admins" element={<AdminList />} />
          <Route path="logs" element={<LogList />} />
          <Route path="config" element={<SystemConfig />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AntApp>
    </ErrorBoundary>
  );
}
