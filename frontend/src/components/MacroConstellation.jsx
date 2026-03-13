import { useEffect, useMemo, useRef, useState } from "react";
import {
  AmbientLight,
  BufferAttribute,
  BufferGeometry,
  Clock,
  Color,
  DirectionalLight,
  Float32BufferAttribute,
  FogExp2,
  Group,
  Line,
  LineBasicMaterial,
  LineDashedMaterial,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  PointLight,
  Points,
  PointsMaterial,
  QuadraticBezierCurve3,
  Raycaster,
  Scene,
  SphereGeometry,
  SRGBColorSpace,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const DATASET_COLORS = ["#14b8a6", "#f97316", "#0284c7", "#e11d48", "#7c3aed", "#d97706"];
const DAY_MS = 86400000;

function getDateWindowCutoff(points, selectedWindow) {
  if (selectedWindow === "all" || points.length === 0) {
    return null;
  }

  const latestTimestamp = points[points.length - 1].timestampMs;
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

function buildFilteredDataset(datasetEntry, selectedDateWindow, minSeverity, directionFilter) {
  const timeseries = datasetEntry.timeseries
    .map((point) => ({
      ...point,
      timestampMs: new Date(point.timestamp).getTime(),
    }))
    .sort((left, right) => left.timestampMs - right.timestampMs);
  const cutoff = getDateWindowCutoff(timeseries, selectedDateWindow);

  const filteredPoints = timeseries.filter((point) => (cutoff ? point.timestampMs >= cutoff : true));
  const severityThreshold = Number(minSeverity);
  const anomalyMap = new Map(
    datasetEntry.anomalies
      .filter((item) => (cutoff ? new Date(item.timestamp).getTime() >= cutoff : true))
      .filter((item) => item.severity_score >= severityThreshold)
      .filter((item) => directionFilter === "all" || item.direction === directionFilter)
      .map((item) => [item.timestamp, item]),
  );

  return {
    ...datasetEntry,
    filteredPoints,
    filteredAnomalies: Array.from(anomalyMap.values()),
    anomalyMap,
  };
}

function samplePoints(points, maxPoints = 180) {
  if (points.length <= maxPoints) {
    return points;
  }

  const sampled = [];
  const step = Math.max(Math.floor(points.length / maxPoints), 1);
  for (let index = 0; index < points.length; index += step) {
    sampled.push(points[index]);
  }

  const lastPoint = points[points.length - 1];
  if (sampled[sampled.length - 1] !== lastPoint) {
    sampled.push(lastPoint);
  }

  return sampled;
}

function normalizeValue(value, min, max) {
  if (max === min) {
    return 0;
  }
  return ((value - min) / (max - min)) * 2 - 1;
}

function findClosestPoint(points, targetTimestampMs) {
  if (points.length === 0) {
    return null;
  }

  let closestPoint = points[0];
  let smallestDistance = Math.abs(points[0].timestampMs - targetTimestampMs);

  for (const point of points) {
    const distance = Math.abs(point.timestampMs - targetTimestampMs);
    if (distance < smallestDistance) {
      closestPoint = point;
      smallestDistance = distance;
    }
  }

  return closestPoint;
}

function formatDate(timestamp) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(timestamp));
}

function formatPercent(score) {
  return `${score >= 0 ? "+" : ""}${(score * 100).toFixed(0)}%`;
}

