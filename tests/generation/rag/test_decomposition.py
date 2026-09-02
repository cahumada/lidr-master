"""El divisor de consultas compuestas, y la garantía de que no puede regresar.

Casos tomados del golden set, no inventados: cada pregunta de acá es una
pregunta real de usuario del conjunto de 35.
"""

from app.generation.rag.retrieval.decomposition import decompose
from app.generation.rag.retrieval.fusion import cap_per_group, reciprocal_rank_fusion

# --- No dividir es una respuesta válida ----------------------------------------


def test_a_simple_question_is_not_split():
    """`U-DP001-borrar-ramo-comercial`, del golden set. Una sola pregunta, un
    solo documento."""
    pregunta = (
        "¿Qué códigos de error me arrojará el sistema si intento eliminar un "
        "ramo comercial que todavía tiene pólizas o productos asociados?"
    )
    assert decompose(pregunta) == []


def test_a_comma_that_does_not_precede_an_interrogative_does_not_split():
    """El lookahead es todo el punto: sin él esta pregunta se parte por la coma
    de la subordinada y produce dos consultas sin sentido."""
    pregunta = (
        "¿Cuáles son los únicos tipos de documentos permitidos si intento "
        "realizar una relación de cobranzas para una póliza de un producto "
        "Unit Linked (VNT)?"
    )
    assert decompose(pregunta) == []


def test_an_enumeration_with_no_determiners_is_not_split():
    """`U-multi-declaracion-siniestro`. Es genuinamente compuesta y el divisor
    NO la parte: "variables de clave inicial" y "validaciones de clientes" son
    plurales escuetos, sin determinante donde anclarse.

    Este es el límite conocido de las reglas y el caso que justificaría un
    modelo. Queda fijado como test para que se vea cuándo deja de ser cierto."""
    pregunta = (
        "¿Qué secuencia de ventanas, variables de clave inicial y validaciones "
        "de clientes requiero para realizar la declaración formal de un siniestro?"
    )
    assert decompose(pregunta) == []


# --- Forma 1: cláusulas coordinadas --------------------------------------------


def test_three_coordinated_clauses_give_three_sub_queries():
    """`U-multi-lote-pac-rechazos`, del golden set."""
    pregunta = (
        "Si un lote de cobranza PAC tiene problemas de pago, ¿cómo se originan "
        "esos boletines en el sistema, cómo puedo registrar sus rechazos "
        "(manual o automáticamente) y en qué pantalla valido el monto neto que "
        "realmente se va a notificar como cobrado?"
    )
    assert len(decompose(pregunta)) == 3


def test_the_context_reaches_every_sub_query():
    """Donde están las entidades. La cláusula suelta "de qué manera afecta a la
    generación manual de su boletín de cobro" no menciona PAC ni TRANSBANK ni el
    recibo, así que sin el contexto es una pregunta sobre nada."""
    pregunta = (
        "Si un recibo tiene configurada una vía de cobro automática como PAC o "
        "TRANSBANK, ¿cómo se gestiona esta domiciliación bancaria, de qué "
        "manera afecta a la generación manual de su boletín de cobro y qué "
        "controles existen si necesito traspasar ese pago a otro recibo?"
    )
    subs = decompose(pregunta)

    assert len(subs) == 3
    assert all("PAC o TRANSBANK" in sub for sub in subs)


def test_every_sub_query_is_a_question():
    pregunta = (
        "Para controlar la cartera de cobros pendientes de la compañía, ¿cómo se "
        "agrupan los cobros automáticos al generarse, por qué el reporte general "
        "de recibos por estado los excluye y con qué informe controlo "
        "específicamente los cheques a fecha y tarjetas pendientes?"
    )
    for sub in decompose(pregunta):
        assert sub.endswith("?")


# --- Forma 2: frases nominales coordinadas -------------------------------------


