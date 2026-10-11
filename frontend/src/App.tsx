import { BrowserRouter, HashRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardDataProvider } from './DataContext'
import { Alerts } from './pages/Alerts'
import { Charts } from './pages/Charts'
import { Demo } from './pages/Demo'
import { Dependencies } from './pages/Dependencies'
import { Evidence } from './pages/Evidence'
import { IncidentPage } from './pages/Incident'
import { Metrics } from './pages/Metrics'
import { Overview } from './pages/Overview'
import { Setup } from './pages/Setup'

export function AppRoutes() {
  return (
    <DashboardDataProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/charts" element={<Charts />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/incident" element={<IncidentPage />} />
          <Route path="/evidence" element={<Evidence />} />
          <Route path="/dependencies" element={<Dependencies />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/demo" element={<Demo />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="*" element={<Overview />} />
        </Routes>
      </Layout>
    </DashboardDataProvider>
  )
}

export default function App() {
  // HashRouter only for static previews (no server-side fallback); BrowserRouter otherwise.
  const Router = import.meta.env.VITE_HASH_ROUTER === 'true' ? HashRouter : BrowserRouter
  return <Router><AppRoutes /></Router>
}