export default function MacroConstellation({
  datasets,
  selectedDateWindow,
  minSeverity,
  directionFilter,
  selectedAnomalyId,
  selectedAnomalyDetail,
  onSelectAnomaly,
}) {
  const containerRef = useRef(null);
  const onSelectAnomalyRef = useRef(onSelectAnomaly);
  const [hoveredItem, setHoveredItem] = useState(null);

  useEffect(() => {
    onSelectAnomalyRef.current = onSelectAnomaly;
  }, [onSelectAnomaly]);

  const filteredDatasets = useMemo(
    () =>
      datasets
        .map((item) => buildFilteredDataset(item, selectedDateWindow, minSeverity, directionFilter))
        .filter((item) => item.filteredPoints.length > 1),
    [datasets, selectedDateWindow, minSeverity, directionFilter],
  );

  const visibleAnomalyCount = useMemo(
    () => filteredDatasets.reduce((sum, item) => sum + item.filteredAnomalies.length, 0),
    [filteredDatasets],
  );

  useEffect(() => {
    if (!containerRef.current || filteredDatasets.length === 0) {
      return undefined;
    }

    const container = containerRef.current;
    const scene = new Scene();
    scene.background = new Color("#020617");
    scene.fog = new FogExp2("#020617", 0.018);

    const renderer = new WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = SRGBColorSpace;
    container.replaceChildren(renderer.domElement);

    const camera = new PerspectiveCamera(42, 1, 0.1, 400);
    camera.position.set(0, 10, 32);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.minDistance = 18;
    controls.maxDistance = 60;
    controls.maxPolarAngle = Math.PI * 0.48;

    const ambientLight = new AmbientLight("#cbd5e1", 1.1);
    const keyLight = new DirectionalLight("#ffffff", 1.4);
    keyLight.position.set(12, 20, 10);
    const rimLight = new PointLight("#38bdf8", 10, 80, 2);
    rimLight.position.set(-16, 10, -20);
    scene.add(ambientLight, keyLight, rimLight);

    const universeGroup = new Group();
    scene.add(universeGroup);

    const starsGeometry = new BufferGeometry();
    const starPositions = new Float32Array(1200 * 3);
    for (let index = 0; index < 1200; index += 1) {
      starPositions[index * 3] = (Math.random() - 0.5) * 120;
      starPositions[index * 3 + 1] = (Math.random() - 0.2) * 50;
      starPositions[index * 3 + 2] = (Math.random() - 0.5) * 120;
    }
    starsGeometry.setAttribute("position", new BufferAttribute(starPositions, 3));
    const starsMaterial = new PointsMaterial({
      color: "#cbd5e1",
      size: 0.14,
      transparent: true,
      opacity: 0.7,
    });
    universeGroup.add(new Points(starsGeometry, starsMaterial));

    const clickableObjects = [];
    const datasetLanes = new Map();
    const laneSpacing = 5.5;
    const half = (filteredDatasets.length - 1) / 2;

    filteredDatasets.forEach((datasetEntry, datasetIndex) => {
      const laneZ = (datasetIndex - half) * laneSpacing;
      const color = DATASET_COLORS[datasetIndex % DATASET_COLORS.length];
      const sampled = samplePoints(datasetEntry.filteredPoints);
      const latestTimestamp = datasetEntry.filteredPoints[datasetEntry.filteredPoints.length - 1].timestampMs;
      const earliestTimestamp = datasetEntry.filteredPoints[0].timestampMs;
      const span = Math.max(latestTimestamp - earliestTimestamp, 1);
      const values = datasetEntry.filteredPoints.map((point) => point.value);
      const minValue = Math.min(...values);
      const maxValue = Math.max(...values);

      const buildPosition = (point) =>
        new Vector3(
          ((point.timestampMs - earliestTimestamp) / span) * 30 - 15,
          normalizeValue(point.value, minValue, maxValue) * 4,
          laneZ,
        );

      const linePositions = [];
      const pointLookup = new Map();
      for (const point of sampled) {
        const position = buildPosition(point);
        linePositions.push(position.x, position.y, position.z);
      }
      for (const point of datasetEntry.filteredPoints) {
        pointLookup.set(point.timestampMs, buildPosition(point));
      }

      datasetLanes.set(datasetEntry.dataset.id, {
        color,
        laneZ,
        pointLookup,
        points: datasetEntry.filteredPoints,
      });

      const lineGeometry = new BufferGeometry();
      lineGeometry.setAttribute("position", new Float32BufferAttribute(linePositions, 3));
      const lineMaterial = new LineBasicMaterial({
        color,
        transparent: true,
        opacity: selectedAnomalyDetail?.dataset_id === datasetEntry.dataset.id ? 1 : 0.78,
      });
      universeGroup.add(new Line(lineGeometry, lineMaterial));

      const laneGeometry = new BufferGeometry().setFromPoints([
        new Vector3(-16.5, -5.8, laneZ),
        new Vector3(16.5, -5.8, laneZ),
      ]);
      const laneGuide = new Line(
        laneGeometry,
        new LineDashedMaterial({
          color: "#334155",
          dashSize: 0.4,
          gapSize: 0.2,
          transparent: true,
          opacity: 0.8,
        }),
      );
      laneGuide.computeLineDistances();
      universeGroup.add(laneGuide);

      for (const anomaly of datasetEntry.filteredAnomalies) {
        const pointTimestamp = new Date(anomaly.timestamp).getTime();
        const position = pointLookup.get(pointTimestamp) ?? findClosestPoint(datasetEntry.filteredPoints, pointTimestamp);
        const vector = position instanceof Vector3 ? position : pointLookup.get(position?.timestampMs);
        if (!vector) {
          continue;
        }

        const sphere = new Mesh(
          new SphereGeometry(Math.min(0.28 + anomaly.severity_score * 0.06, 0.62), 20, 20),
          new MeshStandardMaterial({
            color: anomaly.direction === "down" ? "#fb923c" : color,
            emissive: anomaly.direction === "down" ? "#c2410c" : color,
            emissiveIntensity: selectedAnomalyId === anomaly.id ? 1.4 : 0.65,
            metalness: 0.18,
            roughness: 0.22,
          }),
        );
        sphere.position.copy(vector);
        sphere.userData = {
          kind: "anomaly",
          datasetId: datasetEntry.dataset.id,
          anomalyId: anomaly.id,
          datasetName: datasetEntry.dataset.name,
          timestamp: anomaly.timestamp,
          severityScore: anomaly.severity_score,
          direction: anomaly.direction,
        };
        universeGroup.add(sphere);
        clickableObjects.push(sphere);
      }
    });

    if (selectedAnomalyDetail) {
      const sourceLane = datasetLanes.get(selectedAnomalyDetail.dataset_id);
      const sourceTargetTime = new Date(selectedAnomalyDetail.timestamp).getTime();
      const sourcePoint =
        sourceLane &&
        (sourceLane.pointLookup.get(sourceTargetTime) ??
          sourceLane.pointLookup.get(findClosestPoint(sourceLane.points, sourceTargetTime)?.timestampMs));

      if (sourceLane && sourcePoint) {
        for (const relation of selectedAnomalyDetail.correlations) {
          const targetLane = datasetLanes.get(relation.related_dataset_id);
          if (!targetLane) {
            continue;
          }
          const targetTimestamp = sourceTargetTime + relation.lag_days * DAY_MS;
          const targetPoint =
            targetLane.pointLookup.get(targetTimestamp) ??
            targetLane.pointLookup.get(findClosestPoint(targetLane.points, targetTimestamp)?.timestampMs);
          if (!targetPoint) {
            continue;
          }

          const midPoint = new Vector3(
            (sourcePoint.x + targetPoint.x) / 2,
            Math.max(sourcePoint.y, targetPoint.y) + 3.8,
            (sourcePoint.z + targetPoint.z) / 2,
          );
          const curve = new QuadraticBezierCurve3(sourcePoint, midPoint, targetPoint);
          const curvePoints = curve.getPoints(32);
          const curveGeometry = new BufferGeometry().setFromPoints(curvePoints);
          const curveMaterial = new LineBasicMaterial({
            color: relation.correlation_score >= 0 ? "#38bdf8" : "#f97316",
            transparent: true,
            opacity: 0.7,
          });
          universeGroup.add(new Line(curveGeometry, curveMaterial));
        }
      }
    }

    const raycaster = new Raycaster();
    const pointer = new Vector2();

    function resize() {
      const width = container.clientWidth;
      const height = Math.max(container.clientHeight, 420);
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }

    function handlePointerMove(event) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(clickableObjects, false);
      if (hits.length === 0) {
        setHoveredItem(null);
        return;
      }

      const hit = hits[0].object.userData;
      setHoveredItem({
        datasetName: hit.datasetName,
        timestamp: hit.timestamp,
        severityScore: hit.severityScore,
        direction: hit.direction,
      });
    }

    function handlePointerLeave() {
      setHoveredItem(null);
    }

    function handleClick(event) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(clickableObjects, false);
      if (hits.length === 0) {
        return;
      }

      const hit = hits[0].object.userData;
      onSelectAnomalyRef.current(hit.datasetId, hit.anomalyId);
    }

    let frameId = 0;
    const clock = new Clock();
    function animate() {
      const elapsed = clock.getElapsedTime();
      universeGroup.rotation.y = Math.sin(elapsed * 0.16) * 0.08;
      universeGroup.position.y = Math.sin(elapsed * 0.35) * 0.12;
      controls.update();
      renderer.render(scene, camera);
      frameId = window.requestAnimationFrame(animate);
    }

    resize();
    animate();

    renderer.domElement.addEventListener("pointermove", handlePointerMove);
    renderer.domElement.addEventListener("pointerleave", handlePointerLeave);
    renderer.domElement.addEventListener("click", handleClick);
    window.addEventListener("resize", resize);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
      renderer.domElement.removeEventListener("pointermove", handlePointerMove);
      renderer.domElement.removeEventListener("pointerleave", handlePointerLeave);
      renderer.domElement.removeEventListener("click", handleClick);
      controls.dispose();
      renderer.dispose();
      scene.traverse((object) => {
        if (object.geometry) {
          object.geometry.dispose();
        }
        if (object.material) {
          if (Array.isArray(object.material)) {
            object.material.forEach((item) => item.dispose());
          } else {
            object.material.dispose();
          }
        }
      });
      container.replaceChildren();
    };
  }, [filteredDatasets, selectedAnomalyDetail, selectedAnomalyId]);

  return (
    <section className="constellation-card">
      <div className="panel-header">
        <div>
          <p className="panel-label">Macro constellation</p>
          <h2>See every dataset as one shared evidence field</h2>
          <p className="panel-meta">
            Each luminous lane is one dataset. Brighter spheres are stored anomalies. Curved arcs
            appear for the currently selected anomaly and its strongest stored relationships.
          </p>
        </div>
        <div className="constellation-metrics">
          <article>
            <span>Datasets</span>
            <strong>{filteredDatasets.length}</strong>
          </article>
          <article>
            <span>Visible anomalies</span>
            <strong>{visibleAnomalyCount}</strong>
          </article>
        </div>
      </div>

      <div className="constellation-stage">
        {filteredDatasets.length > 0 ? (
          <div className="constellation-canvas" ref={containerRef} />
        ) : (
          <div className="constellation-empty">
            No datasets have enough visible points for the current window and anomaly filters.
          </div>
        )}

        {filteredDatasets.length > 0 ? hoveredItem ? (
          <div className="constellation-tooltip">
            <p>{hoveredItem.datasetName}</p>
            <strong>{formatDate(hoveredItem.timestamp)}</strong>
            <span>
              {hoveredItem.direction ?? "n/a"} / severity {hoveredItem.severityScore.toFixed(2)}
            </span>
          </div>
        ) : (
          <div className="constellation-tooltip idle">
            <p>Hover an anomaly sphere</p>
            <span>Click to jump into the standard event panel.</span>
          </div>
        ) : null}
      </div>

      <div className="constellation-legend">
        {filteredDatasets.map((item, index) => (
          <article className="constellation-legend-item" key={item.dataset.id}>
            <span
              className="constellation-swatch"
              style={{ "--swatch-color": DATASET_COLORS[index % DATASET_COLORS.length] }}
            />
            <div>
              <strong>{item.dataset.name}</strong>
              <p>
                {item.filteredAnomalies.length} anomalies / latest move{" "}
                {item.filteredPoints.length > 0
                  ? formatPercent(
                      item.filteredPoints[item.filteredPoints.length - 1].value /
                        item.filteredPoints[0].value -
                        1,
                    )
                  : "n/a"}
              </p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
