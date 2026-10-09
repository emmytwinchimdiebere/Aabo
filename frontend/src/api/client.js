const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? window.location.origin;


export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}


async function request(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: "application/json", ...options.headers },
    ...options,
  });

  if (!response.ok) {
    throw new ApiError(`Request failed with status ${response.status}`, response.status);
  }

  return response.json();
}


export function getHealth(options = {}) {
  return request("/health", options);
}


export async function createTranscription({ audio, language, signal }) {
  const form = new FormData();
  form.append("language", language);
  form.append("audio", audio, `aabo-${language}.wav`);

  const response = await fetch(`${apiBaseUrl}/transcriptions`, {
    method: "POST",
    body: form,
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.detail ?? `Request failed with status ${response.status}`, response.status);
  }
  return response.json();
}


export function extractLocation({ transcript, language, signal }) {
  return request("/locations/extract", {
    method: "POST",
    body: JSON.stringify({ transcript, language }),
    headers: { "Content-Type": "application/json" },
    signal,
  });
}


export async function createWebIncident({
  audio,
  language,
  emergencyType,
  confirmedAddress,
  rawTranscript,
  confirmedTranscript,
  durationSeconds,
  coordinates,
  trainingConsent = false,
  signal,
}) {
  const form = new FormData();
  form.append("audio", audio, `aabo-${language}.wav`);
  form.append("language", language);
  form.append("emergency_type", emergencyType);
  form.append("confirmed_address", confirmedAddress);
  form.append("raw_transcript", rawTranscript);
  form.append("confirmed_transcript", confirmedTranscript);
  form.append("duration_seconds", String(durationSeconds));
  form.append("training_consent", String(trainingConsent));
  if (coordinates) {
    form.append("latitude", String(coordinates.latitude));
    form.append("longitude", String(coordinates.longitude));
  }

  const response = await fetch(`${apiBaseUrl}/incidents/web`, {
    method: "POST",
    body: form,
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.detail ?? `Request failed with status ${response.status}`, response.status);
  }
  return response.json();
}


export function getIncidents(options = {}) {
  return request("/incidents", options);
}


export function getRecordingUrl(incidentId) {
  return `${apiBaseUrl}/incidents/${encodeURIComponent(incidentId)}/recording`;
}
