/**
 * TypeScript mirror of the AI service's Pydantic contracts.
 * || Espejo TypeScript de los contratos Pydantic del servicio IA.
 *
 * These mirror `ai-service/app/generation/rag/schemas.py` and
 * `ai-service/app/ingestion/schemas.py` 1:1. Written by hand and not generated
 * from OpenAPI: there are six shapes, and a generator would add a dependency
 * and a build step to maintain something that changes every few weeks.
 *
 * When the service adds a field, it is added HERE first -- a screen must never
 * read a field this file does not declare.
 *
 * || Espejan `ai-service/app/generation/rag/schemas.py` y
 * `ai-service/app/ingestion/schemas.py` 1:1. Escritos a mano y no generados
 * desde OpenAPI: son seis formas, y un generador agregaría una dependencia y
 * un paso de build para mantener algo que cambia cada varias semanas.
 *
 * Cuando el servicio agrega un campo, se agrega ACÁ primero -- una pantalla
 * nunca debe leer un campo que este archivo no declara.
 */

// --- Búsqueda || Search ------------------------------------------------------

/** One retrieved chunk with its provenance. || Un chunk recuperado con su procedencia. */
export interface SearchHit {
  content_hash: string;
  chunk_id: string;
  /** Transaction code, e.g. 'CA014'. || Código de transacción. */
  document_id: string;
  document_title: string | null;
  section: string | null;
  bullet_path: string | null;
  module_code: string | null;
  text: string;
  /** Fused RRF score. || Puntaje RRF fusionado. */
  score: number;
  /** Which retrieval branches found it. || Qué ramas de recuperación lo encontraron. */
  branches: string[];
  /** Position in each branch that found it. || Posición en cada rama que lo encontró. */
  ranks: Record<string, number>;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  count: number;
  /** Parts a compound question was split into. || Partes en que se dividió una pregunta compuesta. */
  sub_queries: string[];
  reranked: boolean;
  branch_counts: Record<string, number>;
  identifier_terms: string[];
}

/** Query params of `GET /search`, with the service's own defaults. || Params de `GET /search`, con los defaults del servicio. */
export interface SearchParams {
  q: string;
  limit?: number;
  max_per_document?: number;
  /** Several values are OR'd -- matches `module_code` in any of them. || Varios valores se combinan con OR. */
  module_code?: string[];
  window_type_name?: string[];
  lexical?: boolean;
  split?: boolean;
  rerank?: boolean;
}

/** Response for `GET /search/facets`: what a filter can pick from, straight from the corpus. || Respuesta de `GET /search/facets`: de qué puede elegir un filtro, directo del corpus. */
export interface SearchFacets {
  modules: string[];
  window_types: string[];
}

// --- Ingesta de un documento || Single-document ingestion --------------------

export type ChunkType = "table" | "narrative";
export type DocumentKind = "content" | "index";
export type ReferenceType = "inline_transaction" | "footnote_tag";

export interface Reference {
  /** Referenced document id, e.g. 'CA003', 'DF009'. || Id del documento referenciado. */
  code: string;
  type: ReferenceType;
  context: string | null;
}

export interface ChunkMetadata {
  source_type: string;
  document_id: string;
  document_title: string;
  /** Literal heading from the source document, in Spanish. || Heading literal del documento fuente. */
  section: string;
  chunk_type: ChunkType;
  transaction_type: string;
  document_kind: DocumentKind;
  module_code: string | null;
  module_name: string | null;
  submodule_code: string | null;
  submodule_name: string | null;
  tenant_id: string;
  window_type_name: string | null;
  doc_version: string;
  content_hash: string;
  field: string | null;
  bullet_path: string | null;
  continued_from: string | null;
  continues_into: string | null;
}

export interface Chunk {
  chunk_id: string;
  /** Contextual header + content: this is what gets embedded. || Header contextual + contenido: esto es lo que se embebe. */
  text: string;
  metadata: ChunkMetadata;
  token_count: number;
  references: Reference[];
}

