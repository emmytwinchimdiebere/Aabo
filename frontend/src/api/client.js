const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";


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
