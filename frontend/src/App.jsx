import { ApiStatus } from "./components/ApiStatus";
import { AppHeader } from "./components/AppHeader";
import { IncidentList } from "./features/incidents/IncidentList";
import { MapPanel } from "./features/map/MapPanel";
import { useApiHealth } from "./hooks/useApiHealth";


export default function App() {
  const apiHealth = useApiHealth();

  return (
    <main className="shell">
      <AppHeader status={<ApiStatus health={apiHealth} />} />
      <section className="workspace" aria-label="Dispatcher workspace">
        <IncidentList incidents={[]} />
        <MapPanel />
      </section>
    </main>
  );
}