export interface ChunkedDocument {
  document_id: string;
  document_title: string;
  parent_transaction_code: string | null;
  /** A block with no id of its own: it describes the family, not one transaction. || Un bloque sin id propio: describe la familia, no una transacción. */
  is_container: boolean;
  transaction_type: string;
  transaction_type_reason: string | null;
  document_kind: DocumentKind;
  child_links: string[];
  navigation_path: string | null;
  is_menu_node: boolean | null;
  content_hash: string;
  source_revision: string | null;
  valid_from: string | null;
  chunks: Chunk[];
}

export interface IngestStats {
  total_documents: number;
  total_chunks: number;
  total_tokens: number;
  table_chunks: number;
  narrative_chunks: number;
}

export interface IngestResponse {
  source_file: string;
  documents: ChunkedDocument[];
  stats: IngestStats;
}

// --- Reconstrucción del corpus || Corpus rebuild -----------------------------

export type RebuildStep = "chunk" | "embed" | "load";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface RebuildRequest {
  steps?: RebuildStep[];
  modules?: string[];
  /** Non-destructive cleanup. || Limpieza NO destructiva. */
  prune?: boolean;
  /** DESTRUCTIVE. Requires the two confirm fields. || DESTRUCTIVO. Exige los dos campos de confirmación. */
  reset?: boolean;
  confirm_tenant_id?: string;
  confirm_doc_version?: string;
  dry_run?: boolean;
}

export interface RebuildStarted {
  job_id: string;
  /** The steps, in run order -- the service reorders them. || Los pasos, en orden de corrida. */
  steps: string[];
  status: string;
}

export interface IngestionJob {
  id: string;
  tenant_id: string;
  doc_version: string;
  status: JobStatus | string;
  steps: string[];
  current_step: string | null;
  /** What each step produced, keyed by step name. || Lo que produjo cada paso, por nombre de paso. */
  result: Record<string, unknown>;
  /** Last progress line, so a long step is not a black box. || Última línea de progreso. */
  progress: Record<string, unknown>;
  /** The message, never a stack trace. || El mensaje, nunca un stack trace. */
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
}

/**
 * The corpus identity a reset has to be confirmed against.
 * || La identidad del corpus contra la que hay que confirmar un reset.
 *
 * Derived from the most recent job rather than read from a settings endpoint:
 * the service does not expose one, and a constant hard-coded in this UI would
 * turn the guard into a formality.
 *
 * || Se deriva del job más reciente en vez de leerse de un endpoint de
 * configuración: el servicio no expone ninguno, y una constante escrita en
 * esta UI convertiría el guard en un trámite.
 */
export interface CorpusIdentity {
  tenant_id: string;
  doc_version: string;
}

// --- Respuesta / agentes || Answer / agents ----------------------------------

/** Body of `POST /answer` and `POST /answer/agentic`. || Cuerpo de ambos endpoints. */
export interface AnswerRequest {
  question: string;
  limit?: number;
  max_per_document?: number;
  module_code?: string[];
  window_type_name?: string[];
  lexical?: boolean;
  split?: boolean;
  rerank?: boolean;
}

export interface RoutingRecord {
  step: number;
  next_agent: string;
  reason: string;
  source: string;
}

export interface AnswerAgenticCompleted {
  status: "completed";
  thread_id: string;
  question: string;
  answer: string;
  citations: SearchHit[];
  grounded: boolean;
  confidence: number | null;
  needs_human_review: boolean;
  review_reasons: string[];
  routing_history: RoutingRecord[];
}

export interface AnswerAgenticPaused {
  status: "awaiting_human_review";
  thread_id: string;
  question: string;
  answer: string | null;
  citations: SearchHit[];
  review_reasons: string[];
  confidence: number | null;
}

export type AnswerAgenticResponse = AnswerAgenticCompleted | AnswerAgenticPaused;

export interface AnswerAgenticResumeRequest {
  thread_id: string;
  decision: "approve" | "reject" | "adjust";
  note?: string | null;
}
