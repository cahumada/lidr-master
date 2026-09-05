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
  SystemGuardrail,
  ToolCatalogEntry,
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

function toolDescription(catalog: ToolCatalogEntry[], name: string): string | undefined {
  return catalog.find((item) => item.name === name)?.description;
}

function ToolChips({
  names,
  catalog,
  empty,
}: {
  names: string[];
  catalog: ToolCatalogEntry[];
  empty: string;
}) {
  if (names.length === 0) {
    return (
      <Badge variant="secondary" className="text-[10px]">
        {empty}
      </Badge>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      {names.map((name) => (
        <div key={name} className="flex flex-col gap-0.5">
          <Badge variant="secondary" className="w-fit font-mono text-[10px]">
            {name}
          </Badge>
          {toolDescription(catalog, name) && (
            <span className="text-muted-foreground text-[11px] leading-relaxed">
              {toolDescription(catalog, name)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function ToolPair({
  granted,
  used,
  catalog,
}: {
  granted: string[];
  used: string[];
  catalog: ToolCatalogEntry[];
}) {
  return (
    <div className="grid gap-3 text-xs sm:grid-cols-2">
      <div className="flex flex-col gap-1.5">
        <span className="text-muted-foreground">Disponibles</span>
        <ToolChips names={granted} catalog={catalog} empty="ninguna concedida" />
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="text-muted-foreground">Utilizadas</span>
        <ToolChips names={used} catalog={catalog} empty="ninguna" />
      </div>
    </div>
  );
}

function SystemPromptBlock({ prompt }: { prompt: string }) {
  return (
    <details open className="rounded-md border">
      <summary className="cursor-pointer px-3 py-2 text-xs font-medium">
        System prompt (solo lectura)
      </summary>
      <pre className="bg-muted/40 max-h-80 overflow-auto whitespace-pre-wrap px-3 py-2 font-mono text-[11px] leading-relaxed">
        {prompt}
      </pre>
    </details>
  );
}

function SystemGuardrailsList({ items }: { items: SystemGuardrail[] }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-medium">Guardrails de sistema</p>
      <p className="text-muted-foreground text-[11px] leading-relaxed">
        No se editan: son las cinco reglas del prompt más el chequeo de citas en
        código. Un perfil no puede apagarlos.
      </p>
      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item.id} className="rounded-md border px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium">{item.title}</span>
              <Badge variant="outline" className="text-[10px]">
                {item.kind === "code" ? "código" : "prompt"}
              </Badge>
            </div>
            <p className="text-muted-foreground mt-1 text-[11px] leading-relaxed">
              {item.description}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A deterministic agent: nothing to configure, and the screen says why.
 * || Un agente determinista: nada que configurar, y la pantalla dice por qué.
 */
function ReadOnlyAgent({
  agent,
  catalog,
}: {
  agent: AgentConfig;
  catalog: ToolCatalogEntry[];
}) {
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
        <ToolPair
          granted={agent.tools}
          used={agent.tools_used ?? []}
          catalog={catalog}
        />
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
  guardrailsMaxChars,
  personaTemplate,
  guardrailsTemplate,
  onSaved,
}: {
  agentKey: string;
  profile: NamedAgentProfile;
  models: ModelConfig[];
  providers: ProviderConfig[];
  personaMaxChars: number;
  guardrailsMaxChars: number;
  personaTemplate: string;
  guardrailsTemplate: string;
  onSaved: (updated: AgentConfig) => void;
}) {
  const effective = profile.effective;
  const [name, setName] = useState(profile.name);
  const [persona, setPersona] = useState(profile.persona ?? "");
  const [guardrails, setGuardrails] = useState(profile.guardrails ?? "");
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
            guardrails: guardrails.trim() || null,
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
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Label htmlFor={`persona-${profile.id}`} className="text-xs">
              Persona
            </Label>
            <div className="flex items-center gap-2">
              {personaTemplate && (
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  onClick={() => setPersona(personaTemplate)}
                >
                  Cargar template
                </Button>
              )}
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
          </div>
          <p className="text-muted-foreground text-[11px] leading-relaxed">
            Cambia la voz, no las cinco reglas. Template: analista funcional senior
            del mercado asegurador, especialista en Visual Time.
          </p>
          <Textarea
            id={`persona-${profile.id}`}
            value={persona}
            onChange={(event) => setPersona(event.target.value)}
            placeholder="p. ej. Respondé como un analista funcional: primero la regla, después el caso borde."
            rows={6}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Label htmlFor={`guardrails-${profile.id}`} className="text-xs">
              Guardrails de operador
            </Label>
            <div className="flex items-center gap-2">
              {guardrailsTemplate && (
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  onClick={() => setGuardrails(guardrailsTemplate)}
                >
                  Cargar template
                </Button>
              )}
              <span
                className={`text-[10px] ${
                  guardrails.length > guardrailsMaxChars
                    ? "text-destructive font-medium"
                    : "text-muted-foreground"
                }`}
              >
                {guardrails.length} / {guardrailsMaxChars}
              </span>
            </div>
          </div>
          <p className="text-muted-foreground text-[11px] leading-relaxed">
            Restricciones extra de negocio. Van después de las cinco reglas y no
            pueden contradecirlas.
          </p>
          <Textarea
            id={`guardrails-${profile.id}`}
            value={guardrails}
            onChange={(event) => setGuardrails(event.target.value)}
            placeholder="p. ej. Si la respuesta toca importes, advertí que el valor exacto depende de la póliza."
            rows={5}
          />
        </div>

        {profile.composed_system_prompt && (
          <details className="rounded-md border">
            <summary className="cursor-pointer px-3 py-2 text-xs font-medium">
              Prompt compuesto de este perfil
            </summary>
            <pre className="bg-muted/40 max-h-80 overflow-auto whitespace-pre-wrap px-3 py-2 font-mono text-[11px] leading-relaxed">
              {profile.composed_system_prompt}
            </pre>
          </details>
        )}

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
            disabled={
              pending ||
              !name.trim() ||
              persona.length > personaMaxChars ||
              guardrails.length > guardrailsMaxChars
            }
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
  guardrailsMaxChars,
  personaTemplate,
  guardrailsTemplate,
  catalog,
  onSaved,
}: {
  agent: AgentConfig;
  models: ModelConfig[];
  providers: ProviderConfig[];
  personaMaxChars: number;
  guardrailsMaxChars: number;
  personaTemplate: string;
  guardrailsTemplate: string;
  catalog: ToolCatalogEntry[];
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
        <ToolPair
          granted={agent.tools}
          used={agent.tools_used ?? []}
          catalog={catalog}
        />
      </div>
      {agent.system_prompt && <SystemPromptBlock prompt={agent.system_prompt} />}
      <SystemGuardrailsList items={agent.system_guardrails ?? []} />
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
          guardrailsMaxChars={guardrailsMaxChars}
          personaTemplate={personaTemplate}
          guardrailsTemplate={guardrailsTemplate}
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
  const catalog = config.tools ?? [];
  const personaTemplate = config.persona_template ?? "";
  const guardrailsTemplate = config.guardrails_template ?? "";
  const guardrailsMaxChars = config.guardrails_max_chars ?? config.persona_max_chars;

  return (
    <div className="flex flex-col gap-8">
      {catalog.length > 0 && (
        <section className="flex flex-col gap-3">
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Tools del grafo</h2>
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
              Lo que la tabla de privilegios concede y lo que cada nodo realmente
              llama. No se asignan desde acá.
            </p>
          </div>
          <Card>
            <CardContent className="flex flex-col gap-3">
              {catalog.map((tool) => (
                <div key={tool.name} className="flex flex-col gap-1">
                  <Badge variant="secondary" className="w-fit font-mono text-[10px]">
                    {tool.name}
                  </Badge>
                  <p className="text-muted-foreground text-xs leading-relaxed">
                    {tool.description}
                  </p>
                  <p className="text-muted-foreground text-[11px]">
                    Concedida a {tool.granted_to.join(", ") || "nadie"} · usada por{" "}
                    {tool.used_by.join(", ") || "nadie"}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>
      )}

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
            guardrailsMaxChars={guardrailsMaxChars}
            personaTemplate={personaTemplate}
            guardrailsTemplate={guardrailsTemplate}
            catalog={catalog}
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
          <ReadOnlyAgent key={agent.key} agent={agent} catalog={catalog} />
        ))}
      </section>
    </div>
  );
}
