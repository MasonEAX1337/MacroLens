import { lazy, startTransition, Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  Brush,
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
  regenerateAnomalyExplanation,
} from "./lib/api";
import "./styles.css";

const MacroConstellation = lazy(() => import("./components/MacroConstellation"));

const DATE_WINDOW_OPTIONS = [
  { value: "6m", label: "6M" },
  { value: "1y", label: "1Y" },
  { value: "5y", label: "5Y" },
  { value: "all", label: "All" },
];

const MIN_SEVERITY_OPTIONS = [
  { value: "0", label: "Any severity" },
  { value: "2.5", label: "2.5+" },
  { value: "3", label: "3.0+" },
  { value: "3.5", label: "3.5+" },
];

const DIRECTION_OPTIONS = [
  { value: "all", label: "All moves" },
  { value: "up", label: "Up only" },
  { value: "down", label: "Down only" },
];

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

function getDateWindowCutoff(chartData, selectedWindow) {
  if (selectedWindow === "all" || chartData.length === 0) {
    return null;
  }

  const latestTimestamp = chartData[chartData.length - 1].timestampMs;
  const cutoff = new Date(latestTimestamp);

  if (selectedWindow === "6m") {
    cutoff.setMonth(cutoff.getMonth() - 6);
  } else if (selectedWindow === "1y") {
    cutoff.setFullYear(cutoff.getFullYear() - 1);
  } else if (selectedWindow === "5y") {
    cutoff.setFullYear(cutoff.getFullYear() - 5);
  }

  return cutoff.getTime();
}

function classifyLagDays(lagDays) {
  if (lagDays < 0) {
    return "leading";
  }
  if (lagDays > 0) {
    return "lagging";
  }
  return "concurrent";
}

function describeLagDays(lagDays) {
  const absoluteLag = Math.abs(lagDays);
  if (lagDays < 0) {
    return `${absoluteLag} day(s) before`;
  }
  if (lagDays > 0) {
    return `${absoluteLag} day(s) after`;
  }
  return "same window";
}

function getArticleDayOffset(publishedAt, anomalyTimestamp) {
  if (!publishedAt) {
    return null;
  }

  const articleDate = new Date(publishedAt);
  const anomalyDate = new Date(anomalyTimestamp);
  articleDate.setHours(0, 0, 0, 0);
  anomalyDate.setHours(0, 0, 0, 0);
  return Math.round((articleDate.getTime() - anomalyDate.getTime()) / 86400000);
}

function classifyArticleTiming(publishedAt, anomalyTimestamp) {
  const dayOffset = getArticleDayOffset(publishedAt, anomalyTimestamp);
  if (dayOffset === null) {
    return "unknown";
  }
  if (dayOffset < 0) {
    return "leading";
  }
  if (dayOffset > 0) {
    return "lagging";
  }
  return "concurrent";
}

function describeArticleTiming(publishedAt, anomalyTimestamp) {
  const dayOffset = getArticleDayOffset(publishedAt, anomalyTimestamp);
  if (dayOffset === null) {
    return "unknown timing";
  }
  if (dayOffset < 0) {
    return `${Math.abs(dayOffset)} day(s) before`;
  }
  if (dayOffset > 0) {
    return `${dayOffset} day(s) after`;
  }
  return "same day";
}

function buildEvidenceSummary(detail) {
  if (!detail) {
    return null;
  }

  const timingCounts = { leading: 0, concurrent: 0, lagging: 0 };
  for (const item of detail.correlations) {
    timingCounts[classifyLagDays(item.lag_days)] += 1;
  }

  return {
    correlationCount: detail.correlations.length,
    newsCount: detail.news_context.length,
    explanationProviders: detail.explanations.map((item) => item.provider),
    strongestCorrelation: detail.correlations[0] ?? null,
    timingCounts,
  };
}

