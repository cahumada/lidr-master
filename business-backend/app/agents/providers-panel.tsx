"use client";

import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { ModelConfig, ProviderConfig, ServiceConfig } from "@/lib/ai-service/types";

/**
 * Provider management: credentials, availability and the model catalog.
 *
 * The credential field is write-only, and that is not a UI convention — it is
 * what the API allows. Nothing here can display a stored key because no
 * endpoint returns one; what it shows is where the key in force came from
 * (`env` or `stored`) and four characters of it, which is enough to tell two
 * keys apart and not enough to be worth leaking.
 *
 * || Gestión de proveedores: credenciales, disponibilidad y catálogo de
 * modelos. El campo de credencial es write-only, y no es una convención de UI
 * sino lo que permite la API: acá no hay nada que pueda mostrar una clave
 * guardada porque ningún endpoint la devuelve.
 */

function KeyState({ provider }: { provider: ProviderConfig }) {
  if (provider.key_source === "env") {
    return (
      <span className="text-xs text-emerald-600 dark:text-emerald-400">
        clave del entorno (<code>{provider.api_key_setting}</code>)
      </span>
    );
  }
  if (provider.key_source === "stored") {
    return (
      <span className="text-primary text-xs">
        clave guardada y cifrada{" "}
        <code className="text-muted-foreground">{provider.api_key_hint}</code>
      </span>
    );
  }
  return <span className="text-muted-foreground text-xs">sin credencial</span>;
}

function ModelRow({
  model,
  onToggleVisible,
  onToggleTemperature,
  onDelete,
  pending,
}: {
  model: ModelConfig;
  onToggleVisible: () => void;
  onToggleTemperature: () => void;
  onDelete: () => void;
  pending: boolean;
}) {
  return (
    <li className="flex flex-wrap items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs">
      <Switch
        id={`visible-${model.provider}-${model.model}`}
        checked={model.visible}
        disabled={pending}
        onCheckedChange={onToggleVisible}
      />
      <code className={model.visible ? "font-medium" : "text-muted-foreground"}>
        {model.model}
      </code>
      {!model.supports_temperature && (
        <Badge variant="outline" className="text-[10px]">
          sin temperatura
        </Badge>
      )}
      <span className="ml-auto flex items-center gap-2">
        <button
          type="button"
          disabled={pending}
          onClick={onToggleTemperature}
          className="text-muted-foreground hover:text-foreground underline decoration-dotted text-[10px]"
        >
          {model.supports_temperature ? "marcar sin temperatura" : "marcar con temperatura"}
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={onDelete}
          className="text-destructive text-[10px] underline decoration-dotted"
        >
          quitar
        </button>
      </span>
    </li>
  );
}

