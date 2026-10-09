import { CallerVoiceReport } from "./features/caller/CallerVoiceReport";
import { DispatcherConsole } from "./features/dispatch/DispatcherConsole";

export default function App() {
  return window.location.pathname.startsWith("/dispatch")
    ? <DispatcherConsole />
    : <CallerVoiceReport />;
}
