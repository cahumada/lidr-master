"use client";

import { useState, type ReactNode } from "react";
import { Plus } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
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

const NEW_PROFILE = "new";

function firstConfigurableKey(agents: AgentConfig[]): string {
  return agents.find((agent) => agent.configurable)?.key ?? agents[0]?.key ?? "";
}

function initialProfileTab(agent: AgentConfig | undefined): string {
  if (!agent?.configurable) return "";
  const preferred = agent.profiles.find((profile) => profile.is_default) ?? agent.profiles[0];
  return preferred?.id ?? NEW_PROFILE;
}

function KindBadge({ kind }: { kind: string }) {
  return <Badge variant="outline">{KIND_LABEL[kind] ?? kind}</Badge>;
}

function SourceNote({ source }: { source: string }) {
  if (source === "profile") {
    return <span className="text-primary text-xs font-medium">viene del perfil</span>;
  }
  if (source === "unset") {
    return <span className="text-muted-foreground text-xs">sin definir</span>;
  }
  return <span className="text-muted-foreground text-xs">default del servicio</span>;
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
    return <p className="text-muted-foreground text-sm">{empty}</p>;
  }
  return (
    <ul className="flex flex-col gap-3">
      {names.map((name) => (
        <li key={name} className="flex flex-col gap-1">
          <Badge variant="secondary" className="w-fit font-mono text-xs">
            {name}
          </Badge>
          {toolDescription(catalog, name) && (
            <p className="text-muted-foreground text-xs leading-relaxed">
              {toolDescription(catalog, name)}
            </p>
          )}
        </li>
      ))}
    </ul>
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
    <div className="grid gap-6 sm:grid-cols-2">
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">Disponibles</h3>
        <p className="text-muted-foreground text-xs leading-relaxed">
          Lo que la tabla de privilegios le concede. No se asignan desde acá.
        </p>
        <ToolChips names={granted} catalog={catalog} empty="Ninguna concedida." />
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">Utilizadas</h3>
        <p className="text-muted-foreground text-xs leading-relaxed">
          Las que este nodo llama de verdad en una corrida.
        </p>
        <ToolChips names={used} catalog={catalog} empty="Ninguna." />
      </div>
    </div>
  );
}

function ReadOnlyBlock({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <details className="rounded-xl border">
      <summary className="cursor-pointer px-4 py-3 text-sm font-medium">{title}</summary>
      <div className="border-t px-4 py-3">{children}</div>
    </details>
  );
}

function SystemPromptBlock({ prompt }: { prompt: string }) {
  return (
    <ReadOnlyBlock title="System prompt (solo lectura)">
      <pre className="bg-muted/40 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg p-3 font-mono text-xs leading-relaxed">
        {prompt}
      </pre>
    </ReadOnlyBlock>
  );
}

