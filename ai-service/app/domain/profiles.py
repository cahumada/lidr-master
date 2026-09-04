"""Per-agent overrides: persona, model, temperature, token cap.

In a table and not in a file: the deployment's filesystem is ephemeral
(Railway rebuilds the container on every deploy), so a persona edited in the
console would survive until the next push and then quietly revert. The corpus
already needs Postgres, so this costs one small table and no new dependency.

Every knob is nullable and an absent knob means "use the service default" —
the same semantics as the course's `config_payload`, which sends only the keys
that are set. That is what makes "clear the field to go back to the default" a
real operation instead of a magic sentinel value.

|| Overrides por agente: persona, modelo, temperatura, tope de tokens.

En una tabla y no en un archivo: el filesystem del despliegue es efímero
(Railway reconstruye el contenedor en cada deploy), así que una persona editada
en la consola sobreviviría hasta el próximo push y después volvería sola al
default sin avisar. El corpus ya necesita Postgres, así que esto cuesta una
tabla chica y ninguna dependencia nueva.

Cada knob es nullable y un knob ausente significa "usar el default del
servicio" — la misma semántica que el `config_payload` del curso, que manda
solo las claves seteadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.config import Settings
from app.domain.graph.catalog import SYNTHESIZER_AGENT
from app.foundation.persistence.database import Base


class AgentProfileRow(Base):
    """One agent's overrides. Absent columns fall back to Settings.

    || Los overrides de un agente. Las columnas ausentes caen a Settings.
    """

    __tablename__ = "agent_profiles"

    # The agent key from `app/domain/graph/catalog.py`, not a surrogate id:
    # there is at most one profile per agent, and making that the primary key
    # is how the database says so.
    # || La clave del agente del catálogo, no un id surrogate: hay a lo sumo un
    # perfil por agente, y que eso sea la primary key es cómo lo dice la base.
    agent_key: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Appended to the agent's system prompt, exactly like the course's
    # `persona`. Not a replacement for it: the rules that keep the answer
    # inside the retrieved context are not up for negotiation by configuration.
    # || Se appendea al system prompt del agente, igual que la `persona` del
    # curso. No lo reemplaza: las reglas que mantienen la respuesta dentro del
    # contexto recuperado no se negocian por configuración.
    persona: Mapped[str | None] = mapped_column(Text)

    # The provider travels WITH the model, in its own column rather than
    # encoded into the model string. Two providers can serve a model whose
    # name looks similar, and parsing `provider:model` back out of one column
    # is a string-splitting bug waiting for the first id that contains a
    # colon. Null means "the service default provider".
    # || El proveedor viaja CON el modelo, en su propia columna y no
    # codificado dentro del string del modelo: partir `proveedor:modelo` de una
    # sola columna es un bug de string a la espera del primer id con dos
    # puntos. Null significa "el proveedor default del servicio".
    provider: Mapped[str | None] = mapped_column(String(32))

    model: Mapped[str | None] = mapped_column(String(64))
    temperature: Mapped[float | None] = mapped_column(Float)
    max_tokens: Mapped[int | None] = mapped_column(Integer)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


@dataclass(frozen=True)
class EffectiveAgentConfig:
    """What the agent will actually run with, and where each value came from.

    ``sources`` matters for the console: "temperatura 0.0" reads very
    differently when it is the service default than when somebody set it.

    ``temperature`` is ``None`` when the chosen model does not accept one —
    current Claude models reject sampling parameters with a 400, so "no
    temperature" is a real state and not a missing value.

    || Con qué va a correr realmente el agente, y de dónde salió cada valor.
    ``temperature`` es ``None`` cuando el modelo elegido no la acepta — los
    modelos Claude actuales rechazan los parámetros de sampling con un 400,
    así que "sin temperatura" es un estado real y no un valor faltante.
    """

    provider: str
    model: str
    temperature: float | None
    max_tokens: int
    persona: str | None
    supports_temperature: bool
    sources: dict[str, str]


def resolve_agent_config(
    profile: AgentProfileRow | None, settings: Settings
) -> EffectiveAgentConfig:
    """Merge an agent's overrides over the service defaults.

    || Mezcla los overrides de un agente sobre los defaults del servicio.
    """
    from app.foundation.llm.providers import supports_temperature

    provider = getattr(profile, "provider", None)
    model = getattr(profile, "model", None)
    temperature = getattr(profile, "temperature", None)
    max_tokens = getattr(profile, "max_tokens", None)
    persona = getattr(profile, "persona", None)

    # The pair moves together: a stored model with no stored provider would
    # otherwise be read against the default provider, which may not serve it.
    # || El par se mueve junto: un modelo guardado sin proveedor guardado se
    # leería contra el proveedor default, que puede no servirlo.
    effective_model = model or settings.ANSWER_MODEL
    effective_provider = provider or (settings.ANSWER_PROVIDER if not model else provider)
    if not effective_provider:
        effective_provider = settings.ANSWER_PROVIDER

    accepts_temperature = supports_temperature(effective_model)
    if not accepts_temperature:
        effective_temperature = None
        temperature_source = "unsupported"
    elif temperature is None:
        effective_temperature = settings.ANSWER_TEMPERATURE
        temperature_source = "settings"
    else:
        effective_temperature = temperature
        temperature_source = "profile"

    return EffectiveAgentConfig(
        provider=effective_provider,
        model=effective_model,
        temperature=effective_temperature,
        max_tokens=max_tokens or settings.ANSWER_MAX_TOKENS,
        persona=persona or None,
        supports_temperature=accepts_temperature,
        sources={
            "provider": "profile" if provider else "settings",
            "model": "profile" if model else "settings",
            "temperature": temperature_source,
            "max_tokens": "profile" if max_tokens else "settings",
            "persona": "profile" if persona else "unset",
        },
    )


async def synthesizer_runtime(
    session: AsyncSession, settings: Settings
) -> tuple[Any, str | None]:
    """The LLM and persona the ``answer_synthesizer`` profile asks for.

    The single seam every synthesis path goes through — ``POST /answer``,
    ``POST /answer/agentic`` and the background runner — so a persona
    configured in the console cannot apply to one of them and not the others.
    The graph receives both through its config instead of letting the agent
    read the database, which is what keeps the agent testable without one.

    || El único punto por el que pasan todos los caminos de síntesis, así una
    persona configurada en la consola no puede aplicar a uno y no a los otros.
    El grafo los recibe por su config en vez de que el agente lea la base, que
    es lo que mantiene al agente testeable sin base.
    """
    from app.dependencies import build_answer_llm

    effective = await effective_config_for(SYNTHESIZER_AGENT, session, settings)
    llm = build_answer_llm(
        effective.provider,
        effective.model,
        effective.max_tokens,
        effective.temperature,
    )
    return llm, effective.persona


async def effective_config_for(
    agent_key: str, session: AsyncSession, settings: Settings
) -> EffectiveAgentConfig:
    """Load ``agent_key``'s profile and merge it over the defaults.

    One call for the two entry points that synthesize (``POST /answer`` and
    the graph's ``answer_synthesizer``), so a persona configured in the
    console cannot apply to one of them and not the other.

    || Carga el perfil de ``agent_key`` y lo mezcla sobre los defaults. Una
    sola llamada para los dos puntos de entrada que sintetizan, así una
    persona configurada en la consola no puede aplicar a uno y no al otro.
    """
    return resolve_agent_config(await AgentProfileRepository(session).get(agent_key), settings)


class AgentProfileRepository:
    """Reads and writes ``agent_profiles``. || Lee y escribe ``agent_profiles``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, agent_key: str) -> AgentProfileRow | None:
        """The profile for ``agent_key``, or ``None``. || El perfil, o ``None``."""
        result = await self._session.execute(
            select(AgentProfileRow).where(AgentProfileRow.agent_key == agent_key)
        )
        return result.scalar_one_or_none()

    async def all(self) -> dict[str, AgentProfileRow]:
        """Every stored profile, keyed by agent. || Todos los perfiles, por agente."""
        result = await self._session.execute(select(AgentProfileRow))
        return {row.agent_key: row for row in result.scalars()}

    async def upsert(
        self,
        agent_key: str,
        *,
        persona: str | None,
        provider: str | None,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> AgentProfileRow:
        """Write the whole profile for ``agent_key``.

        A full replace and not a patch: the console sends the form as it
        stands, and a cleared field has to mean "back to the default" rather
        than "leave whatever was there".

        || Escribe el perfil completo de ``agent_key``. Un reemplazo y no un
        patch: la consola manda el formulario como está, y un campo vaciado
        tiene que significar "volver al default" y no "dejar lo que había".
        """
        values = {
            "agent_key": agent_key,
            "persona": persona,
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        statement = (
            pg_insert(AgentProfileRow)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[AgentProfileRow.agent_key],
                set_={
                    "persona": persona,
                    "provider": provider,
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "updated_at": func.now(),
                },
            )
            .returning(AgentProfileRow)
        )
        result = await self._session.execute(statement)
        await self._session.commit()
        return result.scalar_one()

    async def delete(self, agent_key: str) -> bool:
        """Drop the profile, so the agent falls back to Settings.

        || Borra el perfil, así el agente cae a Settings.
        """
        profile = await self.get(agent_key)
        if profile is None:
            return False
        await self._session.delete(profile)
        await self._session.commit()
        return True
