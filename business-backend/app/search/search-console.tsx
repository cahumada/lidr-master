"use client";

import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { SearchHit, SearchResponse } from "@/lib/ai-service/types";

/**
 * Every toggle carries the number that was measured for it.
 * || Cada toggle lleva el número que se midió para él.
 *
 * These come from the endpoint's own documentation in
 * `ai-service/app/api/search.py`. A switch without that context invites turning
 * off what is worth leaving on: `lexical` looks like "more recall" and costs 29
 * points of hit@1.
 *
 * || Salen de la documentación del propio endpoint. Un switch sin ese contexto
 * invita a apagar lo que conviene dejar prendido: `lexical` parece "más
 * recuperación" y cuesta 29 puntos de acierto@1.
 */
const TOGGLES = [
  {
    name: "rerank" as const,
    label: "Reranker",
    hint: "Medido: p@10 de 0,140 a 0,171 y hallazgo de 86% a 94%, a 3× la latencia.",
  },
  {
    name: "split" as const,
    label: "Descomponer",
    hint: "Divide una pregunta compuesta y suma lo que encuentran las partes. Nunca reordena, así que no puede empeorar el resultado.",
  },
  {
    name: "lexical" as const,
    label: "Rama léxica",
    hint: "Medido: lleva el acierto@1 de 77% a 48% mientras el @10 se queda en 94%. Apagada por default.",
  },
];

export function SearchConsole() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState("10");
  const [moduleCode, setModuleCode] = useState("");
  const [windowType, setWindowType] = useState("");
  const [flags, setFlags] = useState({
    rerank: true,
    split: true,
    lexical: false,
  });

  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);

  async function runSearch(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;

    setPending(true);
    setError(null);
    const startedAt = performance.now();

    const params = new URLSearchParams({
      q: query.trim(),
      limit,
      rerank: String(flags.rerank),
      split: String(flags.split),
      lexical: String(flags.lexical),
    });
    if (moduleCode.trim()) params.set("module_code", moduleCode.trim());
    if (windowType.trim()) params.set("window_type_name", windowType.trim());

    try {
      const response = await fetch(`/api/search?${params}`);
      const body = await response.json();
      if (!response.ok) {
        setResult(null);
        setError(body.error ?? "La búsqueda falló.");
      } else {
        setResult(body as SearchResponse);
      }
    } catch {
      setResult(null);
      setError("No se pudo contactar a la consola.");
    } finally {
      setElapsedMs(Math.round(performance.now() - startedAt));
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={runSearch} className="flex flex-col gap-4">
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="¿Cómo se da de alta una póliza? · CA014"
            className="h-11 text-base"
            aria-label="Consulta"
          />
          <Button
            type="submit"
            disabled={pending || !query.trim()}
            className="h-11 px-6"
          >
            {pending ? "Buscando…" : "Buscar"}
          </Button>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="limit" className="text-xs">
              Resultados
            </Label>
            <Input
              id="limit"
              type="number"
              min={1}
              max={100}
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="module" className="text-xs">
              Módulo
            </Label>
            <Input
              id="module"
              value={moduleCode}
              onChange={(event) => setModuleCode(event.target.value)}
              placeholder="CA"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="window-type" className="text-xs">
              Tipo de ventana
            </Label>
            <Input
              id="window-type"
              value={windowType}
              onChange={(event) => setWindowType(event.target.value)}
              placeholder="Masivo con encabezado"
            />
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          {TOGGLES.map((toggle) => (
            <div
              key={toggle.name}
              className="flex items-start gap-3 rounded-lg border p-3"
            >
              <Switch
                id={toggle.name}
                checked={flags[toggle.name]}
                onCheckedChange={(checked) =>
                  setFlags((current) => ({ ...current, [toggle.name]: checked }))
                }
                className="mt-0.5"
              />
              <div className="flex flex-col gap-1">
                <Label htmlFor={toggle.name} className="text-sm">
                  {toggle.label}
                </Label>
                <p className="text-muted-foreground text-xs leading-relaxed">
                  {toggle.hint}
                </p>
              </div>
            </div>
          ))}
        </div>
      </form>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && <Results result={result} elapsedMs={elapsedMs} />}
    </div>
  );
}

function Results({
  result,
  elapsedMs,
}: {
  result: SearchResponse;
  elapsedMs: number | null;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <span>
          <strong className="text-foreground">{result.count}</strong> resultados
          {elapsedMs !== null && ` · ${elapsedMs} ms`}
          {result.reranked && " · reordenados"}
        </span>
        {Object.entries(result.branch_counts).length > 0 && (
          <span>
            candidatos por rama:{" "}
            {Object.entries(result.branch_counts)
              .map(([branch, count]) => `${branch} ${count}`)
              .join(" · ")}
          </span>
        )}
        {result.identifier_terms.length > 0 && (
          <span>identificadores: {result.identifier_terms.join(", ")}</span>
        )}
      </div>

      {result.sub_queries.length > 0 && (
        <Card>
          <CardContent className="flex flex-col gap-2">
            <p className="text-xs font-medium">
              La consulta se dividió en {result.sub_queries.length} partes
            </p>
            <ul className="flex flex-col gap-1">
              {result.sub_queries.map((sub) => (
                <li key={sub} className="text-muted-foreground text-sm">
                  — {sub}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {result.count === 0 && (
        <p className="text-muted-foreground py-8 text-center text-sm">
          Sin resultados. Con filtros puestos, puede que la búsqueda vectorial
          haya recorrido sus candidatos más cercanos antes de aplicarlos.
        </p>
      )}

      <ol className="flex flex-col gap-3">
        {result.hits.map((hit, index) => (
          <li key={hit.content_hash + index}>
            <Hit hit={hit} position={index + 1} />
          </li>
        ))}
      </ol>
    </div>
  );
}

/** A hit is never rendered without its provenance. || Un hit nunca se muestra sin su procedencia. */
function Hit({ hit, position }: { hit: SearchHit; position: number }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground text-xs tabular-nums">
            {position}
          </span>
          <Badge variant="secondary" className="font-mono text-xs">
            {hit.document_id}
          </Badge>
          {hit.document_title && (
            <span className="text-sm font-medium">{hit.document_title}</span>
          )}
          {hit.module_code && (
            <Badge variant="outline" className="text-xs">
              {hit.module_code}
            </Badge>
          )}
          <span className="text-muted-foreground ml-auto text-xs tabular-nums">
            {hit.score.toFixed(4)}
          </span>
        </div>

        <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
          {hit.section && <span>{hit.section}</span>}
          {hit.bullet_path && <span>› {hit.bullet_path}</span>}
          <span className="ml-auto flex items-center gap-1">
            {hit.branches.map((branch) => (
              <Badge key={branch} variant="outline" className="text-[10px]">
                {branch}
                {hit.ranks[branch] !== undefined && (
                  <span className="text-muted-foreground ml-1 tabular-nums">
                    #{hit.ranks[branch]}
                  </span>
                )}
              </Badge>
            ))}
          </span>
        </div>

        <p className="bg-muted/40 max-h-64 overflow-y-auto rounded-md p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
          {hit.text}
        </p>
      </CardContent>
    </Card>
  );
}
