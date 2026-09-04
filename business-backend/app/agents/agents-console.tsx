"use client";

import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  AgentConfig,
  ModelConfig,
  ProviderConfig,
  ServiceConfig,
} from "@/lib/ai-service/types";

/** `provider:model` is the form's option value; the pair travels together.
 * || `proveedor:modelo` es el value de la opción; el par viaja junto.
 */
function pairValue(provider: string, model: string): string {
  return `${provider}:${model}`;
}

function splitPair(value: string): { provider: string; model: string } | null {
  const separator = value.indexOf(":");
  if (separator <= 0) return null;
  return {
    provider: value.slice(0, separator),
    model: value.slice(separator + 1),
  };
}

const KIND_LABEL: Record<string, string> = {
  supervisor: "orquestador",
  agent: "agente",
  gate: "gate",
};

function KindBadge({ kind }: { kind: string }) {
  return (
    <Badge variant="outline" className="text-[10px]">
      {KIND_LABEL[kind] ?? kind}
    </Badge>
  );
}

function SourceNote({ source }: { source: string }) {
  if (source === "profile") {
    return <span className="text-primary text-[10px] font-medium">perfil</span>;
  }
  if (source === "unset") {
    return <span className="text-muted-foreground text-[10px]">sin definir</span>;
  }
  return <span className="text-muted-foreground text-[10px]">default del servicio</span>;
}

/** A deterministic agent: nothing to configure, and the screen says why.
 * || Un agente determinista: nada que configurar, y la pantalla dice por qué.
 */
function ReadOnlyAgent({ agent }: { agent: AgentConfig }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold">{agent.label}</h2>
          <KindBadge kind={agent.kind} />
          <code className="text-muted-foreground text-[10px]">{agent.key}</code>
        </div>
        <p className="text-sm">{agent.role}</p>
        <p className="text-muted-foreground text-xs leading-relaxed">{agent.explanation}</p>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">Herramientas:</span>
          {agent.tools.length === 0 ? (
            <Badge variant="secondary" className="text-[10px]">
              ninguna
            </Badge>
          ) : (
            agent.tools.map((tool) => (
              <Badge key={tool} variant="secondary" className="font-mono text-[10px]">
                {tool}
              </Badge>
            ))
          )}
        </div>
        <p className="text-muted-foreground border-t pt-2 text-xs">
          Determinista: no llama a ningún modelo, así que no tiene persona ni modelo que
          configurar.
          {agent.config_source && (
            <>
              {" "}
              Se ajusta por <code>{agent.config_source}</code>.
            </>
          )}
        </p>
      </CardContent>
    </Card>
  );
}

