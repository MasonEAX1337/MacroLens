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
  fetchDatasetLeadingIndicators,
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

const MAX_COMPARED_EPISODES = 3;

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

function getSupportingEpisodeKey(episode) {
  return `${episode.target_cluster_id}-${episode.target_anomaly_id}`;
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

function getContextTimingClass(item, anomalyTimestamp) {
  if (item.timing_relation === "before") {
    return "leading";
  }
  if (item.timing_relation === "during") {
    return "concurrent";
  }
  if (item.timing_relation === "after") {
    return "lagging";
  }
  return classifyArticleTiming(item.published_at, anomalyTimestamp);
}

function describeContextTiming(item, anomalyTimestamp) {
  if (item.timing_relation === "before") {
    return "before the episode";
  }
  if (item.timing_relation === "during") {
    return "during the episode";
  }
  if (item.timing_relation === "after") {
    return "after the episode";
  }
  return describeArticleTiming(item.published_at, anomalyTimestamp);
}

function formatRetrievalScope(scope) {
  if (scope === "episode") {
    return "episode window";
  }
  if (scope === "anomaly") {
    return "anomaly window";
  }
  if (scope === "curated_timeline") {
    return "curated timeline";
  }
  if (scope === "dataset_backdrop") {
    return "dataset backdrop";
  }
  return "stored context";
}

function formatEventTheme(theme) {
  if (!theme) {
    return null;
  }
  return theme.replace(/_/g, " ");
}

function splitContextEvidence(detail) {
  if (!detail || detail.news_context.length === 0) {
    return { likelyDrivers: [], supportingArticles: [] };
  }

  const likelyDrivers = [];
  const supportingArticles = [];

  detail.news_context.forEach((item, index) => {
    const timingRelation = item.timing_relation ?? "unknown";
    const isLikelyDriver =
      index === 0 ||
      item.provider === "macro_timeline" ||
      item.source_kind === "dataset_driver_fallback" ||
      timingRelation === "during" ||
      timingRelation === "before";

    if (isLikelyDriver && likelyDrivers.length < 2) {
      likelyDrivers.push(item);
      return;
    }
    supportingArticles.push(item);
  });

  return { likelyDrivers, supportingArticles };
}

function describeClusterSpan(cluster) {
  if (!cluster) {
    return "n/a";
  }

  if (cluster.start_timestamp === cluster.end_timestamp) {
    return formatDate(cluster.start_timestamp);
  }

  return `${formatDate(cluster.start_timestamp)} to ${formatDate(cluster.end_timestamp)}`;
}

function describeClusterDuration(cluster) {
  if (!cluster) {
    return "n/a";
  }

  const start = new Date(cluster.start_timestamp);
  const end = new Date(cluster.end_timestamp);
  start.setHours(0, 0, 0, 0);
  end.setHours(0, 0, 0, 0);
  const durationDays = Math.round((end.getTime() - start.getTime()) / 86400000);
  return durationDays === 0 ? "single-day cluster" : `${durationDays + 1}-day span`;
}

function formatEpisodeKind(kind) {
  if (kind === "cross_dataset_episode") {
    return "cross-dataset episode";
  }
  if (kind === "single_dataset_wave") {
    return "single-dataset wave";
  }
  return "isolated signal";
}

function formatFrequencyMix(frequencyMix) {
  if (!frequencyMix) {
    return "n/a";
  }
  return frequencyMix.replace("_", " ");
}

function formatQualityBand(qualityBand) {
  return qualityBand ? `${qualityBand} quality` : "n/a";
}

function formatEvidenceStrength(score) {
  if (score >= 0.75) {
    return "strong";
  }
  if (score >= 0.5) {
    return "moderate";
  }
  return "weak";
}

function formatShare(value) {
  return `${Math.round(value * 100)}%`;
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

function LeadingIndicatorCard({
  item,
  expandedLeadingIndicatorId,
  setExpandedLeadingIndicatorId,
  selectedComparisonKeys,
  onToggleComparison,
  onClearComparison,
  onSelectEpisode,
}) {
  const comparedEpisodes = selectedComparisonKeys
    .map((key) =>
      item.supporting_episodes.find((episode) => getSupportingEpisodeKey(episode) === key),
    )
    .filter(Boolean);

  return (
    <article className="leading-indicator-card">
      <div className="leading-indicator-top">
        <div>
          <h3>{item.related_dataset_name}</h3>
          <p>
            {item.supporting_cluster_count} of {item.target_cluster_count} target cluster
            {item.target_cluster_count === 1 ? "" : "s"}
          </p>
          <p className="leading-indicator-frequency-pair">
            {item.related_dataset_frequency} to {item.target_dataset_frequency}
          </p>
        </div>
        <div className="propagation-score">
          <strong>{item.consistency_score.toFixed(2)}</strong>
          <span>consistency</span>
        </div>
      </div>

      <div className="leading-indicator-metrics leading-indicator-metrics-wide">
        <article>
          <span>Coverage</span>
          <strong>{formatShare(item.cluster_coverage)}</strong>
        </article>
        <article>
          <span>Support confidence</span>
          <strong>{formatShare(item.support_confidence)}</strong>
        </article>
        <article>
          <span>Average lead</span>
          <strong>{item.average_lead_days} day(s)</strong>
        </article>
        <article>
          <span>Average strength</span>
          <strong>{item.average_abs_correlation_score.toFixed(2)}</strong>
        </article>
        <article>
          <span>Sign consistency</span>
          <strong>{formatShare(item.sign_consistency)}</strong>
        </article>
        <article>
          <span>Frequency fit</span>
          <strong>{formatShare(item.frequency_alignment)}</strong>
        </article>
        <article>
          <span>Strongest link</span>
          <strong>{formatCorrelation(item.strongest_correlation_score)}</strong>
        </article>
      </div>

      <div className="propagation-note">
        Dominant direction: <strong>{item.dominant_direction}</strong>. This ranking aggregates
        only leading relationships and collapses duplicate matches inside the same target cluster.
        It is a repeated-pattern view, not causal proof. Support confidence reflects how many
        distinct target clusters actually back the ranking, so one-cluster leaders stay visible
        without looking fully mature.
      </div>

      <div className="leading-indicator-support">
        <div className="leading-indicator-support-header">
          <div className="leading-indicator-support-copy">
            <span>Supporting episodes</span>
            <small>
              Select up to {MAX_COMPARED_EPISODES} episodes to compare regimes side by side.
            </small>
          </div>
          <button
            type="button"
            className="action-button subtle"
            onClick={() =>
              setExpandedLeadingIndicatorId((current) =>
                current === item.related_dataset_id ? null : item.related_dataset_id,
              )
            }
          >
            {expandedLeadingIndicatorId === item.related_dataset_id
              ? "Hide episodes"
              : `Show episodes (${item.supporting_episodes.length})`}
          </button>
        </div>

        {expandedLeadingIndicatorId === item.related_dataset_id ? (
          <>
            {comparedEpisodes.length > 0 ? (
              <section className="leading-indicator-comparison">
                <div className="leading-indicator-comparison-header">
                  <div>
                    <strong>Episode comparison</strong>
                    <p>
                      Compare how this leader appears across stored target clusters before you
                      inspect one anomaly in depth.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="action-button subtle"
                    onClick={() => onClearComparison(item.related_dataset_id)}
                  >
                    Clear selection
                  </button>
                </div>

                {comparedEpisodes.length < 2 ? (
                  <div className="leading-indicator-comparison-note">
                    Select one more episode to make the comparison meaningful.
                  </div>
                ) : null}

                <div className="leading-indicator-comparison-grid">
                  {comparedEpisodes.map((episode) => (
                    <article
                      className="leading-indicator-comparison-card"
                      key={`${item.related_dataset_id}-${getSupportingEpisodeKey(episode)}`}
                    >
                      <div className="leading-indicator-comparison-top">
                        <div>
                          <strong>
                            {formatDate(episode.target_cluster_start_timestamp)}
                            {episode.target_cluster_start_timestamp !==
                            episode.target_cluster_end_timestamp
                              ? ` to ${formatDate(episode.target_cluster_end_timestamp)}`
                              : ""}
                          </strong>
                          <p>
                            cluster {episode.target_cluster_id} /{" "}
                            {episode.target_cluster_anomaly_count} anomaly
                            {episode.target_cluster_anomaly_count === 1 ? "" : "ies"} /{" "}
                            {episode.target_cluster_dataset_count} dataset
                            {episode.target_cluster_dataset_count === 1 ? "" : "s"}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="action-button subtle"
                          onClick={() =>
                            onToggleComparison(
                              item.related_dataset_id,
                              getSupportingEpisodeKey(episode),
                            )
                          }
                        >
                          Remove
                        </button>
                      </div>

                      <div className="leading-indicator-comparison-metrics">
                        <article>
                          <span>Matched lag</span>
                          <strong>{describeLagDays(episode.lag_days)}</strong>
                        </article>
                        <article>
                          <span>Correlation</span>
                          <strong>{formatCorrelation(episode.correlation_score)}</strong>
                        </article>
                        <article>
                          <span>Target event</span>
                          <strong>{formatDate(episode.target_timestamp)}</strong>
                        </article>
                        <article>
                          <span>Method</span>
                          <strong>{episode.target_detection_method}</strong>
                        </article>
                        <article>
                          <span>Direction</span>
                          <strong>{episode.target_direction ?? "n/a"}</strong>
                        </article>
                        <article>
                          <span>Severity</span>
                          <strong>{episode.target_severity_score.toFixed(2)}</strong>
                        </article>
                        <article>
                          <span>Cluster peak</span>
                          <strong>{episode.target_cluster_peak_severity_score.toFixed(2)}</strong>
                        </article>
                        <article>
                          <span>Episode type</span>
                          <strong>{formatEpisodeKind(episode.target_cluster_episode_kind)}</strong>
                        </article>
                        <article>
                          <span>Episode quality</span>
                          <strong>{formatQualityBand(episode.target_cluster_quality_band)}</strong>
                        </article>
                        <article>
                          <span>Frequency mix</span>
                          <strong>{formatFrequencyMix(episode.target_cluster_frequency_mix)}</strong>
                        </article>
                      </div>

                      <div className="leading-indicator-member-preview comparison-preview">
                        <span>Cluster members</span>
                        <div className="leading-indicator-member-list">
                          {episode.cluster_members.map((member) => (
                            <div
                              className="leading-indicator-member-chip"
                              key={`${episode.target_cluster_id}-${member.anomaly_id}`}
                            >
                              <strong>{member.dataset_name}</strong>
                              <small>
                                {formatDate(member.timestamp)} / {member.direction ?? "n/a"} /{" "}
                                {member.detection_method}
                              </small>
                            </div>
                          ))}
                        </div>
                      </div>

                      <button
                        type="button"
                        className="action-button"
                        onClick={() => onSelectEpisode(episode.target_anomaly_id)}
                      >
                        Inspect this cluster
                      </button>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            <div className="leading-indicator-episode-list">
              {item.supporting_episodes.map((episode) => {
                const episodeKey = getSupportingEpisodeKey(episode);
                const isCompared = selectedComparisonKeys.includes(episodeKey);

                return (
                  <article
                    className={`leading-indicator-episode ${isCompared ? "compared" : ""}`}
                    key={`${item.related_dataset_id}-${episode.target_cluster_id}-${episode.target_anomaly_id}`}
                  >
                    <div className="leading-indicator-episode-top">
                      <div>
                        <strong>
                          {formatDate(episode.target_cluster_start_timestamp)}
                          {episode.target_cluster_start_timestamp !==
                          episode.target_cluster_end_timestamp
                            ? ` to ${formatDate(episode.target_cluster_end_timestamp)}`
                            : ""}
                        </strong>
                        <p>
                          cluster {episode.target_cluster_id} /{" "}
                          {episode.target_cluster_anomaly_count} anomaly
                          {episode.target_cluster_anomaly_count === 1 ? "" : "ies"} /{" "}
                          {episode.target_cluster_dataset_count} dataset
                          {episode.target_cluster_dataset_count === 1 ? "" : "s"}
                        </p>
                      </div>
                      <div className="leading-indicator-episode-signal">
                        <strong>{formatCorrelation(episode.correlation_score)}</strong>
                        <span>{describeLagDays(episode.lag_days)}</span>
                      </div>
                    </div>

                    <div className="leading-indicator-episode-metrics">
                      <article>
                        <span>Target event</span>
                        <strong>{formatDate(episode.target_timestamp)}</strong>
                      </article>
                      <article>
                        <span>Method</span>
                        <strong>{episode.target_detection_method}</strong>
                      </article>
                      <article>
                        <span>Direction</span>
                        <strong>{episode.target_direction ?? "n/a"}</strong>
                      </article>
                      <article>
                        <span>Severity</span>
                        <strong>{episode.target_severity_score.toFixed(2)}</strong>
                      </article>
                      <article>
                        <span>Cluster peak</span>
                        <strong>{episode.target_cluster_peak_severity_score.toFixed(2)}</strong>
                      </article>
                      <article>
                        <span>Episode type</span>
                        <strong>{formatEpisodeKind(episode.target_cluster_episode_kind)}</strong>
                      </article>
                      <article>
                        <span>Quality</span>
                        <strong>{formatQualityBand(episode.target_cluster_quality_band)}</strong>
                      </article>
                    </div>

                    <div className="leading-indicator-episode-note">
                      This is the strongest stored leading match for{" "}
                      <strong>{item.related_dataset_name}</strong> inside this target cluster after
                      deduplication.
                    </div>

                    <div className="leading-indicator-member-preview">
                      <span>Cluster members</span>
                      <div className="leading-indicator-member-list">
                        {episode.cluster_members.map((member) => (
                          <div
                            className="leading-indicator-member-chip"
                            key={`${episode.target_cluster_id}-${member.anomaly_id}`}
                          >
                            <strong>{member.dataset_name}</strong>
                            <small>
                              {formatDate(member.timestamp)} / {member.direction ?? "n/a"} /{" "}
                              {member.detection_method}
                            </small>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="leading-indicator-episode-actions">
                      <button
                        type="button"
                        className={`action-button subtle ${isCompared ? "active" : ""}`}
                        onClick={() => onToggleComparison(item.related_dataset_id, episodeKey)}
                      >
                        {isCompared ? "Remove from comparison" : "Compare episode"}
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => onSelectEpisode(episode.target_anomaly_id)}
                      >
                        Inspect this cluster
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </>
        ) : null}
      </div>
    </article>
  );
}

export default function App() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState(null);
  const [selectedAnomalyDetail, setSelectedAnomalyDetail] = useState(null);
  const [leadingIndicators, setLeadingIndicators] = useState([]);
  const [expandedLeadingIndicatorId, setExpandedLeadingIndicatorId] = useState(null);
  const [leadingIndicatorComparisons, setLeadingIndicatorComparisons] = useState({});
  const [selectedDateWindow, setSelectedDateWindow] = useState("1y");
  const [minSeverity, setMinSeverity] = useState("0");
  const [directionFilter, setDirectionFilter] = useState("all");
  const [brushRange, setBrushRange] = useState({ startIndex: 0, endIndex: 0 });
  const [constellationDatasets, setConstellationDatasets] = useState([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [constellationLoading, setConstellationLoading] = useState(false);
  const [chartLoading, setChartLoading] = useState(false);
  const [leadingIndicatorsLoading, setLeadingIndicatorsLoading] = useState(false);
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
      setLeadingIndicatorsLoading(true);
      setErrorMessage("");

      try {
        const [nextTimeseries, nextAnomalies, nextLeadingIndicators] = await Promise.all([
          fetchDatasetTimeseries(selectedDatasetId, 2000),
          fetchDatasetAnomalies(selectedDatasetId, 250),
          fetchDatasetLeadingIndicators(selectedDatasetId, 6),
        ]);
        if (cancelled) {
          return;
        }
        setTimeseries(nextTimeseries);
        setAnomalies(nextAnomalies);
        setLeadingIndicators(nextLeadingIndicators);
        setExpandedLeadingIndicatorId(nextLeadingIndicators[0]?.related_dataset_id ?? null);
        setLeadingIndicatorComparisons({});
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
          setLeadingIndicators([]);
          setExpandedLeadingIndicatorId(null);
          setSelectedAnomalyId(null);
          setSelectedAnomalyDetail(null);
        }
      } finally {
        if (!cancelled) {
          setChartLoading(false);
          setLeadingIndicatorsLoading(false);
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
  const contextEvidence = useMemo(
    () => splitContextEvidence(selectedAnomalyDetail),
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

  function handleLeadingIndicatorEpisodeSelect(anomalyId) {
    startTransition(() => {
      setErrorMessage("");
      setSelectedAnomalyId(anomalyId);
    });
  }

  function toggleLeadingIndicatorComparison(relatedDatasetId, episodeKey) {
    setLeadingIndicatorComparisons((current) => {
      const existing = current[relatedDatasetId] ?? [];
      const nextSelection = existing.includes(episodeKey)
        ? existing.filter((key) => key !== episodeKey)
        : [...existing, episodeKey].slice(-MAX_COMPARED_EPISODES);

      if (nextSelection.length === 0) {
        const nextState = { ...current };
        delete nextState[relatedDatasetId];
        return nextState;
      }

      return {
        ...current,
        [relatedDatasetId]: nextSelection,
      };
    });
  }

  function clearLeadingIndicatorComparison(relatedDatasetId) {
    setLeadingIndicatorComparisons((current) => {
      if (!current[relatedDatasetId]) {
        return current;
      }

      const nextState = { ...current };
      delete nextState[relatedDatasetId];
      return nextState;
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

            <section className="detail-section">
              <header>
                <p className="panel-label">Leading signals</p>
                <h3 className="section-title">Repeatedly leading datasets for {selectedDataset?.name ?? "this series"}</h3>
              </header>
              {leadingIndicatorsLoading ? (
                <div className="state-card">Aggregating leading relationships across clustered events...</div>
              ) : leadingIndicators.length > 0 ? (
                <div className="leading-indicator-list">
                  {leadingIndicators.map((item) => (
                    <LeadingIndicatorCard
                      key={item.related_dataset_id}
                      item={item}
                      expandedLeadingIndicatorId={expandedLeadingIndicatorId}
                      setExpandedLeadingIndicatorId={setExpandedLeadingIndicatorId}
                      selectedComparisonKeys={
                        leadingIndicatorComparisons[item.related_dataset_id] ?? []
                      }
                      onToggleComparison={toggleLeadingIndicatorComparison}
                      onClearComparison={clearLeadingIndicatorComparison}
                      onSelectEpisode={handleLeadingIndicatorEpisodeSelect}
                    />
                  ))}
                </div>
              ) : (
                <div className="empty-card">
                  No repeated leading relationships are currently strong enough for this dataset.
                </div>
              )}
            </section>
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
                  <article>
                    <span>Cluster size</span>
                    <strong>{selectedAnomalyDetail.cluster?.anomaly_count ?? 1}</strong>
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
                    <p className="panel-label">Macro event cluster</p>
                  </header>
                  {selectedAnomalyDetail.cluster ? (
                    <div className="cluster-card">
                      <div className="cluster-summary-grid">
                        <article>
                          <span>Cluster window</span>
                          <strong>{describeClusterSpan(selectedAnomalyDetail.cluster)}</strong>
                        </article>
                        <article>
                          <span>Anomalies</span>
                          <strong>{selectedAnomalyDetail.cluster.anomaly_count}</strong>
                        </article>
                        <article>
                          <span>Datasets affected</span>
                          <strong>{selectedAnomalyDetail.cluster.dataset_count}</strong>
                        </article>
                        <article>
                          <span>Peak severity</span>
                          <strong>{selectedAnomalyDetail.cluster.peak_severity_score.toFixed(2)}</strong>
                        </article>
                        <article>
                          <span>Episode type</span>
                          <strong>{formatEpisodeKind(selectedAnomalyDetail.cluster.episode_kind)}</strong>
                        </article>
                        <article>
                          <span>Quality</span>
                          <strong>{formatQualityBand(selectedAnomalyDetail.cluster.quality_band)}</strong>
                        </article>
                        <article>
                          <span>Frequency mix</span>
                          <strong>{formatFrequencyMix(selectedAnomalyDetail.cluster.frequency_mix)}</strong>
                        </article>
                      </div>

                      <div className="cluster-window-note">
                        This anomaly belongs to a persisted macro-event cluster spanning{" "}
                        <strong>{describeClusterDuration(selectedAnomalyDetail.cluster)}</strong>. This
                        episode is currently labeled{" "}
                        <strong>{formatEpisodeKind(selectedAnomalyDetail.cluster.episode_kind)}</strong>{" "}
                        with <strong>{formatQualityBand(selectedAnomalyDetail.cluster.quality_band)}</strong>{" "}
                        based on breadth, span, and dataset coverage.
                      </div>

                      <div className="cluster-member-list">
                        {selectedAnomalyDetail.cluster.members.map((member) => (
                          <button
                            className={`anomaly-list-item ${
                              selectedAnomalyId === member.anomaly_id ? "active" : ""
                            }`}
                            key={member.anomaly_id}
                            onClick={() => setSelectedAnomalyId(member.anomaly_id)}
                            type="button"
                          >
                            <div className="anomaly-list-copy">
                              <span>{member.dataset_name}</span>
                              <small>
                                {formatDate(member.timestamp)} / {member.direction ?? "n/a"} /{" "}
                                {member.detection_method}
                              </small>
                            </div>
                            <strong>{member.severity_score.toFixed(2)}</strong>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="empty-card">This anomaly has not been assigned to a cluster yet.</div>
                  )}
                </section>

                <section className="detail-section">
                  <header>
                    <p className="panel-label">Propagation timeline</p>
                  </header>
                  {selectedAnomalyDetail.propagation_timeline.length > 0 ? (
                    <div className="propagation-list">
                      {selectedAnomalyDetail.propagation_timeline.map((edge) => (
                        <article className="propagation-card" key={`${edge.source_cluster_id}-${edge.target_cluster_id}`}>
                          <div className="propagation-card-top">
                            <div>
                              <h3>
                                {describeClusterSpan({
                                  start_timestamp: edge.target_start_timestamp,
                                  end_timestamp: edge.target_end_timestamp,
                                })}
                              </h3>
                              <p>
                                {edge.target_dataset_names.join(", ")} / {edge.target_anomaly_count} anomaly
                                {edge.target_anomaly_count === 1 ? "" : "ies"} / {edge.target_dataset_count} dataset
                                {edge.target_dataset_count === 1 ? "" : "s"}
                              </p>
                            </div>
                            <div className="propagation-score">
                              <strong>{edge.evidence_strength.toFixed(2)}</strong>
                              <span>{formatEvidenceStrength(edge.evidence_strength)} evidence</span>
                            </div>
                          </div>

                          <div className="propagation-metrics">
                            <article>
                              <span>Average lag</span>
                              <strong>{describeLagDays(edge.average_lag_days)}</strong>
                            </article>
                            <article>
                              <span>Strongest correlation</span>
                              <strong>{formatCorrelation(edge.strongest_correlation_score)}</strong>
                            </article>
                            <article>
                              <span>Supporting links</span>
                              <strong>{edge.supporting_link_count}</strong>
                            </article>
                            <article>
                              <span>Target episode</span>
                              <strong>{formatEpisodeKind(edge.target_episode_kind)}</strong>
                            </article>
                            <article>
                              <span>Target quality</span>
                              <strong>{formatQualityBand(edge.target_quality_band)}</strong>
                            </article>
                          </div>

                          <div className="propagation-breakdown">
                            <article>
                              <span>Correlation</span>
                              <strong>{edge.evidence_strength_components.correlation_strength.toFixed(2)}</strong>
                            </article>
                            <article>
                              <span>Support</span>
                              <strong>{edge.evidence_strength_components.support_density.toFixed(2)}</strong>
                            </article>
                            <article>
                              <span>Timing</span>
                              <strong>{edge.evidence_strength_components.temporal_alignment.toFixed(2)}</strong>
                            </article>
                            <article>
                              <span>Coverage</span>
                              <strong>{edge.evidence_strength_components.target_scale.toFixed(2)}</strong>
                            </article>
                            <article>
                              <span>Episode quality</span>
                              <strong>{edge.evidence_strength_components.episode_quality.toFixed(2)}</strong>
                            </article>
                          </div>

                          <div className="propagation-note">
                            This is a suggested downstream transmission path derived from stored lagged correlations and later anomaly matches. The target episode is{" "}
                            <strong>{formatEpisodeKind(edge.target_episode_kind)}</strong> with{" "}
                            <strong>{formatFrequencyMix(edge.target_frequency_mix)}</strong> frequency composition. It is evidence for sequencing, not proof of causation.
                          </div>

                          <div className="propagation-evidence-list">
                            {edge.evidence.map((item) => (
                              <div
                                className="propagation-evidence-item"
                                key={`${item.source_anomaly_id}-${item.target_anomaly_id}-${item.method}`}
                              >
                                <span>
                                  {item.source_dataset_name} ({formatDate(item.source_timestamp)}) →{" "}
                                  {item.target_dataset_name} ({formatDate(item.target_timestamp)})
                                </span>
                                <strong>
                                  {formatCorrelation(item.correlation_score)} / {describeLagDays(item.lag_days)}
                                </strong>
                              </div>
                            ))}
                          </div>

                          <button
                            type="button"
                            className="action-button"
                            onClick={() =>
                              handleConstellationSelect(
                                edge.target_anchor_dataset_id,
                                edge.target_anchor_anomaly_id,
                              )
                            }
                          >
                            Follow this path
                          </button>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-card">
                      No downstream propagation path is currently supported by stored lagged evidence for this cluster.
                    </div>
                  )}
                </section>

                <section className="detail-section">
                  <header>
                    <p className="panel-label">Likely real-world drivers</p>
                  </header>
                  {contextEvidence.likelyDrivers.length > 0 ? (
                    <div className="news-list">
                      {contextEvidence.likelyDrivers.map((item) => (
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
                            {item.driver_summary ?? item.historical_event_summary ? (
                              <p>{item.driver_summary ?? item.historical_event_summary}</p>
                            ) : null}
                            <div className="news-card-tags">
                              {item.primary_theme ? (
                                <span className="context-theme-badge">
                                  {formatEventTheme(item.primary_theme)}
                                </span>
                              ) : null}
                              <span
                                className={`timing-badge ${getContextTimingClass(
                                  item,
                                  selectedAnomalyDetail.timestamp,
                                )}`}
                              >
                                {describeContextTiming(item, selectedAnomalyDetail.timestamp)}
                              </span>
                              <span className="timing-note">
                                {formatRetrievalScope(item.retrieval_scope)}
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
                    <div className="empty-card">
                      <p>No likely real-world driver context is stored for this event yet.</p>
                      <div className={`news-status-note ${selectedAnomalyDetail.news_context_status.status}`}>
                        {selectedAnomalyDetail.news_context_status.note}
                      </div>
                    </div>
                  )}
                </section>

                {contextEvidence.supportingArticles.length > 0 ? (
                  <section className="detail-section">
                    <header>
                      <p className="panel-label">Supporting articles</p>
                    </header>
                    <div className="news-list">
                      {contextEvidence.supportingArticles.map((item) => (
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
                            {item.driver_summary ?? item.historical_event_summary ? (
                              <p>{item.driver_summary ?? item.historical_event_summary}</p>
                            ) : null}
                            <div className="news-card-tags">
                              {item.primary_theme ? (
                                <span className="context-theme-badge">
                                  {formatEventTheme(item.primary_theme)}
                                </span>
                              ) : null}
                              <span
                                className={`timing-badge ${getContextTimingClass(
                                  item,
                                  selectedAnomalyDetail.timestamp,
                                )}`}
                              >
                                {describeContextTiming(item, selectedAnomalyDetail.timestamp)}
                              </span>
                              <span className="timing-note">
                                {formatRetrievalScope(item.retrieval_scope)}
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
                  </section>
                ) : null}

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
                      <small>
                        {anomaly.direction ?? "n/a"}
                        {anomaly.cluster_anomaly_count > 1
                          ? ` / cluster ${anomaly.cluster_anomaly_count}`
                          : ""}
                      </small>
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
