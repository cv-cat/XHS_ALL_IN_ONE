import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/layout/app-shell";
import { ComingSoonPage } from "../components/platforms/coming-soon";
import { ProtectedRoute, PublicOnlyRoute } from "../components/ui/protected-route";
import { LoginPage } from "../pages/login/login-page";
import { ModelConfigPage } from "../pages/models/model-config-page";
import { PlatformSelectPage } from "../pages/platform-select/platform-select-page";
import { SettingsPage } from "../pages/settings/settings-page";
import { TaskCenterPage } from "../pages/tasks/task-center-page";
import { AutoOpsPage } from "../pages/platforms/xhs/auto-ops-page";
import { XhsAccountsPage } from "../pages/platforms/xhs/accounts-page";
import { XhsAnalyticsPage } from "../pages/platforms/xhs/analytics-page";
import { XhsBenchmarksPage } from "../pages/platforms/xhs/benchmarks-page";
import { XhsDashboard } from "../pages/platforms/xhs/xhs-dashboard";
import { XhsCrawlerPage } from "../pages/platforms/xhs/crawler-page";
import { XhsDiscoveryPage } from "../pages/platforms/xhs/discovery-page";
import { XhsDraftsPage } from "../pages/platforms/xhs/rewrite-page";
import { XhsKeywordsPage } from "../pages/platforms/xhs/keywords-page";
import { XhsLibraryPage } from "../pages/platforms/xhs/library-page";
import { XhsMonitoringPage } from "../pages/platforms/xhs/monitoring-page";
import { XhsImageStudioPage } from "../pages/platforms/xhs/image-studio-page";
import { XhsPublishPage } from "../pages/platforms/xhs/publish-page";
import { XhsVideoStudioPage } from "../pages/platforms/xhs/video-studio-page";
import { XhsSectionPage } from "../pages/platforms/xhs/xhs-section-page";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/platform-select" replace />} />
        <Route
          path="/login"
          element={
            <PublicOnlyRoute>
              <LoginPage />
            </PublicOnlyRoute>
          }
        />
        <Route
          path="/platform-select"
          element={
            <ProtectedRoute>
              <PlatformSelectPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/platforms/:platformId"
          element={
            <ProtectedRoute>
              <ComingSoonPage />
            </ProtectedRoute>
          }
        />
        <Route
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route path="/platforms/xhs/dashboard" element={<XhsDashboard />} />
          <Route path="/platforms/xhs/accounts" element={<XhsAccountsPage />} />
          <Route path="/platforms/xhs/analytics" element={<XhsAnalyticsPage />} />
          <Route path="/platforms/xhs/discovery" element={<XhsDiscoveryPage />} />
          <Route path="/platforms/xhs/crawler" element={<XhsCrawlerPage />} />
          <Route path="/platforms/xhs/keywords" element={<XhsKeywordsPage />} />
          <Route path="/platforms/xhs/library" element={<XhsLibraryPage />} />
          <Route path="/platforms/xhs/drafts" element={<XhsDraftsPage />} />
          <Route path="/platforms/xhs/benchmarks" element={<XhsBenchmarksPage />} />
          <Route path="/platforms/xhs/image-studio" element={<XhsImageStudioPage />} />
          <Route path="/platforms/xhs/video-studio" element={<XhsVideoStudioPage />} />
          <Route path="/platforms/xhs/publish" element={<XhsPublishPage />} />
          <Route path="/platforms/xhs/auto-ops" element={<AutoOpsPage />} />
          <Route path="/platforms/xhs/:section" element={<XhsSectionPage />} />
          <Route path="/tasks" element={<TaskCenterPage />} />
          <Route path="/models" element={<ModelConfigPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