function ProviderCard({
  provider,
  models,
  storageEnabled,
  onChanged,
}: {
  provider: ProviderConfig;
  models: ModelConfig[];
  storageEnabled: boolean;
  onChanged: () => Promise<void>;
}) {
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(provider.base_url ?? "");
  const [newModel, setNewModel] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showModels, setShowModels] = useState(false);

  async function send(
    path: string,
    method: "PUT" | "POST" | "DELETE",
    body?: unknown,
    onOk?: (data: unknown) => void,
  ) {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(path, {
        method,
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (response.status === 204) {
        onOk?.(null);
        await onChanged();
        return;
      }
      const data = (await response.json()) as { error?: string };
      if (!response.ok) {
        setError(data.error ?? "La operación falló.");
        return;
      }
      onOk?.(data);
      await onChanged();
    } catch {
      setError("No se pudo contactar a la consola.");
    } finally {
      setPending(false);
    }
  }

  const base = `/api/config/providers/${encodeURIComponent(provider.id)}`;
  const visibleCount = models.filter((model) => model.visible).length;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${
              provider.available ? "bg-emerald-500" : "bg-muted-foreground/30"
            }`}
          />
          <h3 className="text-sm font-semibold">{provider.label}</h3>
          <code className="text-muted-foreground text-[10px]">{provider.id}</code>
          <Badge variant="outline" className="text-[10px]">
            {provider.wire_label}
          </Badge>
          <Badge variant="secondary" className="text-[10px]">
            {visibleCount} de {models.length} ofrecidos
          </Badge>
          <span className="ml-auto flex items-center gap-2">
            <Label htmlFor={`enabled-${provider.id}`} className="text-xs">
              Habilitado
            </Label>
            <Switch
              id={`enabled-${provider.id}`}
              checked={provider.enabled}
              disabled={pending}
              onCheckedChange={(checked) => send(base, "PUT", { enabled: checked })}
            />
          </span>
        </div>

        {provider.note && (
          <p className="text-muted-foreground text-xs leading-relaxed">{provider.note}</p>
        )}

        <div className="flex flex-col gap-1.5 rounded-md border p-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <Label className="text-xs">Credencial</Label>
            <KeyState provider={provider} />
          </div>

          {provider.key_source === "env" && (
            <p className="text-muted-foreground text-[10px] leading-relaxed">
              La variable de entorno le gana a una clave guardada, así que guardar una acá
              no tendría efecto mientras <code>{provider.api_key_setting}</code> esté
              definida en el servicio.
            </p>
          )}

          {storageEnabled ? (
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex min-w-56 flex-1 flex-col gap-1">
                <Label htmlFor={`key-${provider.id}`} className="text-[10px]">
                  Clave nueva (se guarda cifrada; no se puede volver a leer)
                </Label>
                <Input
                  id={`key-${provider.id}`}
                  type="password"
                  autoComplete="off"
                  value={apiKey}
                  placeholder="sk-…"
                  disabled={pending}
                  onChange={(event) => setApiKey(event.target.value)}
                />
              </div>
              <Button
                size="sm"
                disabled={pending || apiKey.trim().length < 8}
                onClick={() =>
                  send(`${base}/key`, "PUT", { api_key: apiKey.trim() }, () => setApiKey(""))
                }
              >
                Guardar clave
              </Button>
              {provider.key_source === "stored" && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={pending}
                  onClick={() => send(`${base}/key`, "DELETE")}
                >
                  Olvidar
                </Button>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground text-[10px] leading-relaxed">
              Guardar credenciales está deshabilitado: el servicio no tiene{" "}
              <code>SECRETS_KEY</code>. Generala con{" "}
              <code>uv run python scripts/generate_secrets_key.py</code> y ponela en el
              entorno del servicio, o usá <code>{provider.api_key_setting}</code>.
            </p>
          )}
        </div>

        {provider.wire === "openai_compatible" && (
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex min-w-56 flex-1 flex-col gap-1">
              <Label htmlFor={`base-${provider.id}`} className="text-[10px]">
                Base URL (vacío = el default de OpenAI)
              </Label>
              <Input
                id={`base-${provider.id}`}
                value={baseUrl}
                placeholder="https://api.ejemplo.com/v1"
                disabled={pending}
                onChange={(event) => setBaseUrl(event.target.value)}
              />
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={pending || baseUrl === (provider.base_url ?? "")}
              onClick={() => send(base, "PUT", { base_url: baseUrl })}
            >
              Guardar URL
            </Button>
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertDescription className="text-xs">{error}</AlertDescription>
          </Alert>
        )}
        {notice && (
          <p className="text-xs text-emerald-600 dark:text-emerald-400">{notice}</p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={pending}
            onClick={() => setShowModels((current) => !current)}
          >
            {showModels ? "Ocultar modelos" : `Ver modelos (${models.length})`}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={pending || !provider.available}
            title={
              provider.available
                ? "Le pregunta al proveedor qué modelos sirve"
                : "Necesita una credencial usable"
            }
            onClick={() =>
              send(`${base}/models/refresh`, "POST", {}, (data) => {
                const result = data as { reported?: number; added?: string[] };
                setNotice(
                  `${result.reported ?? 0} modelos reportados, ${
                    result.added?.length ?? 0
                  } nuevos (guardados ocultos: el listado de un proveedor no es un menú curado).`,
                );
              })
            }
          >
            {pending ? "Consultando…" : "Traer del proveedor"}
          </Button>
        </div>

        {showModels && (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex min-w-56 flex-1 flex-col gap-1">
                <Label htmlFor={`new-model-${provider.id}`} className="text-[10px]">
                  Agregar un modelo a mano
                </Label>
                <Input
                  id={`new-model-${provider.id}`}
                  value={newModel}
                  placeholder="nombre exacto del modelo"
                  disabled={pending}
                  onChange={(event) => setNewModel(event.target.value)}
                />
              </div>
              <Button
                size="sm"
                disabled={pending || !newModel.trim()}
                onClick={() =>
                  send(`${base}/models`, "POST", { model: newModel.trim() }, () =>
                    setNewModel(""),
                  )
                }
              >
                Agregar
              </Button>
            </div>
            <ul className="flex max-h-72 flex-col gap-1.5 overflow-y-auto">
              {models.map((model) => (
                <ModelRow
                  key={model.model}
                  model={model}
                  pending={pending}
                  onToggleVisible={() =>
                    send(
                      `${base}/models/${encodeURIComponent(model.model)}`,
                      "PUT",
                      { visible: !model.visible },
                    )
                  }
                  onToggleTemperature={() =>
                    send(
                      `${base}/models/${encodeURIComponent(model.model)}`,
                      "PUT",
                      { supports_temperature: !model.supports_temperature },
                    )
                  }
                  onDelete={() =>
                    send(`${base}/models/${encodeURIComponent(model.model)}`, "DELETE")
                  }
                />
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function ProvidersPanel({
  config,
  onChanged,
}: {
  config: ServiceConfig;
  onChanged: () => Promise<void>;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-semibold tracking-tight">Proveedores</h2>
        <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
          Viven en la base, así que agregar un modelo —o un proveedor entero que hable un
          formato implementado— es una escritura y no un deploy. Un proveedor sin
          credencial usable no se puede elegir: la consola lo deshabilita en vez de dejar
          guardar algo que iba a fallar al responder.
        </p>
        <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
          Las claves guardadas van <strong>cifradas</strong> con una master key que vive
          en el entorno del servicio, y <strong>ningún endpoint las devuelve</strong>: de
          una clave guardada solo se ven cuatro caracteres, para distinguirla de otra. Una
          variable de entorno siempre le gana a una guardada.
        </p>
        <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
          Los <strong>embeddings del corpus no son multi-proveedor</strong>: las 57.101
          filas están en el espacio de <code>text-embedding-3-small</code>, así que
          cambiarlos es reconstruir el corpus, no un setting.
        </p>
      </div>

      {!config.credential_storage_enabled && (
        <Alert>
          <AlertDescription className="text-xs">
            El servicio no tiene <code>SECRETS_KEY</code>, así que guardar credenciales
            está deshabilitado —a propósito no hay un modo &laquo;por ahora en texto
            plano&raquo;, que es cómo un backup termina con claves vivas adentro. Las
            variables de entorno por proveedor siguen funcionando igual.
          </AlertDescription>
        </Alert>
      )}

      {config.providers.map((provider) => (
        <ProviderCard
          key={provider.id}
          provider={provider}
          models={config.models.filter((model) => model.provider === provider.id)}
          storageEnabled={config.credential_storage_enabled}
          onChanged={onChanged}
        />
      ))}
    </section>
  );
}