def test_coordinated_noun_phrases_share_the_head():
    """`U-multi-consultas-disenador`. No hay un interrogativo por parte: hay una
    cabeza compartida y tres frases nominales."""
    pregunta = (
        "¿Cómo puedo consultar de forma estructurada los planes definidos para "
        "un producto, las exclusiones parametrizadas entre sus coberturas y la "
        "escala de comisiones por año asignada a los intermediarios?"
    )
    subs = decompose(pregunta)

    assert len(subs) == 3
    assert all(sub.startswith("¿Cómo puedo consultar de forma estructurada") for sub in subs)


def test_the_noun_shape_also_keeps_the_context():
    """`U-multi-conversion-propuesta-primera-prima`: contexto Y cabeza
    compartida."""
    pregunta = (
        "Al realizar la conversión de una propuesta o cotización a póliza "
        "definitiva, ¿cómo interactúa la exigencia del pago de la primera prima "
        "en caja, el rol del cliente pagador y el registro del abono "
        "correspondiente en la cuenta corriente?"
    )
    subs = decompose(pregunta)

    assert len(subs) == 3
    assert all(sub.startswith("Al realizar la conversión") for sub in subs)
    assert all("¿cómo interactúa" in sub for sub in subs)


def test_clauses_are_tried_before_noun_phrases():
    """Una pregunta con cláusulas coordinadas también tiene determinantes
    adentro. Si la regla nominal corriera primero la partiría por el lugar
    equivocado, así que la de cláusulas —más específica— va antes.

    Acá la cláusula 2 arranca con "cómo", que la regla nominal no respeta."""
    pregunta = (
        "Si un cliente reclama por un recibo que figura como rechazado, ¿cómo "
        "registran las tablas de recibos y de cuenta corriente este rechazo y de "
        "qué manera impacta este saldo en el reporte diario de cuadre?"
    )
    subs = decompose(pregunta)

    assert len(subs) == 2
    assert subs[1].endswith("en el reporte diario de cuadre?")
    assert "de qué manera impacta" in subs[1]


# --- La garantía: agregar no puede cambiar el prefijo --------------------------


def document_of(key: str) -> str:
    return key.split("::")[0]


def test_appending_never_changes_the_capped_prefix():
    """La invariante de la que depende todo el cambio.

    `cap_per_group` es un filtro en streaming sobre una lista ordenada, así que
    agregarle elementos al final no puede tocar lo que ya salió. Eso es lo que
    hace que la descomposición no pueda regresar, y las dos variantes que
    reordenan —fusionar solo las partes, y fusionar completa más partes—
    rompieron 7 y 4 documentos justamente por no tener esta propiedad."""
    completa = reciprocal_rank_fusion(
        {"vector": [f"D{i}::x::1" for i in range(12)]}, key=lambda k: k, k=60
    )
    agregados = reciprocal_rank_fusion(
        {"sub0": [f"E{i}::y::1" for i in range(8)]}, key=lambda k: k, k=60
    )

    solo = cap_per_group(list(completa), document_of, cap=1, limit=10)
    con_extra = cap_per_group(list(completa) + list(agregados), document_of, cap=1, limit=10)

    assert [item.key for item in con_extra] == [item.key for item in solo]


def test_appending_fills_places_the_whole_query_left_empty():
    """El caso donde sí sirve: la consulta completa devuelve 4 documentos y
    quedan 6 puestos vacíos. Ahí lo agregado entra sin desplazar nada."""
    completa = reciprocal_rank_fusion(
        {"vector": [f"D{i}::x::1" for i in range(4)]}, key=lambda k: k, k=60
    )
    agregados = reciprocal_rank_fusion(
        {"sub0": [f"E{i}::y::1" for i in range(8)]}, key=lambda k: k, k=60
    )

    con_extra = cap_per_group(list(completa) + list(agregados), document_of, cap=1, limit=10)

    assert len(con_extra) == 10
    assert [item.key for item in con_extra][:4] == [item.key for item in completa]
