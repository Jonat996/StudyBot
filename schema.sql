CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE students (
  id                uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name              text NOT NULL,
  phone             text UNIQUE,
  channel           text DEFAULT 'whatsapp',
  personal_factor   float DEFAULT 1.0,
  profile           jsonb DEFAULT '{}',
  created_at        timestamptz DEFAULT now()
);

CREATE TABLE tasks (
  id                uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  student_id        uuid REFERENCES students(id) ON DELETE CASCADE,
  week              int NOT NULL,
  subject           text NOT NULL,
  due_date          date,
  difficulty        int CHECK (difficulty BETWEEN 1 AND 5),
  estimated_hours   float NOT NULL,
  days_available    int,
  predicted_hours   float,
  actual_hours      float,
  completed         boolean,
  priority          text CHECK (priority IN ('Maxima','Alta','Media','Baja')),
  origin            text DEFAULT 'chat',
  created_at        timestamptz DEFAULT now()
);

CREATE TABLE schedules (
  id                uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  student_id        uuid REFERENCES students(id) ON DELETE CASCADE,
  week              int NOT NULL,
  slots_by_day      jsonb NOT NULL,
  max_day_load_pct  float,
  generated_at      timestamptz DEFAULT now()
);

CREATE TABLE messages (
  id                uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  student_id        uuid REFERENCES students(id) ON DELETE CASCADE,
  role              text CHECK (role IN ('user','model')),
  content           text NOT NULL,
  created_at        timestamptz DEFAULT now()
);

CREATE TABLE resources (
  id                uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  title             text NOT NULL,
  subject           text,
  topics            text[],
  content           text,
  embedding         vector(768),
  resource_type     text CHECK (resource_type IN ('video','pdf','article','exercise')),
  url               text,
  created_at        timestamptz DEFAULT now()
);

-- Función para búsqueda vectorial (pgvector)
CREATE OR REPLACE FUNCTION match_resources(
  query_embedding vector(768),
  match_count     int,
  filter          jsonb DEFAULT '{}'
)
RETURNS TABLE (
  id            uuid,
  title         text,
  content       text,
  subject       text,
  url           text,
  similarity    float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    r.id,
    r.title,
    r.content,
    r.subject,
    r.url,
    1 - (r.embedding <=> query_embedding) AS similarity
  FROM resources r
  ORDER BY r.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

CREATE INDEX ON tasks(student_id, week);
CREATE INDEX ON messages(student_id, created_at DESC);
CREATE INDEX ON schedules(student_id, week);
CREATE INDEX ON resources USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
