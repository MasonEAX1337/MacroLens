const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const STATIC_DATA_BASE_URL = import.meta.env.VITE_STATIC_DATA_BASE_URL ?? "/static-data";
const FORCE_STATIC_DATA = import.meta.env.VITE_USE_STATIC_DATA === "true";

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

async function requestStatic(path) {
  const response = await fetch(`${STATIC_DATA_BASE_URL}${path}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Static request failed with status ${response.status}`);
  }
  return response.json();
}

async function requestWithStaticFallback(apiPath, staticPath, options = {}) {
  if (FORCE_STATIC_DATA) {
    return requestStatic(staticPath);
  }

  try {
    return await request(apiPath, options);
  } catch (apiError) {
    try {
      return await requestStatic(staticPath);
    } catch {
      throw apiError;
    }
  }
}

export function fetchDatasets() {
  return requestWithStaticFallback("/api/v1/datasets", "/datasets.json");
}

export function fetchDatasetTimeseries(datasetId, limit = 500) {
  return requestWithStaticFallback(
    `/api/v1/datasets/${datasetId}/timeseries?limit=${limit}`,
    `/datasets/${datasetId}/timeseries.json`,
  );
}

export function fetchDatasetAnomalies(datasetId, limit = 100) {
  return requestWithStaticFallback(
    `/api/v1/datasets/${datasetId}/anomalies?limit=${limit}`,
    `/datasets/${datasetId}/anomalies.json`,
  );
}

export function fetchDatasetLeadingIndicators(datasetId, limit = 5) {
  return requestWithStaticFallback(
    `/api/v1/datasets/${datasetId}/leading-indicators?limit=${limit}`,
    `/datasets/${datasetId}/leading-indicators.json`,
  );
}

export function fetchAnomalyDetail(anomalyId) {
  return requestWithStaticFallback(`/api/v1/anomalies/${anomalyId}`, `/anomalies/${anomalyId}.json`);
}

export function regenerateAnomalyExplanation(anomalyId) {
  return request(`/api/v1/anomalies/${anomalyId}/regenerate-explanation`, {
    method: "POST",
  });
}
