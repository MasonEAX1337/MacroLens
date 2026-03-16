CREATE TABLE IF NOT EXISTS datasets (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    source TEXT NOT NULL,
    description TEXT,
    frequency TEXT NOT NULL DEFAULT 'daily',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_datasets_source_symbol UNIQUE (source, symbol)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL,
    dataset_key TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS data_points (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id BIGINT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_data_points_dataset_timestamp UNIQUE (dataset_id, timestamp)
);

CREATE TABLE IF NOT EXISTS anomalies (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id BIGINT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    severity_score DOUBLE PRECISION NOT NULL,
    direction TEXT,
    detection_method TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_anomalies_dataset_timestamp_method UNIQUE (dataset_id, timestamp, detection_method)
);

CREATE TABLE IF NOT EXISTS anomaly_clusters (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    start_timestamp TIMESTAMPTZ NOT NULL,
    end_timestamp TIMESTAMPTZ NOT NULL,
    anchor_timestamp TIMESTAMPTZ NOT NULL,
    anomaly_count INTEGER NOT NULL,
    dataset_count INTEGER NOT NULL,
    peak_severity_score DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS anomaly_cluster_members (
    cluster_id BIGINT NOT NULL REFERENCES anomaly_clusters(id) ON DELETE CASCADE,
    anomaly_id BIGINT NOT NULL REFERENCES anomalies(id) ON DELETE CASCADE,
    membership_rank INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (cluster_id, anomaly_id),
    CONSTRAINT uq_anomaly_cluster_members_anomaly UNIQUE (anomaly_id)
);

CREATE TABLE IF NOT EXISTS correlations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    anomaly_id BIGINT NOT NULL REFERENCES anomalies(id) ON DELETE CASCADE,
    related_dataset_id BIGINT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    correlation_score DOUBLE PRECISION NOT NULL,
    lag_days INTEGER NOT NULL DEFAULT 0,
    method TEXT NOT NULL DEFAULT 'pearson',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS explanations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    anomaly_id BIGINT NOT NULL REFERENCES anomalies(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    generated_text TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news_context (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    anomaly_id BIGINT NOT NULL REFERENCES anomalies(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    article_url TEXT NOT NULL,
    title TEXT NOT NULL,
    domain TEXT,
    language TEXT,
    source_country TEXT,
    published_at TIMESTAMPTZ,
    search_query TEXT NOT NULL,
    relevance_rank INTEGER NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_news_context_anomaly_provider_url UNIQUE (anomaly_id, provider, article_url)
);

CREATE INDEX IF NOT EXISTS idx_data_points_dataset_timestamp
    ON data_points (dataset_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_anomalies_dataset_timestamp
    ON anomalies (dataset_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_anomaly_clusters_start_timestamp
    ON anomaly_clusters (start_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_anomaly_cluster_members_anomaly
    ON anomaly_cluster_members (anomaly_id);

CREATE INDEX IF NOT EXISTS idx_correlations_anomaly
    ON correlations (anomaly_id);

CREATE INDEX IF NOT EXISTS idx_explanations_anomaly_created
    ON explanations (anomaly_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_context_anomaly_rank
    ON news_context (anomaly_id, relevance_rank ASC, published_at DESC);
