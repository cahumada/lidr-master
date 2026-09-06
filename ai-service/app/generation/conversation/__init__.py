"""Conversation memory: what a session remembers between turns.

Memory here feeds RETRIEVAL first and generation second, which is the one
structural difference from the course's conversational estimator. There, the
history enters the generation call and that is the whole job. Here a broken
follow-up ("¿y para siniestros?") reaches the retriever as loose text, brings
back noise, and no amount of memory in the synthesis prompt can repair it —
the synthesizer can only cite what it was handed.

So the pieces are ordered by where they act:

* :mod:`facts` — the durable, structured facts of the session. Re-rendered
  into the system prompt every turn instead of stored as messages, which is
  what makes them survive any trim.
* :mod:`resolver` — turns a referential question into a retrievable one,
  BEFORE decomposition. Conservative by construction: with no clear referent
  it returns the question untouched.
* :mod:`anchors` — scope constraints the user pinned explicitly, which the
  sliding window never evicts.
* :mod:`budget` — fits the memory block inside the context budget, where
  evidence always wins.

|| Memoria de conversación: lo que una sesión recuerda entre turnos.

Acá la memoria alimenta la RECUPERACIÓN antes que la generación, que es la
única diferencia estructural con el estimador conversacional del curso. Allá
el historial entra a la llamada de generación y ahí termina el trabajo. Acá
una pregunta de seguimiento rota llega al retriever como texto suelto, trae
ruido, y ninguna cantidad de memoria en el prompt de síntesis lo arregla: el
sintetizador solo puede citar lo que le trajeron.
"""
