import "server-only";

import { deleteJson, getJson, putJson } from "./base-client";
import type {
  AgentConfig,
  AgentProfileUpdate,
  ServiceConfig,
} from "./types";

/** Agent-configuration context. Never imports another context.
 * || Contexto de configuración de agentes. Nunca importa otro contexto.
 */

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
