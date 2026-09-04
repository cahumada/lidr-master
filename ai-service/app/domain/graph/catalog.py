"""What each agent of the answer graph is, declared once.

The course declares this catalog **twice**: once as the Python graph and again
as `Agents::GraphFlow::NODES` in the Rails app, which is what lets the two
drift — a node renamed in the graph keeps its old label in the console until
somebody notices. Here the catalog lives next to the graph and the web console
reads it over `GET /config`, so there is one place to change.

`tools` is derived from ``AGENT_PRIVILEGES`` rather than repeated, for the same
reason: the privilege table is what the dispatcher actually enforces, and a
catalog that disagreed with it would be documentation that lies.

|| Qué es cada agente del grafo de respuesta, declarado una sola vez. El curso
declara este catálogo DOS veces —el grafo en Python y `Agents::GraphFlow::NODES`
en la app Rails— y eso es lo que les permite divergir. Acá el catálogo vive al
lado del grafo y la consola lo lee por `GET /config`.

`tools` se deriva de ``AGENT_PRIVILEGES`` en vez de repetirse: la tabla de
privilegios es lo que el dispatcher realmente aplica, y un catálogo que la
contradijera sería documentación que miente.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.graph.privilege import allowed_tools

# Only ONE agent calls a model today. That is a design decision, not an
# oversight: `query_planner` splits with `decompose()`, `citation_validator`
# runs `check_grounding`, and both are deterministic so the measured evals stay
# reproducible. The course makes almost every node LLM-driven, which is why
# per-node model and persona mean something in five nodes there and in one
# here. `llm_driven` says which is which instead of pretending they are alike.
# || Hoy un SOLO agente llama a un modelo. Es una decisión de diseño, no un
# descuido: `query_planner` parte con `decompose()` y `citation_validator` corre
# `check_grounding`, los dos deterministas, así los evals medidos siguen siendo
# reproducibles. El curso hace LLM-driven a casi todos los nodos, y por eso allá
# modelo y persona por nodo significan algo en cinco nodos y acá en uno.


@dataclass(frozen=True)
class AgentSpec:
    """One node of the answer graph, as the console shows it.

    || Un nodo del grafo de respuesta, como lo muestra la consola.
    """

    key: str
    label: str
    role: str
    explanation: str
    kind: str
    llm_driven: bool
    config_source: str | None

    @property
    def tools(self) -> list[str]:
        """Tools this agent may call, from the privilege table.

        || Herramientas que este agente puede llamar, de la tabla de privilegios.
        """
        return sorted(allowed_tools(self.key))


AGENT_SPECS: tuple[AgentSpec, ...] = (
    AgentSpec(
        key="orchestrator",
        label="Orquestador",
        role="Decide qué especialista actúa en cada paso.",
        explanation=(
            "Enruta con `Command(goto=...)` en vez de un orden fijo, con tres frenos "
            "deterministas: tope de pasos, guarda de legalidad (rechaza un destino cuyos "
            "inputs no están listos o que ya corrió) y escalera de fallback."
        ),
        kind="supervisor",
        llm_driven=False,
        config_source="ANSWER_ORCHESTRATOR_MAX_STEPS",
    ),
    AgentSpec(
        key="query_planner",
        label="Planificador de consulta",
        role="Parte preguntas compuestas y sugiere filtros.",
        explanation=(
            "Determinista: `decompose()` para las subconsultas y una heurística sobre "
            "tokens con forma de transacción para sugerir `module_code`. Sin LLM, así el "
            "mismo texto produce siempre el mismo plan."
        ),
        kind="agent",
        llm_driven=False,
        config_source=None,
    ),
    AgentSpec(
        key="evidence_retriever",
        label="Recuperación de evidencia",
        role="Recupera del corpus con el pipeline medido.",
        explanation=(
            "El único agente con una tool: `search_corpus`, que envuelve el mismo "
            "`HybridRetriever.retrieve` que usan `/search` y `/answer` — sin una segunda "
            "implementación de recuperación."
        ),
        kind="agent",
        llm_driven=False,
        config_source="RERANK_MODEL",
    ),
    AgentSpec(
        key="answer_synthesizer",
        label="Síntesis de respuesta",
        role="Redacta la respuesta citada a partir de la evidencia.",
        explanation=(
            "El único agente que llama a un modelo: arma el prompt versionado con la "
            "procedencia de cada chunk visible y completa. Su `persona` se appendea al "
            "system prompt, y su modelo, temperatura y tope de tokens se pueden "
            "sobreescribir por perfil."
        ),
        kind="agent",
        llm_driven=True,
        config_source="ANSWER_MODEL",
    ),
    AgentSpec(
        key="citation_validator",
        label="Validación de citas",
        role="Verifica que cada cita tenga respaldo en los hits.",
        explanation=(
            "Determinista: corre `check_grounding` como paso formal del grafo y puede "
            "pedir UN requery con una consulta refinada. Sin LLM: 'esta respuesta está "
            "respaldada' tiene que ser reproducible y testeable."
        ),
        kind="agent",
        llm_driven=False,
        config_source="ANSWER_ORCHESTRATOR_MAX_REQUERIES",
    ),
    AgentSpec(
        key="answer_review_gate",
        label="Gate de revisión",
        role="Pausa para una persona solo cuando hay señal.",
        explanation=(
            "`review_reasons(state)` es una función pura del estado: confianza bajo el "
            "umbral, una cita sin respaldo, o cero evidencia. Sin disparadores no pausa "
            "— un gate que siempre pausa es un formulario, no un control."
        ),
        kind="gate",
        llm_driven=False,
        config_source="ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD",
    ),
)

# The one agent whose profile has an effect today, named once so the two
# synthesis entry points cannot disagree about which key to read.
# || El único agente cuyo perfil tiene efecto hoy, nombrado una vez para que
# los dos puntos de entrada de síntesis no discrepen sobre qué clave leer.
SYNTHESIZER_AGENT = "answer_synthesizer"

AGENT_KEYS: tuple[str, ...] = tuple(spec.key for spec in AGENT_SPECS)

_BY_KEY = {spec.key: spec for spec in AGENT_SPECS}


def agent_spec(key: str) -> AgentSpec | None:
    """The spec for ``key``, or ``None`` if no such agent exists.

    || El spec de ``key``, o ``None`` si no existe ese agente.
    """
    return _BY_KEY.get(key)


def graph_flow() -> dict:
    """Topology the console draws, derived from the graph that actually runs.

    Nodes come from this catalog; edges and the fallback ladder come from
    ``build.py`` and the orchestrator, so a screen cannot invent a connector
    the compiled graph does not have.

    || Topología que dibuja la consola, derivada del grafo que realmente corre.
    Los nodos salen de este catálogo; las aristas y la escalera, de ``build.py``
    y del orquestador.
    """
    from app.domain.graph.build import AGENT_NODES
    from app.domain.graph.orchestrator import FALLBACK_LADDER

    nodes = [
        {
            "key": spec.key,
            "label": spec.label,
            "kind": spec.kind,
            "role": spec.role,
            "explanation": spec.explanation,
            "llm_driven": spec.llm_driven,
            "tools": spec.tools,
        }
        for spec in AGENT_SPECS
    ]
    edges = [{"source": "START", "target": "orchestrator"}]
    for name in AGENT_NODES:
        edges.append({"source": "orchestrator", "target": name})
        edges.append({"source": name, "target": "orchestrator"})
    edges.append({"source": "orchestrator", "target": "answer_review_gate"})
    edges.append({"source": "answer_review_gate", "target": "END"})
    return {"nodes": nodes, "edges": edges, "ladder": list(FALLBACK_LADDER)}


def configurable_agent_keys() -> tuple[str, ...]:
    """Agents whose model and persona actually change behaviour.

    Persisting a persona for a deterministic agent would be a setting that
    does nothing — the write is rejected instead of accepted and ignored.

    || Agentes cuyo modelo y persona realmente cambian el comportamiento.
    Persistir una persona para un agente determinista sería un setting que no
    hace nada — la escritura se rechaza en vez de aceptarse y no tener efecto.
    """
    return tuple(spec.key for spec in AGENT_SPECS if spec.llm_driven)
