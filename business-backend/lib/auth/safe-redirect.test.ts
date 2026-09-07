import assert from "node:assert/strict"
import { test } from "node:test"

import { DEFAULT_REDIRECT, safeRedirect } from "./safe-redirect"

test("una ruta interna pasa tal cual", () => {
  assert.equal(safeRedirect("/models"), "/models")
  assert.equal(safeRedirect("/agents/flow?tab=x"), "/agents/flow?tab=x")
})

test("una URL absoluta no pasa", () => {
  assert.equal(safeRedirect("https://evil.example"), DEFAULT_REDIRECT)
  assert.equal(safeRedirect("http://evil.example"), DEFAULT_REDIRECT)
})

test("una URL protocol-relative no pasa", () => {
  // El caso que vale nombrar: no parece una URL y lo es. El browser lee
  // `//host` como «mismo esquema, ese host».
  // || The case worth naming: it does not look like a URL and is one.
  assert.equal(safeRedirect("//evil.example"), DEFAULT_REDIRECT)
  assert.equal(safeRedirect(String.raw`/\evil.example`), DEFAULT_REDIRECT)
})

test("volver al login no pasa, porque sería un bucle", () => {
  assert.equal(safeRedirect("/login"), DEFAULT_REDIRECT)
  assert.equal(safeRedirect("/login?next=/models"), DEFAULT_REDIRECT)
})

test("un `next` repetido llega como array y no pasa", () => {
  assert.equal(safeRedirect(["/a", "/b"]), DEFAULT_REDIRECT)
})

test("ausente o vacío cae al default", () => {
  assert.equal(safeRedirect(undefined), DEFAULT_REDIRECT)
  assert.equal(safeRedirect(""), DEFAULT_REDIRECT)
})
