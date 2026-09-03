"use client";

import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type {
  CorpusIdentity,
  IngestionJob,
  RebuildStep,
} from "@/lib/ai-service/types";

const STEPS: { id: RebuildStep; label: string; hint: string }[] = [
  { id: "chunk", label: "Trocear", hint: "Lee los markdown de la fuente." },
  { id: "embed", label: "Embeber", hint: "Incremental: reusa el vector de un texto que no cambió." },
  { id: "load", label: "Cargar", hint: "COPY masivo e idempotente a pgvector." },
];

const ACTIVE = new Set(["queued", "running"]);
const POLL_MS = 2000;

export function CorpusConsole({
  identity,
  initialJobs,
  identityError,
}: {
  identity: CorpusIdentity | null;
  initialJobs: IngestionJob[];
  identityError: string | null;
}) {
  const [steps, setSteps] = useState<Record<RebuildStep, boolean>>({
    chunk: true,
    embed: true,
    load: true,
  });
  const [prune, setPrune] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [reset, setReset] = useState(false);
  const [confirmTenant, setConfirmTenant] = useState("");
  const [confirmVersion, setConfirmVersion] = useState("");

  const [jobs, setJobs] = useState<IngestionJob[]>(initialJobs);
  const [trackedId, setTrackedId] = useState<string | null>(
    initialJobs.find((job) => ACTIVE.has(job.status))?.id ?? null,
  );
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const tracked = jobs.find((job) => job.id === trackedId) ?? null;
  const isTracking = tracked !== null && ACTIVE.has(tracked.status);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/corpus/jobs?limit=20");
      if (!response.ok) return;
      setJobs((await response.json()) as IngestionJob[]);
    } catch {
      // A failed poll is not worth an error banner: the next tick retries.
      // || Un sondeo fallido no merece un cartel de error: el siguiente reintenta.
    }
  }, []);

  useEffect(() => {
    if (!isTracking) return;
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [isTracking, refresh]);

  /**
   * The `reset` guard, repeated here on purpose.
   *
   * The service already refuses a `reset` whose confirmation does not match
   * (`app/api/corpus.py` returns 400). Sending it behind a bare checkbox would
   * reintroduce, one level up, the risk the endpoint was designed to prevent.
   * The values come from the service, never from a constant in this file.
   *
   * || El guard de `reset`, repetido acá a propósito. El servicio ya rechaza un
   * `reset` cuya confirmación no coincide; mandarlo detrás de un checkbox pelado
   * reintroduciría, un nivel más arriba, el riesgo que el endpoint fue diseñado
   * para evitar. Los valores salen del servicio, nunca de una constante en este
   * archivo.
   */
  const resetConfirmed =
    identity !== null &&
    confirmTenant === identity.tenant_id &&
    confirmVersion === identity.doc_version;

  const chosenSteps = STEPS.filter((step) => steps[step.id]).map(
    (step) => step.id,
  );
  const canSubmit =
    !pending && chosenSteps.length > 0 && (!reset || resetConfirmed);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    setPending(true);
    setError(null);
    setConflict(null);

    try {
      const response = await fetch("/api/corpus/rebuild", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          steps: chosenSteps,
          prune,
          dry_run: dryRun,
          reset,
          ...(reset
            ? {
                confirm_tenant_id: confirmTenant,
                confirm_doc_version: confirmVersion,
              }
            : {}),
        }),
      });
      const body = await response.json();

      if (response.status === 409) {
        // Not a failure: the service is telling us a rebuild is already running.
        // || No es una falla: el servicio avisa que ya hay una reconstrucción.
        setConflict(body.error);
        await refresh();
      } else if (!response.ok) {
        setError(body.error ?? "No se pudo iniciar la reconstrucción.");
      } else {
        setTrackedId(body.job_id as string);
        setReset(false);
        setConfirmTenant("");
        setConfirmVersion("");
        await refresh();
      }
    } catch {
      setError("No se pudo contactar a la consola.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {identityError && (
        <Alert variant="destructive">
          <AlertTitle>El servicio IA no respondió</AlertTitle>
          <AlertDescription>{identityError}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={submit} className="flex flex-col gap-5">
        <div className="grid gap-3 sm:grid-cols-3">
          {STEPS.map((step) => (
            <div
              key={step.id}
              className="flex items-start gap-3 rounded-lg border p-3"
            >
              <Switch
                id={step.id}
                checked={steps[step.id]}
                onCheckedChange={(checked) =>
                  setSteps((current) => ({ ...current, [step.id]: checked }))
                }
                className="mt-0.5"
              />
              <div className="flex flex-col gap-1">
                <Label htmlFor={step.id} className="text-sm">
                  {step.label}
                </Label>
                <p className="text-muted-foreground text-xs leading-relaxed">
                  {step.hint}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-2">
            <Switch id="prune" checked={prune} onCheckedChange={setPrune} />
            <Label htmlFor="prune" className="text-sm font-normal">
              Podar lo que el corpus ya no tiene
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch id="dry-run" checked={dryRun} onCheckedChange={setDryRun} />
            <Label htmlFor="dry-run" className="text-sm font-normal">
              Simulación (no llama a la API ni escribe)
            </Label>
          </div>
        </div>

        <ResetGuard
          identity={identity}
          reset={reset}
          setReset={setReset}
          confirmTenant={confirmTenant}
          setConfirmTenant={setConfirmTenant}
          confirmVersion={confirmVersion}
          setConfirmVersion={setConfirmVersion}
          confirmed={resetConfirmed}
        />

        <div>
          <Button type="submit" disabled={!canSubmit}>
            {pending ? "Iniciando…" : "Reconstruir"}
          </Button>
        </div>
      </form>

      {conflict && (
        <Alert>
          <AlertTitle>Ya hay una reconstrucción en curso</AlertTitle>
          <AlertDescription>{conflict}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {tracked && <TrackedJob job={tracked} live={isTracking} />}

      <JobList jobs={jobs} trackedId={trackedId} onSelect={setTrackedId} />
    </div>
  );
}

function ResetGuard({
  identity,
  reset,
  setReset,
  confirmTenant,
  setConfirmTenant,
  confirmVersion,
  setConfirmVersion,
  confirmed,
}: {
  identity: CorpusIdentity | null;
  reset: boolean;
  setReset: (value: boolean) => void;
  confirmTenant: string;
  setConfirmTenant: (value: string) => void;
  confirmVersion: string;
  setConfirmVersion: (value: string) => void;
  confirmed: boolean;
}) {
  return (
    <div className="border-destructive/30 flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex items-center gap-2">
        <Switch
          id="reset"
          checked={reset}
          onCheckedChange={setReset}
          disabled={identity === null}
        />
        <Label htmlFor="reset" className="text-sm">
          Reset — borrar todas las filas de este corpus antes de rehacerlo
        </Label>
      </div>

      {identity === null ? (
        <p className="text-muted-foreground text-xs leading-relaxed">
          No hay ningún trabajo previo del que leer la identidad del corpus, así
          que no hay contra qué confirmar un reset. Corré primero una
          reconstrucción sin reset.
        </p>
      ) : (
        <p className="text-muted-foreground text-xs leading-relaxed">
          Un paso destructivo no viaja como booleano. Escribí el{" "}
          <code className="text-xs">tenant_id</code> y la{" "}
          <code className="text-xs">doc_version</code> del corpus configurado
          para habilitarlo — los mismos dos campos que el servicio exige.
        </p>
      )}

      {reset && identity !== null && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirm-tenant" className="text-xs">
              tenant_id{" "}
              <span className="text-muted-foreground font-mono">
                ({identity.tenant_id})
              </span>
            </Label>
            <Input
              id="confirm-tenant"
              value={confirmTenant}
              onChange={(event) => setConfirmTenant(event.target.value)}
              className="font-mono text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirm-version" className="text-xs">
              doc_version{" "}
              <span className="text-muted-foreground font-mono">
                ({identity.doc_version})
              </span>
            </Label>
            <Input
              id="confirm-version"
              value={confirmVersion}
              onChange={(event) => setConfirmVersion(event.target.value)}
              className="font-mono text-sm"
            />
          </div>
          {!confirmed && (
            <p className="text-muted-foreground text-xs sm:col-span-2">
              Los dos campos tienen que coincidir exactamente.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function statusVariant(status: string) {
  if (status === "failed") return "destructive" as const;
  if (status === "succeeded") return "secondary" as const;
  return "default" as const;
}

function TrackedJob({ job, live }: { job: IngestionJob; live: boolean }) {
  const progress = Object.entries(job.progress);

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
          <span className="font-mono text-xs">{job.id}</span>
          {job.current_step && (
            <span className="text-sm">
              paso actual: <strong>{job.current_step}</strong>
            </span>
          )}
          <span className="text-muted-foreground ml-auto text-xs">
            {job.steps.join(" → ")}
            {live && " · actualizando…"}
          </span>
        </div>

        {progress.length > 0 && (
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {progress.map(([key, value]) => (
              <div key={key} className="flex flex-col">
                <dt className="text-muted-foreground text-xs">{key}</dt>
                <dd className="text-sm tabular-nums">{String(value)}</dd>
              </div>
            ))}
          </dl>
        )}

        {job.error && (
          <Alert variant="destructive">
            <AlertDescription>{job.error}</AlertDescription>
          </Alert>
        )}

        {Object.keys(job.result).length > 0 && (
          <pre className="bg-muted/40 max-h-72 overflow-auto rounded-md p-3 font-mono text-xs">
            {JSON.stringify(job.result, null, 2)}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}

function JobList({
  jobs,
  trackedId,
  onSelect,
}: {
  jobs: IngestionJob[];
  trackedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (jobs.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        Todavía no corrió ninguna reconstrucción.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-medium">Trabajos recientes</h2>
      <ul className="divide-y rounded-md border">
        {jobs.map((job) => (
          <li key={job.id}>
            <button
              type="button"
              onClick={() => onSelect(job.id)}
              className={`hover:bg-muted/50 flex w-full flex-wrap items-center gap-3 px-3 py-2 text-left text-xs transition-colors ${
                job.id === trackedId ? "bg-muted/60" : ""
              }`}
            >
              <Badge variant={statusVariant(job.status)} className="text-[10px]">
                {job.status}
              </Badge>
              <span className="font-mono">{job.id.slice(0, 8)}</span>
              <span className="text-muted-foreground">
                {job.steps.join(" → ")}
              </span>
              <span className="text-muted-foreground ml-auto tabular-nums">
                {new Date(job.created_at).toLocaleString("es")}
                {job.duration_ms !== null &&
                  ` · ${(job.duration_ms / 1000).toFixed(1)} s`}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
