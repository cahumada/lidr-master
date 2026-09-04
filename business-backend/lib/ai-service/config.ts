import "server-only";

import { deleteJson, deleteNoContent, getJson, postJson, putJson } from "./base-client";
import type {
  AgentConfig,
  AgentProfileUpdate,
  NamedProfileWrite,
  ModelConfig,
  ModelCreate,
  ModelRefreshResult,
  ModelUpdate,
  ProviderConfig,
  ProviderUpdate,
  ServiceConfig,
} from "./types";

/** Agent-configuration context. Never imports another context.
 * || Contexto de configuración de agentes. Nunca importa otro contexto.
 *
 * On credentials: `setProviderKey` is the only function that sends one, and
 * nothing here reads one back — the service returns a `key_source` and a
 * four-character hint, never the key. A function called `getProviderKey`
 * would have nothing to call.
 * || Sobre credenciales: `setProviderKey` es la única que manda una, y acá no
 * hay nada que las lea de vuelta. Una función `getProviderKey` no tendría a
 * qué llamarle.
 */

/**
 * Asking a provider for its catalog is a network call to THEM, which is
 * slower than the console's usual proxy hop.
 * || Pedirle el catálogo a un proveedor es una llamada de red hacia ELLOS.
 */
const REFRESH_TIMEOUT_MS = 60_000;

export function serviceConfig(): Promise<ServiceConfig> {
  return getJson<ServiceConfig>("/config");
}

export function updateAgentProfile(
  agentKey: string,
  body: AgentProfileUpdate,
): Promise<AgentConfig> {
  return putJson<AgentConfig>(
    `/config/agents/${encodeURIComponent(agentKey)}`,
    body,
  );
}

export function deleteAgentProfile(agentKey: string): Promise<AgentConfig> {
  return deleteJson<AgentConfig>(
    `/config/agents/${encodeURIComponent(agentKey)}`,
  );
}

export function createNamedProfile(
  agentKey: string,
  body: NamedProfileWrite,
): Promise<AgentConfig> {
  return postJson<AgentConfig>(
    `/config/agents/${encodeURIComponent(agentKey)}/profiles`,
    body,
  );
}

export function updateNamedProfile(
  agentKey: string,
  profileId: string,
  body: NamedProfileWrite,
): Promise<AgentConfig> {
  return putJson<AgentConfig>(
    `/config/agents/${encodeURIComponent(agentKey)}/profiles/${encodeURIComponent(profileId)}`,
    body,
  );
}

export function deleteNamedProfile(
  agentKey: string,
  profileId: string,
): Promise<AgentConfig> {
  return deleteJson<AgentConfig>(
    `/config/agents/${encodeURIComponent(agentKey)}/profiles/${encodeURIComponent(profileId)}`,
  );
}

export function updateProvider(
  providerId: string,
  body: ProviderUpdate,
): Promise<ProviderConfig> {
  return putJson<ProviderConfig>(
    `/config/providers/${encodeURIComponent(providerId)}`,
    body,
  );
}

/** Write-only: the service stores it encrypted and never returns it. */
export function setProviderKey(
  providerId: string,
  apiKey: string,
): Promise<ProviderConfig> {
  return putJson<ProviderConfig>(
    `/config/providers/${encodeURIComponent(providerId)}/key`,
    { api_key: apiKey },
  );
}

export function clearProviderKey(
  providerId: string,
): Promise<ProviderConfig> {
  return deleteJson<ProviderConfig>(
    `/config/providers/${encodeURIComponent(providerId)}/key`,
  );
}

export function addProviderModel(
  providerId: string,
  body: ModelCreate,
): Promise<ModelConfig> {
  return postJson<ModelConfig>(
    `/config/providers/${encodeURIComponent(providerId)}/models`,
    body,
  );
}

export function updateProviderModel(
  providerId: string,
  model: string,
  body: ModelUpdate,
): Promise<ModelConfig> {
  return putJson<ModelConfig>(
    `/config/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(model)}`,
    body,
  );
}

export function deleteProviderModel(
  providerId: string,
  model: string,
): Promise<void> {
  return deleteNoContent(
    `/config/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(model)}`,
  );
}

export function refreshProviderModels(
  providerId: string,
): Promise<ModelRefreshResult> {
  return postJson<ModelRefreshResult>(
    `/config/providers/${encodeURIComponent(providerId)}/models/refresh`,
    {},
    REFRESH_TIMEOUT_MS,
  );
}
