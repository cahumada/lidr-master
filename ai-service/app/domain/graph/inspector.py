"""Read-only view of the synthesizer prompt, system guardrails and templates.

The console has to *show* what the model is told. It must not be able to
replace the five grounding rules — those are what keeps the fidelity eval
comparable. Operator extras (persona, guardrails) append after them.

|| Vista de solo lectura del prompt del sintetizador, los guardrails de
sistema y los templates. La consola tiene que *mostrar* lo que se le dice
al modelo; no puede reemplazar las cinco reglas de grounding.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.foundation.prompts import render_prompt
from app.generation.rag.prompt_builder import PROMPT_NAME, PROMPT_VERSION

# Voice for a senior functional analyst who works Visual Time. Domain nouns
# stay in Spanish: they are the words the corpus uses.
# || Voz de un analista funcional senior que trabaja Visual Time. Los
# sustantivos de dominio van en español: son las palabras del corpus.
PERSONA_TEMPLATE = (
    "Sos un analista funcional senior, especialista en el mercado asegurador "
    "y en Visual Time.\n"
    "\n"
    "Cómo respondés:\n"
    "- Primero la regla o el procedimiento; después el caso borde y las excepciones.\n"
    "- Nombrá transacciones, pantallas y campos con el código que aparece en el "
    "contexto (CA014, COL500, …), no con un alias inventado.\n"
    "- Distinguí alta, consulta, anulación y proceso batch cuando el contexto "
    "lo deja ver.\n"
    "- Si hay una validación o un control de usuario, mencioná en qué pantalla "
    "o paso ocurre.\n"
    "- Cuando el contexto no cubra un caso, decilo; no completes con práctica "
    "de mercado genérica.\n"
    "\n"
    "No hagas:\n"
    "- No inventes primas, vigencias, productos ni circuitos de cobranza o "
    "siniestros que no estén citados.\n"
    "- No suavices una validación obligatoria ni omitas un rechazo documentado."
)

# Extra operator constraints — business policy, not a rewrite of the five rules.
# || Restricciones extra de operador: política de negocio, no una reescritura
# de las cinco reglas.
GUARDRAILS_TEMPLATE = (
    "- Si la respuesta toca importes, primas o montos, advertí que el valor "
    "exacto depende de la póliza y de la parametrización vigente.\n"
    "- No recomiendes un workaround que saltee una validación de la especificación.\n"
    "- Si el contexto describe un circuito y una excepción, mencioná ambos y "
    "citá cada uno.\n"
    "- Cuando haya dos caminos (manual y automático), explicalos por separado."
)


@dataclass(frozen=True)
class SystemGuardrail:
    """One rule the operator can see and cannot turn off.

    || Una regla que el operador puede ver y no puede apagar.
    """

    id: str
    kind: str
    title: str
    description: str


# The five prompt rules plus the only verifiable provenance check. `kind`
# tells the console which are text and which are code.
# || Las cinco reglas del prompt más el único chequeo verificable de
# procedencia. `kind` le dice a la consola cuáles son texto y cuál es código.
SYSTEM_GUARDRAILS: tuple[SystemGuardrail, ...] = (
    SystemGuardrail(
        id="context_only",
        kind="prompt",
        title="Solo el contexto recuperado",
        description=(
            "Responde SOLO con información que aparezca en el contexto. No uses "
            "conocimiento previo ni un sistema de seguros genérico."
        ),
    ),
    SystemGuardrail(
        id="cite_provenance",
        kind="prompt",
        title="Citar procedencia",
        description=(
            "Cada afirmación cita [document_id · section] con los identificadores "
            "del contexto. Ejemplo: [CA014 · Validaciones]."
        ),
    ),
    SystemGuardrail(
        id="insufficient_context",
        kind="prompt",
        title="Decir cuando no alcanza",
        description=(
            "Si el contexto no alcanza, usar la frase fija: «No hay información "
            "suficiente en la documentación recuperada para responder.»"
        ),
    ),
    SystemGuardrail(
        id="no_invention",
        kind="prompt",
        title="No inventar artefactos",
        description=(
            "No inventar códigos de transacción, campos, validaciones, "
            "procedimientos ni documentos que no estén en el contexto."
        ),
    ),
    SystemGuardrail(
        id="spanish",
        kind="prompt",
        title="Responder en español",
        description="La respuesta va en español.",
    ),
    SystemGuardrail(
        id="citation_grounding",
        kind="code",
        title="Citas contra los hits",
        description=(
            "`check_grounding` marca grounded=false si un document_id citado no "
            "está entre los hits recuperados. No se puede desactivar desde el perfil."
        ),
    ),
)


def base_system_prompt() -> str:
    """The versioned system prompt with no operator extras.

    || El system prompt versionado, sin extras de operador.
    """
    return render_prompt(PROMPT_NAME, PROMPT_VERSION, "system")


def compose_system_prompt(
    *, persona: str | None = None, guardrails: str | None = None
) -> str:
    """The prompt the model will see for this persona and operator extras.

    || El prompt que verá el modelo con esta persona y estos extras.
    """
    return render_prompt(
        PROMPT_NAME,
        PROMPT_VERSION,
        "system",
        persona=persona,
        guardrails=guardrails,
    )


def system_guardrails_view() -> list[dict[str, str]]:
    """System guardrails as the config payload. || Guardrails de sistema para el config."""
    return [
        {
            "id": item.id,
            "kind": item.kind,
            "title": item.title,
            "description": item.description,
        }
        for item in SYSTEM_GUARDRAILS
    ]