function EditableAgent({
  agent,
  models,
  providers,
  personaMaxChars,
  onSaved,
}: {
  agent: AgentConfig;
  models: ModelConfig[];
  providers: ProviderConfig[];
  personaMaxChars: number;
  onSaved: (updated: AgentConfig) => void;
}) {
  const effective = agent.effective;
  const [persona, setPersona] = useState(effective?.persona ?? "");
  const [pair, setPair] = useState(
    effective?.sources.model === "profile"
      ? pairValue(effective.provider, effective.model)
      : "",
  );
  const [temperature, setTemperature] = useState(
    effective?.sources.temperature === "profile" ? String(effective.temperature) : "",
  );
  const [maxTokens, setMaxTokens] = useState(
    effective?.sources.max_tokens === "profile" ? String(effective.max_tokens) : "",
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // What the currently picked model accepts. An empty pick means "the service
  // default", whose capability the service already reported on `effective`.
  // || Lo que acepta el modelo elegido. Vacío significa "el default del
  // servicio", cuya capacidad el servicio ya reportó en `effective`.
  const picked = pair ? splitPair(pair) : null;
  const pickedModel = picked
    ? models.find((m) => m.provider === picked.provider && m.model === picked.model)
    : undefined;
  const acceptsTemperature = pickedModel
    ? pickedModel.supports_temperature
    : (effective?.supports_temperature ?? true);

  async function send(method: "PUT" | "DELETE") {
    setPending(true);
    setError(null);
    setSaved(false);

    try {
      const response = await fetch(`/api/config/agents/${agent.key}`, {
        method,
        headers: method === "PUT" ? { "Content-Type": "application/json" } : undefined,
        body:
          method === "PUT"
            ? JSON.stringify({
                persona: persona.trim() || null,
                provider: picked?.provider ?? null,
                model: picked?.model ?? null,
                // A model that rejects sampling parameters gets no temperature
                // at all — sending one would be answered with a 400.
                // || Un modelo que rechaza los parámetros de sampling no lleva
                // temperatura: mandarla se contesta con un 400.
                temperature:
                  !acceptsTemperature || temperature === "" ? null : Number(temperature),
                max_tokens: maxTokens === "" ? null : Number(maxTokens),
              })
            : undefined,
      });
      const body = (await response.json()) as AgentConfig & { error?: string };
      if (!response.ok) {
        setError(body.error ?? "No se pudo guardar el perfil.");
        return;
      }
      // Re-seed the form from what the service says is now in force, so a
      // value it normalized (a blank persona, a cleared knob) is visible.
      // || Se recarga el formulario con lo que el servicio dice que quedó
      // vigente, así un valor que normalizó queda a la vista.
      setPersona(body.effective?.persona ?? "");
      setPair(
        body.effective?.sources.model === "profile"
          ? pairValue(body.effective.provider, body.effective.model)
          : "",
      );
      setTemperature(
        body.effective?.sources.temperature === "profile"
          ? String(body.effective.temperature)
          : "",
      );
      setMaxTokens(
        body.effective?.sources.max_tokens === "profile"
          ? String(body.effective.max_tokens)
          : "",
      );
      setSaved(true);
      onSaved(body);
    } catch {
      setError("No se pudo contactar a la consola.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold">{agent.label}</h2>
            <KindBadge kind={agent.kind} />
            <Badge className="text-[10px]">llama a un modelo</Badge>
            <code className="text-muted-foreground text-[10px]">{agent.key}</code>
          </div>
          <p className="text-sm">{agent.role}</p>
          <p className="text-muted-foreground text-xs leading-relaxed">
            {agent.explanation}
          </p>
        </div>

        {effective && (
          <div className="bg-muted/40 grid gap-2 rounded-md p-3 text-xs sm:grid-cols-4">
            <div className="flex flex-col">
              <span className="text-muted-foreground">Proveedor</span>
              <span className="font-mono">
                {providers.find((p) => p.id === effective.provider)?.label ??
                  effective.provider}
              </span>
              <SourceNote source={effective.sources.provider} />
            </div>
            <div className="flex flex-col">
              <span className="text-muted-foreground">Modelo vigente</span>
              <span className="font-mono">{effective.model}</span>
              <SourceNote source={effective.sources.model} />
            </div>
            <div className="flex flex-col">
              <span className="text-muted-foreground">Temperatura</span>
              <span className="font-mono">
                {effective.temperature === null ? "—" : effective.temperature}
              </span>
              <SourceNote source={effective.sources.temperature} />
            </div>
            <div className="flex flex-col">
              <span className="text-muted-foreground">Tope de tokens</span>
              <span className="font-mono">{effective.max_tokens}</span>
              <SourceNote source={effective.sources.max_tokens} />
            </div>
          </div>
        )}

        {effective && !effective.provider_available && (
          <Alert variant="destructive">
            <AlertDescription className="text-xs">
              El proveedor vigente (<strong>{effective.provider}</strong>) no tiene clave
              configurada en el servicio, así que la próxima respuesta va a fallar. Elegí
              un modelo de un proveedor disponible o configurá su clave.
            </AlertDescription>
          </Alert>
        )}

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor={`persona-${agent.key}`} className="text-xs">
              Persona
            </Label>
            <span
              className={`text-[10px] ${
                persona.length > personaMaxChars
                  ? "text-destructive font-medium"
                  : "text-muted-foreground"
              }`}
            >
              {persona.length} / {personaMaxChars}
            </span>
          </div>
          <Textarea
            id={`persona-${agent.key}`}
            value={persona}
            onChange={(event) => setPersona(event.target.value)}
            placeholder="p. ej. Respondé como un analista funcional: primero la regla, después el caso borde."
            rows={4}
          />
          <p className="text-muted-foreground text-[10px] leading-relaxed">
            Se appendea al system prompt <strong>después</strong> de las reglas de
            grounding y subordinada a ellas: cambia la voz, no puede pedirle al modelo
            que deje de citar sus fuentes. Vacío = sin persona.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`model-${agent.key}`} className="text-xs">
              Modelo
            </Label>
            <select
              id={`model-${agent.key}`}
              value={pair}
              onChange={(event) => setPair(event.target.value)}
              className="border-input bg-background h-9 rounded-md border px-3 text-sm"
            >
              <option value="">Default del servicio</option>
              {providers.map((provider) => {
                const owned = models.filter((m) => m.provider === provider.id);
                if (owned.length === 0) return null;
                return (
                  <optgroup
                    key={provider.id}
                    label={
                      provider.available
                        ? provider.label
                        : `${provider.label} — sin clave configurada`
                    }
                  >
                    {owned.map((option) => (
                      <option
                        key={pairValue(option.provider, option.model)}
                        value={pairValue(option.provider, option.model)}
                        disabled={!option.available}
                      >
                        {option.model}
                        {option.supports_temperature ? "" : " · sin temperatura"}
                      </option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`temperature-${agent.key}`} className="text-xs">
              Temperatura
            </Label>
            <Input
              id={`temperature-${agent.key}`}
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={acceptsTemperature ? temperature : ""}
              placeholder={acceptsTemperature ? "default" : "no aplica"}
              disabled={!acceptsTemperature}
              onChange={(event) => setTemperature(event.target.value)}
            />
            {!acceptsTemperature && (
              <p className="text-muted-foreground text-[10px] leading-relaxed">
                Este modelo rechaza los parámetros de sampling: mandarle una temperatura
                devuelve un 400, así que no se manda.
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`max-tokens-${agent.key}`} className="text-xs">
              Tope de tokens
            </Label>
            <Input
              id={`max-tokens-${agent.key}`}
              type="number"
              min={1}
              max={8192}
              value={maxTokens}
              placeholder="default"
              onChange={(event) => setMaxTokens(event.target.value)}
            />
          </div>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription className="text-xs">{error}</AlertDescription>
          </Alert>
        )}
        {saved && !error && (
          <p className="text-xs text-emerald-600 dark:text-emerald-400">
            Guardado. Se aplica en la próxima consulta, en `/answer` y en
            `/answer/agentic`.
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            disabled={pending || persona.length > personaMaxChars}
            onClick={() => send("PUT")}
          >
            {pending ? "Guardando…" : "Guardar perfil"}
          </Button>
          <Button variant="outline" disabled={pending} onClick={() => send("DELETE")}>
            Volver a los defaults
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function AgentsConsole({ initialConfig }: { initialConfig: ServiceConfig }) {
  const [config, setConfig] = useState(initialConfig);

  function replaceAgent(updated: AgentConfig) {
    setConfig((current) => ({
      ...current,
      agents: current.agents.map((agent) =>
        agent.key === updated.key ? updated : agent,
      ),
    }));
  }

  if (config.agents.length === 0) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          No se pudo leer el catálogo del servicio IA. Con el servicio apagado esta
          pantalla no tiene qué mostrar: el catálogo vive ahí, no acá.
        </AlertDescription>
      </Alert>
    );
  }

  const editable = config.agents.filter((agent) => agent.configurable);
  const readOnly = config.agents.filter((agent) => !agent.configurable);

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Configurables</h2>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            Los agentes que llaman a un modelo. Un campo vacío significa «usar el default
            del servicio», no «vacío».
          </p>
        </div>
        {editable.map((agent) => (
          <EditableAgent
            key={agent.key}
            agent={agent}
            models={config.models}
            providers={config.providers}
            personaMaxChars={config.persona_max_chars}
            onSaved={replaceAgent}
          />
        ))}
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Deterministas</h2>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            No llaman a ningún modelo: su comportamiento sale de código y de settings, no
            de un prompt. Es lo que mantiene reproducibles los números de las
            evaluaciones — y la razón por la que persona y modelo no aplican acá.
          </p>
        </div>
        {readOnly.map((agent) => (
          <ReadOnlyAgent key={agent.key} agent={agent} />
        ))}
      </section>
    </div>
  );
}
