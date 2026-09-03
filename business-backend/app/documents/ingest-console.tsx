"use client";

import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ChunkedDocument, IngestResponse } from "@/lib/ai-service/types";

/**
 * Preview only. There is no "save" button because there is no endpoint to pair
 * it with: `/documents/ingest-file` chunks the document and forgets it.
 * || Solo vista previa. No hay botón de "guardar" porque no hay endpoint que lo
 * acompañe: `/documents/ingest-file` trocea el documento y lo olvida.
 */
export function IngestConsole() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;

    setPending(true);
    setError(null);

    const form = new FormData();
    form.append("file", file);

    try {
      const response = await fetch("/api/documents/ingest-file", {
        method: "POST",
        body: form,
      });
      const body = await response.json();
      if (!response.ok) {
        setResult(null);
        setError(body.error ?? "La ingesta falló.");
      } else {
        setResult(body as IngestResponse);
      }
    } catch {
      setResult(null);
      setError("No se pudo contactar a la consola.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={upload} className="flex flex-wrap items-center gap-3">
        <Input
          type="file"
          accept=".md,text/markdown"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          className="max-w-md"
          aria-label="Documento markdown"
        />
        <Button type="submit" disabled={pending || !file}>
          {pending ? "Troceando…" : "Trocear"}
        </Button>
      </form>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && (
        <div className="flex flex-col gap-6">
          <Stats result={result} />
          {result.documents.map((document) => (
            <DocumentChunks key={document.document_id} document={document} />
          ))}
        </div>
      )}
    </div>
  );
}

function Stats({ result }: { result: IngestResponse }) {
  const cells = [
    { label: "Documentos", value: result.stats.total_documents },
    { label: "Chunks", value: result.stats.total_chunks },
    { label: "Tokens", value: result.stats.total_tokens.toLocaleString("es") },
    { label: "De tabla", value: result.stats.table_chunks },
    { label: "Narrativos", value: result.stats.narrative_chunks },
  ];

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <p className="text-muted-foreground font-mono text-xs">
          {result.source_file}
        </p>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          {cells.map((cell) => (
            <div key={cell.label} className="flex flex-col">
              <dt className="text-muted-foreground text-xs">{cell.label}</dt>
              <dd className="text-lg font-medium tabular-nums">{cell.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

/**
 * A source file can carry several transactions, each its own document -- so the
 * result is a list, not one document.
 * || Un archivo fuente puede llevar varias transacciones, cada una su propio
 * documento -- por eso el resultado es una lista y no un documento.
 */
function DocumentChunks({ document }: { document: ChunkedDocument }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="font-mono text-xs">
          {document.document_id}
        </Badge>
        <span className="text-sm font-medium">{document.document_title}</span>
        <Badge variant="outline" className="text-xs">
          {document.transaction_type}
        </Badge>
        {document.document_kind === "index" && (
          <Badge variant="outline" className="text-xs">
            índice
          </Badge>
        )}
        {document.navigation_path && (
          <span className="text-muted-foreground text-xs">
            {document.navigation_path}
          </span>
        )}
      </div>

      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[26%]">Chunk</TableHead>
              <TableHead className="w-[14%]">Sección</TableHead>
              <TableHead className="w-[10%]">Tipo</TableHead>
              <TableHead className="w-[8%] text-right">Tokens</TableHead>
              <TableHead>Texto</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {document.chunks.map((chunk) => (
              <TableRow key={chunk.chunk_id}>
                <TableCell className="font-mono text-xs break-all">
                  {chunk.chunk_id}
                </TableCell>
                <TableCell className="text-xs">
                  {chunk.metadata.section}
                </TableCell>
                <TableCell className="text-xs">
                  {chunk.metadata.chunk_type}
                </TableCell>
                <TableCell className="text-right text-xs tabular-nums">
                  {chunk.token_count}
                </TableCell>
                <TableCell className="text-muted-foreground max-w-md truncate text-xs">
                  {chunk.text}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