export default function App() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState(null);
  const [selectedAnomalyDetail, setSelectedAnomalyDetail] = useState(null);
  const [selectedDateWindow, setSelectedDateWindow] = useState("1y");
  const [minSeverity, setMinSeverity] = useState("0");
  const [directionFilter, setDirectionFilter] = useState("all");
  const [brushRange, setBrushRange] = useState({ startIndex: 0, endIndex: 0 });
  const [constellationDatasets, setConstellationDatasets] = useState([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [constellationLoading, setConstellationLoading] = useState(false);
  const [chartLoading, setChartLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [regeneratingExplanation, setRegeneratingExplanation] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const pendingSelectionRef = useRef(null);

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
    if (datasets.length === 0) {
      setConstellationDatasets([]);
      return;
    }

    let cancelled = false;

    async function loadConstellationView() {
      setConstellationLoading(true);

      try {
        const response = await Promise.all(
          datasets.map(async (dataset) => {
            const [datasetTimeseries, datasetAnomalies] = await Promise.all([
              fetchDatasetTimeseries(dataset.id, 480),
              fetchDatasetAnomalies(dataset.id, 120),
            ]);
            return {
              dataset,
              timeseries: datasetTimeseries,
              anomalies: datasetAnomalies,
            };
          }),
        );

        if (!cancelled) {
          setConstellationDatasets(response);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error.message);
        }
      } finally {
        if (!cancelled) {
          setConstellationLoading(false);
        }
      }
    }

    loadConstellationView();
    return () => {
      cancelled = true;
    };
  }, [datasets]);

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
          fetchDatasetTimeseries(selectedDatasetId, 2000),
          fetchDatasetAnomalies(selectedDatasetId, 250),
        ]);
        if (cancelled) {
          return;
        }
        setTimeseries(nextTimeseries);
        setAnomalies(nextAnomalies);
        const requestedSelection =
          pendingSelectionRef.current?.datasetId === selectedDatasetId
            ? pendingSelectionRef.current.anomalyId
            : null;
        const requestedAnomalyExists = nextAnomalies.some((item) => item.id === requestedSelection);
        setSelectedAnomalyId(
          requestedAnomalyExists ? requestedSelection : (nextAnomalies[0]?.id ?? null),
        );
        pendingSelectionRef.current = null;
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
  const chartData = useMemo(() => buildChartData(timeseries, anomalies), [timeseries, anomalies]);
  const dateCutoff = useMemo(
    () => getDateWindowCutoff(chartData, selectedDateWindow),
    [chartData, selectedDateWindow],
  );

  const filteredChartData = useMemo(() => {
    const severityThreshold = Number(minSeverity);
    return chartData
      .filter((point) => (dateCutoff ? point.timestampMs >= dateCutoff : true))
      .map((point) => {
        const anomaly = point.anomaly;
        const matchesDirection =
          !anomaly || directionFilter === "all" || anomaly.direction === directionFilter;
        const matchesSeverity =
          !anomaly || anomaly.severity_score >= severityThreshold;

        return {
          ...point,
          anomaly: matchesDirection && matchesSeverity ? anomaly : null,
        };
      });
  }, [chartData, dateCutoff, directionFilter, minSeverity]);

  const filteredAnomalies = useMemo(
    () =>
      filteredChartData
        .flatMap((point) => (point.anomaly ? [point.anomaly] : []))
        .sort((left, right) => new Date(right.timestamp) - new Date(left.timestamp)),
    [filteredChartData],
  );

  const anomalyPoints = useMemo(
    () => filteredChartData.filter((point) => point.anomaly),
    [filteredChartData],
  );

  const latestVisibleValue =
    filteredChartData.length > 0 ? filteredChartData[filteredChartData.length - 1].value : null;

  const evidenceSummary = useMemo(
    () => buildEvidenceSummary(selectedAnomalyDetail),
    [selectedAnomalyDetail],
  );

  useEffect(() => {
    if (filteredChartData.length === 0) {
      setBrushRange({ startIndex: 0, endIndex: 0 });
      return;
    }

    const defaultStartIndex = Math.max(filteredChartData.length - 180, 0);
    setBrushRange({
      startIndex: defaultStartIndex,
      endIndex: filteredChartData.length - 1,
    });
  }, [filteredChartData, selectedDatasetId]);

  useEffect(() => {
    if (filteredAnomalies.length === 0) {
      setSelectedAnomalyId(null);
      setSelectedAnomalyDetail(null);
      return;
    }

    if (!filteredAnomalies.some((item) => item.id === selectedAnomalyId)) {
      setSelectedAnomalyId(filteredAnomalies[0].id);
    }
  }, [filteredAnomalies, selectedAnomalyId]);

  function handleConstellationSelect(datasetId, anomalyId) {
    startTransition(() => {
      setErrorMessage("");
      if (datasetId === selectedDatasetId) {
        setSelectedAnomalyId(anomalyId);
        return;
      }

      pendingSelectionRef.current = { datasetId, anomalyId };
      setSelectedDatasetId(datasetId);
    });
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">MacroLens Live MVP</p>
          <h1>Investigate macro events through anomalies, relationships, and explanations.</h1>
        </div>
        <p className="summary">
          This view is connected to the live FastAPI backend and PostgreSQL pipeline. Pick a
          dataset, narrow the evidence window, and inspect exactly what the system stored before it
          generated an explanation.
        </p>
      </section>

      <section className="constellation-wrapper">
        {errorMessage && !constellationDatasets.length ? (
          <div className="state-card error-card">{errorMessage}</div>
        ) : (
          <Suspense
            fallback={
              <div className="state-card constellation-loading">
                Building the macro constellation from the live dataset inventory...
              </div>
            }
          >
            {datasetsLoading || constellationLoading ? (
              <div className="state-card constellation-loading">
                Building the macro constellation from the live dataset inventory...
              </div>
            ) : (
              <MacroConstellation
                datasets={constellationDatasets}
                selectedDateWindow={selectedDateWindow}
                minSeverity={minSeverity}
                directionFilter={directionFilter}
                selectedAnomalyId={selectedAnomalyId}
                selectedAnomalyDetail={selectedAnomalyDetail}
                onSelectAnomaly={handleConstellationSelect}
              />
            )}
          </Suspense>
        )}
      </section>

      <section className="workspace">
        <div className="chart-panel">
          <div className="chart-card control-card">
            <div className="panel-header">
              <div>
                <p className="panel-label">Investigation controls</p>
                <h2>Filter the evidence before you interpret it</h2>
              </div>
            </div>

            <div className="control-grid">
              <label className="dataset-picker">
                <span>Dataset</span>
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

              <label className="dataset-picker">
                <span>Minimum severity</span>
                <select value={minSeverity} onChange={(event) => setMinSeverity(event.target.value)}>
                  {MIN_SEVERITY_OPTIONS.map((option) => (
                    <option value={option.value} key={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="dataset-picker">
                <span>Direction</span>
                <select
                  value={directionFilter}
                  onChange={(event) => setDirectionFilter(event.target.value)}
                >
                  {DIRECTION_OPTIONS.map((option) => (
                    <option value={option.value} key={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="window-pills" aria-label="Date window">
              {DATE_WINDOW_OPTIONS.map((option) => (
                <button
                  type="button"
                  key={option.value}
                  className={`window-pill ${selectedDateWindow === option.value ? "active" : ""}`}
                  onClick={() => setSelectedDateWindow(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="chart-panel">
            <div className="panel-header">
              <div>
                <p className="panel-label">Dataset</p>
                <h2>{selectedDataset?.name ?? "Loading datasets..."}</h2>
                <p className="panel-meta">
                  {selectedDataset ? `${selectedDataset.source} / ${selectedDataset.frequency}` : ""}
                </p>
              </div>
            </div>

            <div className="chart-card">
              {errorMessage ? (
                <div className="state-card error-card">{errorMessage}</div>
              ) : chartLoading ? (
                <div className="state-card">Loading timeseries and anomalies...</div>
              ) : filteredChartData.length === 0 ? (
                <div className="state-card">No chart data matches the current investigation filters.</div>
              ) : (
                <>
                  <div className="chart-summary">
                    <div>
                      <span>Visible points</span>
                      <strong>{filteredChartData.length}</strong>
                    </div>
                    <div>
                      <span>Visible anomalies</span>
                      <strong>{filteredAnomalies.length}</strong>
                    </div>
                    <div>
                      <span>Latest visible value</span>
                      <strong>{latestVisibleValue !== null ? formatValue(latestVisibleValue) : "n/a"}</strong>
                    </div>
                  </div>

                  <div className="chart-shell">
                    <ResponsiveContainer width="100%" height={420}>
                      <LineChart
                        data={filteredChartData}
                        margin={{ top: 20, right: 24, left: 8, bottom: 8 }}
                      >
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
                          width={84}
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
                            fill={point.anomaly.direction === "down" ? "#f97316" : "#0f766e"}
                            stroke={selectedAnomalyId === point.anomaly.id ? "#7f1d1d" : "#fff7ed"}
                            strokeWidth={selectedAnomalyId === point.anomaly.id ? 3 : 2}
                            onClick={() => setSelectedAnomalyId(point.anomaly.id)}
                            ifOverflow="extendDomain"
                          />
                        ))}
                        <Brush
                          dataKey="label"
                          height={28}
                          stroke="#0f766e"
                          travellerWidth={12}
                          startIndex={brushRange.startIndex}
                          endIndex={brushRange.endIndex}
                          onChange={(range) => {
                            if (
                              typeof range?.startIndex === "number" &&
                              typeof range?.endIndex === "number"
                            ) {
                              setBrushRange({
                                startIndex: range.startIndex,
                                endIndex: range.endIndex,
                              });
                            }
                          }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </>
              )}
            </div>
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
                    <p className="panel-label">Evidence provenance</p>
                  </header>
                  <div className="provenance-card">
                    <div className="provenance-grid">
                      <article>
                        <span>Primary series</span>
                        <strong>{selectedAnomalyDetail.dataset_name}</strong>
                      </article>
                      <article>
                        <span>Detection</span>
                        <strong>{selectedAnomalyDetail.detection_method}</strong>
                      </article>
                      <article>
                        <span>Explanation providers</span>
                        <strong>
                          {evidenceSummary?.explanationProviders.length
                            ? evidenceSummary.explanationProviders.join(", ")
                            : "none"}
                        </strong>
                      </article>
                      <article>
                        <span>Stored articles</span>
                        <strong>{evidenceSummary?.newsCount ?? 0}</strong>
                      </article>
                    </div>

                    {evidenceSummary?.strongestCorrelation ? (
                      <div className="provenance-note">
                        Strongest stored relationship:{" "}
                        <strong>{evidenceSummary.strongestCorrelation.related_dataset_name}</strong>{" "}
                        ({formatCorrelation(evidenceSummary.strongestCorrelation.correlation_score)}) /{" "}
                        {describeLagDays(evidenceSummary.strongestCorrelation.lag_days)} /{" "}
                        {classifyLagDays(evidenceSummary.strongestCorrelation.lag_days)} evidence
                      </div>
                    ) : (
                      <div className="provenance-note">
                        No stored cross-dataset relationship currently supports this anomaly.
                      </div>
                    )}

                    <div className="timing-grid">
                      <article>
                        <span>Leading</span>
                        <strong>{evidenceSummary?.timingCounts.leading ?? 0}</strong>
                      </article>
                      <article>
                        <span>Concurrent</span>
                        <strong>{evidenceSummary?.timingCounts.concurrent ?? 0}</strong>
                      </article>
                      <article>
                        <span>Lagging</span>
                        <strong>{evidenceSummary?.timingCounts.lagging ?? 0}</strong>
                      </article>
                    </div>
                  </div>
                </section>

                <section className="detail-section">
                  <header>
                    <p className="panel-label">News context</p>
                  </header>
                  {selectedAnomalyDetail.news_context.length > 0 ? (
                    <div className="news-list">
                      {selectedAnomalyDetail.news_context.map((item) => (
                        <article className="news-card" key={`${item.article_url}-${item.relevance_rank}`}>
                          <div className="news-card-copy">
                            <h3>
                              <a href={item.article_url} target="_blank" rel="noreferrer">
                                {item.title}
                              </a>
                            </h3>
                            <p>
                              {item.domain ?? item.provider}
                              {item.published_at ? ` / ${formatDate(item.published_at)}` : ""}
                            </p>
                            <div className="news-card-tags">
                              <span
                                className={`timing-badge ${classifyArticleTiming(
                                  item.published_at,
                                  selectedAnomalyDetail.timestamp,
                                )}`}
                              >
                                {describeArticleTiming(item.published_at, selectedAnomalyDetail.timestamp)}
                              </span>
                              <span className="timing-note">
                                {classifyArticleTiming(item.published_at, selectedAnomalyDetail.timestamp)}
                              </span>
                            </div>
                          </div>
                          <div className="news-card-meta">
                            <strong>#{item.relevance_rank}</strong>
                            <span>{item.provider}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-card">No news context is stored for this event yet.</div>
                  )}
                </section>

                <section className="detail-section">
                  <header>
                    <div className="section-header">
                      <p className="panel-label">Generated explanation</p>
                      <button
                        type="button"
                        className="action-button"
                        disabled={regeneratingExplanation}
                        onClick={async () => {
                          setRegeneratingExplanation(true);
                          setErrorMessage("");
                          try {
                            const detail = await regenerateAnomalyExplanation(selectedAnomalyId);
                            setSelectedAnomalyDetail(detail);
                          } catch (error) {
                            setErrorMessage(error.message);
                          } finally {
                            setRegeneratingExplanation(false);
                          }
                        }}
                      >
                        {regeneratingExplanation ? "Regenerating..." : "Regenerate"}
                      </button>
                    </div>
                  </header>
                  {selectedAnomalyDetail.explanations.length > 0 ? (
                    selectedAnomalyDetail.explanations.map((item) => (
                      <article className="explanation-card" key={`${item.provider}-${item.created_at}`}>
                        <p>{item.generated_text}</p>
                        <footer>
                          {item.provider} / {item.model}
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
                            <span>
                              {describeLagDays(item.lag_days)} / {classifyLagDays(item.lag_days)}
                            </span>
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
                <h2>Filtered anomalies</h2>
              </div>
              <span className="list-count">{filteredAnomalies.length}</span>
            </div>
            <div className="anomaly-list">
              {filteredAnomalies.length > 0 ? (
                filteredAnomalies.map((anomaly) => (
                  <button
                    className={`anomaly-list-item ${selectedAnomalyId === anomaly.id ? "active" : ""}`}
                    key={anomaly.id}
                    onClick={() => setSelectedAnomalyId(anomaly.id)}
                    type="button"
                  >
                    <div className="anomaly-list-copy">
                      <span>{formatDate(anomaly.timestamp)}</span>
                      <small>{anomaly.direction ?? "n/a"}</small>
                    </div>
                    <strong>{anomaly.severity_score.toFixed(2)}</strong>
                  </button>
                ))
              ) : (
                <div className="empty-card">No anomalies match the current filters.</div>
              )}
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}
