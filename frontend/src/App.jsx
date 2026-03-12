import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  fetchAnomalyDetail,
  fetchDatasetAnomalies,
  fetchDatasets,
  fetchDatasetTimeseries,
} from "./lib/api";
import "./styles.css";

function formatDate(timestamp) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(timestamp));
}

function formatValue(value) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value);
}

function formatCorrelation(score) {
  return `${score >= 0 ? "+" : ""}${score.toFixed(2)}`;
}

function buildChartData(timeseries, anomalies) {
  const anomalyMap = new Map(anomalies.map((item) => [item.timestamp, item]));
  return timeseries.map((point) => ({
    ...point,
    timestampMs: new Date(point.timestamp).getTime(),
    label: formatDate(point.timestamp),
    anomaly: anomalyMap.get(point.timestamp) ?? null,
  }));
}

export default function App() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState(null);
  const [selectedAnomalyDetail, setSelectedAnomalyDetail] = useState(null);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadDatasets() {
      setDatasetsLoading(true);
      setErrorMessage("");

      try {
        const response = await fetchDatasets();
        if (cancelled) {
          return;
        }
        setDatasets(response);
        if (response.length > 0) {
          setSelectedDatasetId(response[0].id);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error.message);
        }
      } finally {
        if (!cancelled) {
          setDatasetsLoading(false);
        }
      }
    }

    loadDatasets();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedDatasetId) {
      return;
    }

    let cancelled = false;

    async function loadDatasetView() {
      setChartLoading(true);
      setErrorMessage("");

      try {
        const [nextTimeseries, nextAnomalies] = await Promise.all([
          fetchDatasetTimeseries(selectedDatasetId, 500),
          fetchDatasetAnomalies(selectedDatasetId, 100),
        ]);
        if (cancelled) {
          return;
        }
        setTimeseries(nextTimeseries);
        setAnomalies(nextAnomalies);
        setSelectedAnomalyId(nextAnomalies[0]?.id ?? null);
        if (nextAnomalies.length === 0) {
          setSelectedAnomalyDetail(null);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error.message);
          setTimeseries([]);
          setAnomalies([]);
          setSelectedAnomalyId(null);
          setSelectedAnomalyDetail(null);
        }
      } finally {
        if (!cancelled) {
          setChartLoading(false);
        }
      }
    }

    loadDatasetView();
    return () => {
      cancelled = true;
    };
  }, [selectedDatasetId]);

  useEffect(() => {
    if (!selectedAnomalyId) {
      return;
    }

    let cancelled = false;

    async function loadAnomalyDetail() {
      setDetailLoading(true);

      try {
        const detail = await fetchAnomalyDetail(selectedAnomalyId);
        if (!cancelled) {
          setSelectedAnomalyDetail(detail);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error.message);
          setSelectedAnomalyDetail(null);
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    }

    loadAnomalyDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedAnomalyId]);

  const selectedDataset = datasets.find((dataset) => dataset.id === selectedDatasetId) ?? null;
  const chartData = buildChartData(timeseries, anomalies);
  const anomalyPoints = chartData.filter((point) => point.anomaly);

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">MacroLens Live MVP</p>
          <h1>Investigate macro events through anomalies, relationships, and explanations.</h1>
        </div>
        <p className="summary">
          This view is connected to the live FastAPI backend and PostgreSQL pipeline. Pick a
          dataset, inspect flagged events on the chart, and open the evidence panel for
          correlations and generated explanations.
        </p>
      </section>

      <section className="workspace">
        <div className="chart-panel">
          <div className="panel-header">
            <div>
              <p className="panel-label">Dataset</p>
              <h2>{selectedDataset?.name ?? "Loading datasets..."}</h2>
              <p className="panel-meta">
                {selectedDataset ? `${selectedDataset.source} · ${selectedDataset.frequency}` : ""}
              </p>
            </div>
            <label className="dataset-picker">
              <span>Choose series</span>
              <select
                value={selectedDatasetId ?? ""}
                onChange={(event) => setSelectedDatasetId(Number(event.target.value))}
                disabled={datasetsLoading}
              >
                {datasets.map((dataset) => (
                  <option value={dataset.id} key={dataset.id}>
                    {dataset.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="chart-card">
            {errorMessage ? (
              <div className="state-card error-card">{errorMessage}</div>
            ) : chartLoading ? (
              <div className="state-card">Loading timeseries and anomalies...</div>
            ) : chartData.length === 0 ? (
              <div className="state-card">No chart data is available for this dataset yet.</div>
            ) : (
              <>
                <div className="chart-summary">
                  <div>
                    <span>Points</span>
                    <strong>{chartData.length}</strong>
                  </div>
                  <div>
                    <span>Anomalies</span>
                    <strong>{anomalies.length}</strong>
                  </div>
                  <div>
                    <span>Latest value</span>
                    <strong>{formatValue(chartData[chartData.length - 1].value)}</strong>
                  </div>
                </div>

                <div className="chart-shell">
                  <ResponsiveContainer width="100%" height={380}>
                    <LineChart data={chartData} margin={{ top: 20, right: 24, left: 8, bottom: 8 }}>
                      <CartesianGrid stroke="rgba(15, 23, 42, 0.08)" vertical={false} />
                      <XAxis
                        dataKey="timestampMs"
                        type="number"
                        scale="time"
                        tickFormatter={(value) =>
                          new Intl.DateTimeFormat("en-US", {
                            month: "short",
                            day: "numeric",
                          }).format(new Date(value))
                        }
                        domain={["dataMin", "dataMax"]}
                        stroke="#64748b"
                      />
                      <YAxis
                        stroke="#64748b"
                        tickFormatter={(value) => formatValue(value)}
                        width={80}
                      />
                      <Tooltip
                        formatter={(value) => formatValue(value)}
                        labelFormatter={(value) => formatDate(value)}
                        contentStyle={{
                          borderRadius: "16px",
                          border: "1px solid rgba(15, 23, 42, 0.08)",
                          boxShadow: "0 16px 40px rgba(15, 23, 42, 0.12)",
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#0f766e"
                        strokeWidth={3}
                        dot={false}
                        activeDot={{ r: 5 }}
                      />
                      {anomalyPoints.map((point) => (
                        <ReferenceDot
                          key={point.anomaly.id}
                          x={point.timestampMs}
                          y={point.value}
                          r={selectedAnomalyId === point.anomaly.id ? 8 : 6}
                          fill={selectedAnomalyId === point.anomaly.id ? "#b91c1c" : "#f97316"}
                          stroke="#fff7ed"
                          strokeWidth={2}
                          onClick={() => setSelectedAnomalyId(point.anomaly.id)}
                          ifOverflow="extendDomain"
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
          </div>
        </div>

        <aside className="detail-panel">
          <div className="detail-card">
            <div className="panel-header compact">
              <div>
                <p className="panel-label">Event panel</p>
                <h2>
                  {selectedAnomalyDetail
                    ? formatDate(selectedAnomalyDetail.timestamp)
                    : "Select an anomaly"}
                </h2>
              </div>
              {selectedAnomalyDetail ? (
                <span className={`direction-badge ${selectedAnomalyDetail.direction ?? "flat"}`}>
                  {selectedAnomalyDetail.direction ?? "n/a"}
                </span>
              ) : null}
            </div>

            {detailLoading ? (
              <div className="state-card">Loading event details...</div>
            ) : selectedAnomalyDetail ? (
              <>
                <div className="metric-grid">
                  <article>
                    <span>Severity</span>
                    <strong>{selectedAnomalyDetail.severity_score.toFixed(2)}</strong>
                  </article>
                  <article>
                    <span>Method</span>
                    <strong>{selectedAnomalyDetail.detection_method}</strong>
                  </article>
                  <article>
                    <span>Correlations</span>
                    <strong>{selectedAnomalyDetail.correlations.length}</strong>
                  </article>
                </div>

                <section className="detail-section">
                  <header>
                    <p className="panel-label">Generated explanation</p>
                  </header>
                  {selectedAnomalyDetail.explanations.length > 0 ? (
                    selectedAnomalyDetail.explanations.map((item) => (
                      <article className="explanation-card" key={`${item.provider}-${item.created_at}`}>
                        <p>{item.generated_text}</p>
                        <footer>
                          {item.provider} · {item.model}
                        </footer>
                      </article>
                    ))
                  ) : (
                    <div className="empty-card">No explanation has been generated yet.</div>
                  )}
                </section>

                <section className="detail-section">
                  <header>
                    <p className="panel-label">Correlated datasets</p>
                  </header>
                  {selectedAnomalyDetail.correlations.length > 0 ? (
                    <div className="correlation-list">
                      {selectedAnomalyDetail.correlations.map((item) => (
                        <article className="correlation-card" key={`${item.related_dataset_id}-${item.lag_days}`}>
                          <div>
                            <h3>{item.related_dataset_name}</h3>
                            <p>{item.method}</p>
                          </div>
                          <div className="correlation-stats">
                            <strong>{formatCorrelation(item.correlation_score)}</strong>
                            <span>lag {item.lag_days}d</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-card">No strong correlations were stored for this event.</div>
                  )}
                </section>
              </>
            ) : (
              <div className="state-card">Choose an anomaly marker to inspect the event.</div>
            )}
          </div>

          <div className="detail-card">
            <div className="panel-header compact">
              <div>
                <p className="panel-label">Detected events</p>
                <h2>Recent anomalies</h2>
              </div>
            </div>
            <div className="anomaly-list">
              {anomalies.length > 0 ? (
                anomalies.map((anomaly) => (
                  <button
                    className={`anomaly-list-item ${selectedAnomalyId === anomaly.id ? "active" : ""}`}
                    key={anomaly.id}
                    onClick={() => setSelectedAnomalyId(anomaly.id)}
                    type="button"
                  >
                    <span>{formatDate(anomaly.timestamp)}</span>
                    <strong>{anomaly.severity_score.toFixed(2)}</strong>
                  </button>
                ))
              ) : (
                <div className="empty-card">No anomalies are available for this dataset.</div>
              )}
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}
