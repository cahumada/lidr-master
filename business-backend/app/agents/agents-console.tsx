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
  NamedAgentProfile,
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

function ModelSelect({
  id,
  pair,
  onChange,
  models,
  providers,
}: {
  id: string;
  pair: string;
  onChange: (value: string) => void;
  models: ModelConfig[];
  providers: ProviderConfig[];
}) {
  return (
    <select
      id={id}
      value={pair}
      onChange={(event) => onChange(event.target.value)}
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
  );
}

function NamedProfileCard({
  agentKey,
  profile,
  models,
  providers,
  personaMaxChars,
  onSaved,
}: {
  agentKey: string;
  profile: NamedAgentProfile;
  models: ModelConfig[];
  providers: ProviderConfig[];
  personaMaxChars: number;
  onSaved: (updated: AgentConfig) => void;
}) {
  const effective = profile.effective;
  const [name, setName] = useState(profile.name);
  const [persona, setPersona] = useState(profile.persona ?? "");
  const [pair, setPair] = useState(
    effective.sources.model === "profile"
      ? pairValue(effective.provider, effective.model)
      : "",
  );
  const [temperature, setTemperature] = useState(
    effective.sources.temperature === "profile" ? String(effective.temperature) : "",
  );
  const [maxTokens, setMaxTokens] = useState(
    effective.sources.max_tokens === "profile" ? String(effective.max_tokens) : "",
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const picked = pair ? splitPair(pair) : null;
  const pickedModel = picked
    ? models.find((m) => m.provider === picked.provider && m.model === picked.model)
    : undefined;
  const acceptsTemperature = pickedModel
    ? pickedModel.supports_temperature
    : effective.supports_temperature;

  async function save(asDefault = profile.is_default) {
    setPending(true);
    setError(null);
    setSaved(false);
    try {
      const response = await fetch(
        `/api/config/agents/${agentKey}/profiles/${profile.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: name.trim(),
            is_default: asDefault,
            persona: persona.trim() || null,
            provider: picked?.provider ?? null,
            model: picked?.model ?? null,
            temperature:
              !acceptsTemperature || temperature === "" ? null : Number(temperature),
            max_tokens: maxTokens === "" ? null : Number(maxTokens),
          }),
        },
      );
      const body = (await response.json()) as AgentConfig & { error?: string };
      if (!response.ok) {
        setError(body.error ?? "No se pudo guardar el perfil.");
        return;
      }
      setSaved(true);
      onSaved(body);
    } catch {
      setError("No se pudo contactar a la consola.");
    } finally {
      setPending(false);
    }
  }

  async function remove() {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/config/agents/${agentKey}/profiles/${profile.id}`,
        { method: "DELETE" },
      );
      const body = (await response.json()) as AgentConfig & { error?: string };
      if (!response.ok) {
        setError(body.error ?? "No se pudo borrar el perfil.");
        return;
      }
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
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">{profile.name}</h3>
          {profile.is_default && <Badge className="text-[10px]">default</Badge>}
          <code className="text-muted-foreground text-[10px]">{profile.id}</code>
        </div>

        <div className="bg-muted/40 grid gap-2 rounded-md p-3 text-xs sm:grid-cols-3">
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

        {effective && !effective.provider_available && (
          <Alert variant="destructive">
            <AlertDescription className="text-xs">
              El proveedor vigente (<strong>{effective.provider}</strong>) no tiene clave
              configurada en el servicio.
            </AlertDescription>
          </Alert>
        )}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`name-${profile.id}`} className="text-xs">
            Nombre
          </Label>
          <Input
            id={`name-${profile.id}`}
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={64}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor={`persona-${profile.id}`} className="text-xs">
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
            id={`persona-${profile.id}`}
            value={persona}
            onChange={(event) => setPersona(event.target.value)}
            placeholder="p. ej. Respondé como un analista funcional: primero la regla, después el caso borde."
            rows={4}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`model-${profile.id}`} className="text-xs">
              Modelo
            </Label>
            <ModelSelect
              id={`model-${profile.id}`}
              pair={pair}
              onChange={setPair}
              models={models}
              providers={providers}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`temperature-${profile.id}`} className="text-xs">
              Temperatura
            </Label>
            <Input
              id={`temperature-${profile.id}`}
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={acceptsTemperature ? temperature : ""}
              placeholder={acceptsTemperature ? "default" : "no aplica"}
              disabled={!acceptsTemperature}
              onChange={(event) => setTemperature(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`max-tokens-${profile.id}`} className="text-xs">
              Tope de tokens
            </Label>
            <Input
              id={`max-tokens-${profile.id}`}
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
            Guardado. Se aplica en la próxima consulta si este perfil es el default o
            si lo elegís en el chat.
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            disabled={pending || !name.trim() || persona.length > personaMaxChars}
            onClick={() => void save()}
          >
            {pending ? "Guardando…" : "Guardar"}
          </Button>
          {!profile.is_default && (
            <Button
              variant="outline"
              disabled={pending}
              onClick={() => void save(true)}
            >
              Usar como default
            </Button>
          )}
          <Button variant="outline" disabled={pending} onClick={() => void remove()}>
            Borrar
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function CreateProfileForm({
  agentKey,
  onSaved,
}: {
  agentKey: string;
  onSaved: (updated: AgentConfig) => void;
}) {
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(`/api/config/agents/${agentKey}/profiles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      const body = (await response.json()) as AgentConfig & { error?: string };
      if (!response.ok) {
        setError(body.error ?? "No se pudo crear el perfil.");
        return;
      }
      setName("");
      onSaved(body);
    } catch {
      setError("No se pudo contactar a la consola.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div>
          <h3 className="text-sm font-semibold">Nuevo perfil</h3>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            Un nombre, como en el curso: <em>Conservador</em>, <em>Exhaustivo</em>.
            La persona y el modelo se editan después.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex min-w-48 flex-1 flex-col gap-1.5">
            <Label htmlFor={`new-name-${agentKey}`} className="text-xs">
              Nombre
            </Label>
            <Input
              id={`new-name-${agentKey}`}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="p. ej. Conservador"
              maxLength={64}
            />
          </div>
          <Button disabled={pending || !name.trim()} onClick={() => void create()}>
            {pending ? "Creando…" : "Crear perfil"}
          </Button>
        </div>
        {error && (
          <Alert variant="destructive">
            <AlertDescription className="text-xs">{error}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

function ConfigurableAgent({
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
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold">{agent.label}</h2>
          <KindBadge kind={agent.kind} />
          <Badge className="text-[10px]">llama a un modelo</Badge>
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
      </div>
      <CreateProfileForm agentKey={agent.key} onSaved={onSaved} />
      {agent.profiles.length === 0 && (
        <p className="text-muted-foreground text-xs">
          Sin perfiles nombrados: el sintetizador corre con los defaults del servicio.
        </p>
      )}
      {agent.profiles.map((profile) => (
        <NamedProfileCard
          key={profile.id}
          agentKey={agent.key}
          profile={profile}
          models={models}
          providers={providers}
          personaMaxChars={personaMaxChars}
          onSaved={onSaved}
        />
      ))}
    </div>
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
            Perfiles nombrados del agente que llama a un modelo. El default se usa
            cuando el chat no elige otro. Un campo vacío significa «usar el default
            del servicio», no «vacío».
          </p>
        </div>
        {editable.map((agent) => (
          <ConfigurableAgent
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
            de un prompt. Por eso no se les crea un perfil.
          </p>
        </div>
        {readOnly.map((agent) => (
          <ReadOnlyAgent key={agent.key} agent={agent} />
        ))}
      </section>
    </div>
  );
}
