const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}

export function fetchDatasets() {
  return request("/api/v1/datasets");
}

export function fetchDatasetTimeseries(datasetId, limit = 500) {
  return request(`/api/v1/datasets/${datasetId}/timeseries?limit=${limit}`);
}

export function fetchDatasetAnomalies(datasetId, limit = 100) {
  return request(`/api/v1/datasets/${datasetId}/anomalies?limit=${limit}`);
}

export function fetchAnomalyDetail(anomalyId) {
  return request(`/api/v1/anomalies/${anomalyId}`);
}

export function regenerateAnomalyExplanation(anomalyId) {
  return request(`/api/v1/anomalies/${anomalyId}/regenerate-explanation`, {
    method: "POST",
  });
}