function SystemGuardrailsList({ items }: { items: SystemGuardrail[] }) {
  if (items.length === 0) return null;
  return (
    <ReadOnlyBlock title="Guardrails de sistema (no se editan)">
      <p className="text-muted-foreground mb-3 text-xs leading-relaxed">
        Son las cinco reglas del prompt más el chequeo de citas en código. Un
        perfil no puede apagarlos.
      </p>
      <ul className="flex flex-col gap-3">
        {items.map((item) => (
          <li key={item.id} className="rounded-lg border px-3 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{item.title}</span>
              <Badge variant="outline">
                {item.kind === "code" ? "código" : "prompt"}
              </Badge>
            </div>
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
              {item.description}
            </p>
          </li>
        ))}
      </ul>
    </ReadOnlyBlock>
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
      className="border-input bg-background h-8 w-full rounded-lg border px-2.5 text-sm"
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

function CharCount({ current, max }: { current: number; max: number }) {
  return (
    <span
      className={cn(
        "text-xs",
        current > max ? "text-destructive font-medium" : "text-muted-foreground",
      )}
    >
      {current} / {max}
    </span>
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
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const picked = pair ? splitPair(pair) : null;
  const pickedModel = picked
    ? models.find((m) => m.provider === picked.provider && m.model === picked.model)
    : undefined;
  const acceptsTemperature = pickedModel
    ? pickedModel.supports_temperature
    : effective.supports_temperature;
  const overLimit =
    persona.length > personaMaxChars || guardrails.length > guardrailsMaxChars;

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
      setConfirmingDelete(false);
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
      <CardHeader className="border-b">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>{profile.name}</CardTitle>
          {profile.is_default && <Badge>default del chat</Badge>}
        </div>
        <CardDescription>
          Un campo vacío usa el default del servicio, no deja el valor en
          blanco. Los cambios se aplican en la próxima consulta.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-8 pt-6">
        {effective && !effective.provider_available && (
          <Alert variant="destructive">
            <AlertDescription>
              El proveedor vigente (<strong>{effective.provider}</strong>) no
              tiene clave configurada en el servicio.
            </AlertDescription>
          </Alert>
        )}

        <section className="flex flex-col gap-3">
          <div>
            <h3 className="text-sm font-semibold">Identidad</h3>
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
              Cómo aparece este perfil en el chat y en esta lista.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={`name-${profile.id}`}>Nombre</Label>
            <Input
              id={`name-${profile.id}`}
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={64}
            />
          </div>
        </section>

        <Separator />

        <section className="flex flex-col gap-3">
          <div>
            <h3 className="text-sm font-semibold">Voz</h3>
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
              Cambia el tono, no las cinco reglas de anclaje. Template: analista
              funcional senior del mercado asegurador, especialista en Visual
              Time.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Label htmlFor={`persona-${profile.id}`}>Persona</Label>
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
                <CharCount current={persona.length} max={personaMaxChars} />
              </div>
            </div>
            <Textarea
              id={`persona-${profile.id}`}
              value={persona}
              onChange={(event) => setPersona(event.target.value)}
              placeholder="p. ej. Respondé como un analista funcional: primero la regla, después el caso borde."
              rows={7}
            />
            <SourceNote source={effective.sources.persona} />
          </div>
        </section>

        <Separator />

        <section className="flex flex-col gap-3">
          <div>
            <h3 className="text-sm font-semibold">Reglas extra</h3>
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
              Restricciones de negocio. Van después de las cinco reglas y no
              pueden contradecirlas.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Label htmlFor={`guardrails-${profile.id}`}>Guardrails de operador</Label>
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
                <CharCount current={guardrails.length} max={guardrailsMaxChars} />
              </div>
            </div>
            <Textarea
              id={`guardrails-${profile.id}`}
              value={guardrails}
              onChange={(event) => setGuardrails(event.target.value)}
              placeholder="p. ej. Si la respuesta toca importes, advertí que el valor exacto depende de la póliza."
              rows={5}
            />
            <SourceNote source={effective.sources.guardrails ?? "unset"} />
          </div>
        </section>

        <Separator />

        <section className="flex flex-col gap-3">
          <div>
            <h3 className="text-sm font-semibold">Modelo</h3>
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
              Vacío = el default del servicio. Los proveedores se cargan en
              Modelos.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor={`model-${profile.id}`}>Modelo</Label>
              <ModelSelect
                id={`model-${profile.id}`}
                pair={pair}
                onChange={setPair}
                models={models}
                providers={providers}
              />
              <p className="font-mono text-xs">
                Vigente: {effective.model} · <SourceNote source={effective.sources.model} />
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor={`temperature-${profile.id}`}>Temperatura</Label>
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
              <p className="font-mono text-xs">
                Vigente: {effective.temperature === null ? "—" : effective.temperature} ·{" "}
                <SourceNote source={effective.sources.temperature} />
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor={`max-tokens-${profile.id}`}>Tope de tokens</Label>
              <Input
                id={`max-tokens-${profile.id}`}
                type="number"
                min={1}
                max={8192}
                value={maxTokens}
                placeholder="default"
                onChange={(event) => setMaxTokens(event.target.value)}
              />
              <p className="font-mono text-xs">
                Vigente: {effective.max_tokens} ·{" "}
                <SourceNote source={effective.sources.max_tokens} />
              </p>
            </div>
          </div>
        </section>

        {profile.composed_system_prompt && (
          <ReadOnlyBlock title="Prompt compuesto de este perfil">
            <pre className="bg-muted/40 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg p-3 font-mono text-xs leading-relaxed">
              {profile.composed_system_prompt}
            </pre>
          </ReadOnlyBlock>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {saved && !error && (
          <p className="text-sm text-emerald-600 dark:text-emerald-400">
            Guardado. Se aplica en la próxima consulta si este perfil es el
            default o si lo elegís en el chat.
          </p>
        )}
      </CardContent>

      <CardFooter className="justify-end gap-2">
        {confirmingDelete ? (
          <>
            <p className="text-destructive mr-auto text-sm">¿Borrar este perfil?</p>
            <Button
              variant="outline"
              disabled={pending}
              onClick={() => setConfirmingDelete(false)}
            >
              Cancelar
            </Button>
            <Button variant="destructive" disabled={pending} onClick={() => void remove()}>
              Sí, borrar
            </Button>
          </>
        ) : (
          <>
            <Button
              variant="outline"
              disabled={pending}
              onClick={() => setConfirmingDelete(true)}
            >
              Borrar
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
            <Button
              disabled={pending || !name.trim() || overLimit}
              onClick={() => void save()}
            >
              {pending ? "Guardando…" : "Guardar"}
            </Button>
          </>
        )}
      </CardFooter>
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
      <CardHeader className="border-b">
        <CardTitle>Nuevo perfil</CardTitle>
        <CardDescription>
          Un nombre, como en el curso: <em>Conservador</em>, <em>Exhaustivo</em>.
          La persona y el modelo se editan después de crearlo.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 pt-6">
        <div className="flex flex-col gap-2">
          <Label htmlFor={`new-name-${agentKey}`}>Nombre</Label>
          <Input
            id={`new-name-${agentKey}`}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="p. ej. Conservador"
            maxLength={64}
          />
        </div>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </CardContent>
      <CardFooter className="justify-end">
        <Button disabled={pending || !name.trim()} onClick={() => void create()}>
          {pending ? "Creando…" : "Crear perfil"}
        </Button>
      </CardFooter>
    </Card>
  );
}

function AgentIdentity({ agent }: { agent: AgentConfig }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold tracking-tight">{agent.label}</h2>
        <KindBadge kind={agent.kind} />
        {agent.configurable ? (
          <Badge>llama a un modelo</Badge>
        ) : (
          <Badge variant="secondary">determinista</Badge>
        )}
      </div>
      <p className="text-base leading-relaxed">{agent.role}</p>
      <p className="text-muted-foreground text-sm leading-relaxed">{agent.explanation}</p>
    </div>
  );
}

function AgentNav({
  agents,
  selectedKey,
  onSelect,
}: {
  agents: AgentConfig[];
  selectedKey: string;
  onSelect: (key: string) => void;
}) {
  const editable = agents.filter((agent) => agent.configurable);
  const readOnly = agents.filter((agent) => !agent.configurable);

  function group(title: string, items: AgentConfig[], hint: string) {
    if (items.length === 0) return null;
    return (
      <div className="flex flex-col gap-2">
        <div>
          <p className="text-xs font-medium tracking-wide uppercase">{title}</p>
          <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">{hint}</p>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible">
          {items.map((agent) => {
            const selected = agent.key === selectedKey;
            return (
              <button
                key={agent.key}
                type="button"
                aria-current={selected ? "true" : undefined}
                onClick={() => onSelect(agent.key)}
                className={cn(
                  "min-w-44 shrink-0 rounded-xl border px-3 py-2.5 text-left transition-colors lg:min-w-0 lg:w-full",
                  selected
                    ? "border-foreground/15 bg-muted"
                    : "border-transparent hover:bg-muted/60",
                )}
              >
                <span className="block text-sm font-medium">{agent.label}</span>
                <span className="text-muted-foreground mt-0.5 line-clamp-2 block text-xs leading-relaxed">
                  {agent.role}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <nav
      aria-label="Agentes del grafo"
      className="flex flex-col gap-6 lg:sticky lg:top-4"
    >
      {group("Se configura", editable, "Llama a un modelo. Acá se editan los perfiles.")}
      {group("Solo se lee", readOnly, "Corren en código. No tienen persona ni modelo.")}
    </nav>
  );
}

function ConfigurableWorkspace({
  agent,
  models,
  providers,
  personaMaxChars,
  guardrailsMaxChars,
  personaTemplate,
  guardrailsTemplate,
  catalog,
  profileTab,
  onProfileTab,
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
  profileTab: string;
  onProfileTab: (id: string) => void;
  onSaved: (previous: AgentConfig, updated: AgentConfig) => void;
}) {
  const selected = agent.profiles.find((profile) => profile.id === profileTab);

  return (
    <div className="flex flex-col gap-8">
      <AgentIdentity agent={agent} />
      <ToolPair granted={agent.tools} used={agent.tools_used ?? []} catalog={catalog} />

      <div className="flex flex-col gap-3">
        {agent.system_prompt && <SystemPromptBlock prompt={agent.system_prompt} />}
        <SystemGuardrailsList items={agent.system_guardrails ?? []} />
      </div>

      <section className="flex flex-col gap-4">
        <div>
          <h3 className="text-sm font-semibold">Perfiles</h3>
          <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
            El default se usa cuando el chat no elige otro. Creá uno, después
            editá voz, reglas y modelo.
          </p>
        </div>
        <div
          role="tablist"
          aria-label="Perfiles del agente"
          className="flex flex-wrap gap-2"
        >
          {agent.profiles.map((profile) => {
            const selectedTab = profile.id === profileTab;
            return (
              <Button
                key={profile.id}
                type="button"
                role="tab"
                aria-selected={selectedTab}
                variant={selectedTab ? "default" : "outline"}
                onClick={() => onProfileTab(profile.id)}
              >
                {profile.name}
                {profile.is_default ? " · default" : ""}
              </Button>
            );
          })}
          <Button
            type="button"
            role="tab"
            aria-selected={profileTab === NEW_PROFILE}
            variant={profileTab === NEW_PROFILE ? "default" : "outline"}
            onClick={() => onProfileTab(NEW_PROFILE)}
          >
            <Plus data-icon="inline-start" />
            Nuevo perfil
          </Button>
        </div>

        {profileTab === NEW_PROFILE && (
          <CreateProfileForm
            agentKey={agent.key}
            onSaved={(updated) => onSaved(agent, updated)}
          />
        )}
        {selected && (
          <NamedProfileCard
            key={selected.id}
            agentKey={agent.key}
            profile={selected}
            models={models}
            providers={providers}
            personaMaxChars={personaMaxChars}
            guardrailsMaxChars={guardrailsMaxChars}
            personaTemplate={personaTemplate}
            guardrailsTemplate={guardrailsTemplate}
            onSaved={(updated) => onSaved(agent, updated)}
          />
        )}
      </section>
    </div>
  );
}

function ReadOnlyWorkspace({
  agent,
  catalog,
}: {
  agent: AgentConfig;
  catalog: ToolCatalogEntry[];
}) {
  return (
    <Card>
      <CardHeader className="border-b">
        <AgentIdentity agent={agent} />
      </CardHeader>
      <CardContent className="flex flex-col gap-6 pt-6">
        <ToolPair granted={agent.tools} used={agent.tools_used ?? []} catalog={catalog} />
        <p className="text-muted-foreground text-sm leading-relaxed">
          Determinista: no llama a ningún modelo, así que no tiene persona ni
          modelo que configurar.
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

function ToolsCatalog({ catalog }: { catalog: ToolCatalogEntry[] }) {
  if (catalog.length === 0) return null;
  return (
    <ReadOnlyBlock title="Catálogo de tools (referencia)">
      <p className="text-muted-foreground mb-4 text-sm leading-relaxed">
        Lo que la tabla de privilegios concede y lo que cada nodo realmente
        llama. No se asignan desde acá.
      </p>
      <ul className="flex flex-col gap-4">
        {catalog.map((tool) => (
          <li key={tool.name} className="flex flex-col gap-1">
            <Badge variant="secondary" className="w-fit font-mono text-xs">
              {tool.name}
            </Badge>
            <p className="text-muted-foreground text-sm leading-relaxed">
              {tool.description}
            </p>
            <p className="text-muted-foreground text-xs">
              Concedida a {tool.granted_to.join(", ") || "nadie"} · usada por{" "}
              {tool.used_by.join(", ") || "nadie"}
            </p>
          </li>
        ))}
      </ul>
    </ReadOnlyBlock>
  );
}

export function AgentsConsole({ initialConfig }: { initialConfig: ServiceConfig }) {
  const [config, setConfig] = useState(initialConfig);
  const [selectedKey, setSelectedKey] = useState(() =>
    firstConfigurableKey(initialConfig.agents),
  );
  const [profileTab, setProfileTab] = useState(() =>
    initialProfileTab(
      initialConfig.agents.find(
        (agent) => agent.key === firstConfigurableKey(initialConfig.agents),
      ),
    ),
  );

  function replaceAgent(updated: AgentConfig) {
    setConfig((current) => ({
      ...current,
      agents: current.agents.map((agent) =>
        agent.key === updated.key ? updated : agent,
      ),
    }));
  }

  function selectAgent(key: string) {
    setSelectedKey(key);
    const agent = config.agents.find((item) => item.key === key);
    setProfileTab(initialProfileTab(agent));
  }

  function handleSaved(previous: AgentConfig, updated: AgentConfig) {
    replaceAgent(updated);
    const created = updated.profiles.find(
      (profile) => !previous.profiles.some((item) => item.id === profile.id),
    );
    if (created) {
      setProfileTab(created.id);
      return;
    }
    if (profileTab !== NEW_PROFILE && !updated.profiles.some((item) => item.id === profileTab)) {
      setProfileTab(initialProfileTab(updated));
    }
  }

  if (config.agents.length === 0) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          No se pudo leer el catálogo del servicio IA. Con el servicio apagado
          esta pantalla no tiene qué mostrar: el catálogo vive ahí, no acá.
        </AlertDescription>
      </Alert>
    );
  }

  const selected =
    config.agents.find((agent) => agent.key === selectedKey) ?? config.agents[0];
  const catalog = config.tools ?? [];
  const personaTemplate = config.persona_template ?? "";
  const guardrailsTemplate = config.guardrails_template ?? "";
  const guardrailsMaxChars = config.guardrails_max_chars ?? config.persona_max_chars;

  return (
    <div className="flex flex-col gap-8">
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(16rem,18rem)_minmax(0,1fr)]">
        <AgentNav
          agents={config.agents}
          selectedKey={selected.key}
          onSelect={selectAgent}
        />
        <div>
          {selected.configurable ? (
            <ConfigurableWorkspace
              agent={selected}
              models={config.models}
              providers={config.providers}
              personaMaxChars={config.persona_max_chars}
              guardrailsMaxChars={guardrailsMaxChars}
              personaTemplate={personaTemplate}
              guardrailsTemplate={guardrailsTemplate}
              catalog={catalog}
              profileTab={profileTab}
              onProfileTab={setProfileTab}
              onSaved={handleSaved}
            />
          ) : (
            <ReadOnlyWorkspace agent={selected} catalog={catalog} />
          )}
        </div>
      </div>
      <ToolsCatalog catalog={catalog} />
    </div>
  );
}
