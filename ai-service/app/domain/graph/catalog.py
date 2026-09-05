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

from app.domain.graph.privilege import AGENT_PRIVILEGES, SEARCH_CORPUS_TOOL, allowed_tools

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


# One real user question, walked through every node so the console can show
# what each one does instead of only what it is. It comes from the curated
# golden set — questions a user actually asked, annotated by someone who knows
# the business — because a made-up example would be the only prose in the
# console that is not backed by data. It is compound on purpose: it exercises
# `decompose()`, so the planner and the retriever have something visible to do.
# || Una pregunta real de usuario, recorrida por todos los nodos para que la
# consola muestre qué hace cada uno y no solo qué es. Sale del golden curado
# —preguntas que un usuario hizo, anotadas por alguien que conoce el negocio—
# porque un ejemplo inventado sería la única prosa de la consola sin un dato
# atrás. Es compuesta a propósito: ejercita `decompose()`.
EXAMPLE_QUESTION = (
    "Si un lote de cobranza PAC tiene problemas de pago, ¿cómo se originan esos "
    "boletines en el sistema, cómo puedo registrar sus rechazos (manual o "
    "automáticamente) y en qué pantalla valido el monto neto que realmente se va "
    "a notificar como cobrado?"
)
EXAMPLE_SOURCE = "evals/golden_curated.json · U-multi-lote-pac-rechazos"
EXAMPLE_NOTE = (
    "Pregunta real de un usuario, con sus documentos anotados por alguien que "
    "conoce el negocio. Compuesta: se parte en tres sub-preguntas, así que los "
    "seis nodos tienen algo que hacer con ella."
)

# The sub-queries `decompose()` produces for EXAMPLE_QUESTION, written out so
# the console can show them verbatim. A test asserts they are still what the
# function returns — an example the code no longer produces has to fail in CI,
# not sit on a screen looking authoritative.
# || Las subconsultas que `decompose()` produce para EXAMPLE_QUESTION, escritas
# para que la consola las muestre tal cual. Un test afirma que siguen siendo lo
# que la función devuelve.
EXAMPLE_SUB_QUERIES: tuple[str, ...] = (
    (
        "Si un lote de cobranza PAC tiene problemas de pago, cómo se originan esos "
        "boletines en el sistema?"
    ),
    (
        "Si un lote de cobranza PAC tiene problemas de pago, cómo puedo registrar sus "
        "rechazos (manual o automáticamente)?"
    ),
    (
        "Si un lote de cobranza PAC tiene problemas de pago, en qué pantalla valido el "
        "monto neto que realmente se va a notificar como cobrado?"
    ),
)


@dataclass(frozen=True)
class NodeExample:
    """What one node receives and leaves for ``EXAMPLE_QUESTION``.

    ``caveat`` is not decoration: it separates what the code deterministically
    produces from what only illustrates it. The synthesizer's text depends on
    the model, and the retrieved documents depend on the loaded corpus — saying
    so on the screen costs one line and keeps the example from reading as a
    recorded run.

    || Qué recibe y qué deja un nodo para ``EXAMPLE_QUESTION``. ``caveat``
    separa lo que el código produce de forma determinista de lo que solo lo
    ilustra.
    """

    receives: str
    leaves: str
    detail: tuple[str, ...] = ()
    caveat: str | None = None


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
    example: NodeExample
    # Tools this node actually calls. Distinct from `tools` (the grant).
    # || Tools que este nodo llama de verdad. Distinto de `tools` (la concesión).
    tools_used: tuple[str, ...] = ()

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
        example=NodeExample(
            receives=(
                "El estado de la corrida: la pregunta entera en `query`, `supervisor_steps` "
                "en 0, todavía sin `sub_queries` ni `hits`."
            ),
            leaves=(
                "`Command(goto=\"query_planner\")`: el primer agente de la escalera cuyas "
                "precondiciones se cumplen (hay `query`) y que todavía no corrió. Vuelve a "
                "decidir después de cada especialista, así que en esta pregunta actúa "
                "cinco veces: cuatro para despachar y una para cerrar."
            ),
            detail=(
                "paso 0 → query_planner",
                "paso 1 → evidence_retriever",
                "paso 2 → answer_synthesizer",
                "paso 3 → citation_validator",
                "paso 4 → answer_review_gate (ninguno puede volver a actuar)",
            ),
        ),
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
        example=NodeExample(
            receives="La pregunta entera, sin tocar.",
            leaves=(
                "Tres subconsultas: `decompose()` encuentra tres cláusulas coordinadas, "
                "cada una con su propio interrogativo, y le pega a cada una el contexto "
                "(«Si un lote de cobranza PAC…») para que no pierda las entidades. Y "
                "`filters` vacío: ningún token tiene forma de transacción — `PAC` son "
                "letras sin dígito, así que no propone `module_code`."
            ),
            detail=EXAMPLE_SUB_QUERIES,
        ),
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
        tools_used=(SEARCH_CORPUS_TOOL,),
        example=NodeExample(
            receives="Las tres subconsultas del planificador, más sus filtros (acá, ninguno).",
            leaves=(
                "Una llamada a `search_corpus` por subconsulta —el mismo "
                "`HybridRetriever.retrieve` de `/search`— y los hits unidos, deduplicados "
                "por `content_hash`. Tres búsquedas angostas en vez de una ancha: el "
                "motivo está medido, la consulta compuesta entierra el documento que la "
                "responde."
            ),
            detail=(
                "COL500 — boletines generados agrupando recibos con vía de pago PAC",
                "CO501 — marcación manual de un boletín rechazado",
                "COL704 — carga masiva del archivo plano de rechazos del banco",
                "COL520 — resumen del lote para validar la cifra neta",
            ),
            caveat=(
                "Los cuatro documentos son los que una persona anotó como relevantes en el "
                "golden set, no la salida de una corrida: lo que recupera depende del "
                "corpus cargado."
            ),
        ),
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
        example=NodeExample(
            receives=(
                "La pregunta y los chunks recuperados, cada uno con su procedencia visible "
                "en el prompt: documento, sección, ruta de bullets y título."
            ),
            leaves=(
                "Una respuesta con una parte por sub-pregunta, y cada afirmación citando el "
                "documento del que salió, con el formato exacto que exige el system "
                "prompt."
            ),
            detail=(
                (
                    "Los boletines se generan agrupando los recibos con vía de pago PAC "
                    "[COL500 · sección]; los rechazos se marcan uno a uno "
                    "[CO501 · sección] o se cargan por archivo plano del banco "
                    "[COL704 · sección]."
                ),
            ),
            caveat=(
                "Es el único nodo que llama a un modelo: el texto exacto cambia con el "
                "modelo, la temperatura y la persona del perfil. Este es un ejemplo "
                "ilustrativo del formato, no una respuesta grabada."
            ),
        ),
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
        example=NodeExample(
            receives="La respuesta redactada y los hits que deberían sostenerla.",
            leaves=(
                "`check_grounding` compara cada documento citado en la prosa contra los "
                "hits. Con los cuatro respaldados: `citations_valid=true` y "
                "`confidence=0.9` — el valor que da estar grounded con tres hits o más. "
                "Si un documento citado no estuviera entre los hits, pediría UN requery "
                "con la consulta refinada en vez de aprobar."
            ),
        ),
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
        example=NodeExample(
            receives="`confidence=0.9`, `citations_valid=true`, cuatro hits.",
            leaves=(
                "`review_reasons()` vuelve vacía —0.90 está sobre el umbral por defecto de "
                "0.60, no hay citas sin respaldo y hay evidencia— así que no pausa y la "
                "respuesta se entrega. Con la confianza bajo el umbral, o una cita sin "
                "respaldo, `interrupt()` detendría la corrida para que la mire una "
                "persona."
            ),
        ),
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
    the compiled graph does not have. ``example`` travels with them so the
    console can show what each node *does* with one real question instead of
    only what it is.

    || Topología que dibuja la consola, derivada del grafo que realmente corre.
    Los nodos salen de este catálogo; las aristas y la escalera, de ``build.py``
    y del orquestador. ``example`` viaja con ellos para que la consola muestre
    qué *hace* cada nodo con una pregunta real, y no solo qué es.
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
            "tools_used": list(spec.tools_used),
            "example": {
                "receives": spec.example.receives,
                "leaves": spec.example.leaves,
                "detail": list(spec.example.detail),
                "caveat": spec.example.caveat,
            },
        }
        for spec in AGENT_SPECS
    ]
    edges = [{"source": "START", "target": "orchestrator"}]
    for name in AGENT_NODES:
        edges.append({"source": "orchestrator", "target": name})
        edges.append({"source": name, "target": "orchestrator"})
    edges.append({"source": "orchestrator", "target": "answer_review_gate"})
    edges.append({"source": "answer_review_gate", "target": "END"})
    return {
        "nodes": nodes,
        "edges": edges,
        "ladder": list(FALLBACK_LADDER),
        "example": {
            "question": EXAMPLE_QUESTION,
            "source": EXAMPLE_SOURCE,
            "note": EXAMPLE_NOTE,
        },
    }


# Descriptions for the privilege table's tools. A name without an entry
# here would reach the console as a bare token — fail here instead.
# || Descripciones de las tools de la tabla de privilegios. Un nombre sin
# entrada llegaría a la consola como un token pelado: fallar acá.
TOOL_DESCRIPTIONS: dict[str, str] = {
    SEARCH_CORPUS_TOOL: (
        "Recupera chunks del corpus con el mismo HybridRetriever que usan "
        "`/search` y `/answer`. No es una segunda implementación de retrieval."
    ),
}


def tool_catalog() -> list[dict]:
    """Every tool the privilege table knows, with who may call it and who does.

    || Todas las tools que conoce la tabla de privilegios, con quién puede
    llamarlas y quién las llama.
    """
    names = sorted({tool for granted in AGENT_PRIVILEGES.values() for tool in granted})
    catalog: list[dict] = []
    for name in names:
        description = TOOL_DESCRIPTIONS.get(name)
        if description is None:
            raise RuntimeError(
                f"tool {name!r} is granted but has no description in TOOL_DESCRIPTIONS"
            )
        catalog.append(
            {
                "name": name,
                "description": description,
                "granted_to": [spec.key for spec in AGENT_SPECS if name in spec.tools],
                "used_by": [spec.key for spec in AGENT_SPECS if name in spec.tools_used],
            }
        )
    return catalog


def configurable_agent_keys() -> tuple[str, ...]:
    """Agents whose model and persona actually change behaviour.

    Persisting a persona for a deterministic agent would be a setting that
    does nothing — the write is rejected instead of accepted and ignored.

    || Agentes cuyo modelo y persona realmente cambian el comportamiento.
    Persistir una persona para un agente determinista sería un setting que no
    hace nada — la escritura se rechaza en vez de aceptarse y no tener efecto.
    """
    return tuple(spec.key for spec in AGENT_SPECS if spec.llm_driven)
