import assert from "node:assert/strict"
import { randomUUID } from "node:crypto"
import { test } from "node:test"

import { hashPassword, verifyPassword } from "./password"

/**
 * Hashing and verification. Slow on purpose — bcrypt with cost 12 is about a
 * quarter second per call, and that is the point of it, so this file stays
 * short rather than exhaustive.
 *
 * The fixtures are built at run time and not written as literals. Nothing
 * here was ever a credential, but a plausible-looking password string in a
 * committed file is what a secret scanner is built to flag, and it did — on
 * this file, on a public repo. Cheaper to leave the scanner nothing to find
 * than to teach every scanner that these two are fine.
 *
 * || Hasheo y verificación. Lentos a propósito: bcrypt con costo 12 tarda un
 * cuarto de segundo por llamada, y esa es su razón de ser. Los fixtures se
 * arman en tiempo de ejecución y no van como literales: nunca fueron una
 * credencial, pero una cadena con pinta de contraseña en un archivo
 * commiteado es justo lo que un escáner de secretos busca — y lo encontró,
 * acá, en un repo público. Sale más barato no dejarle nada que encontrar que
 * enseñarle a cada escáner que estas dos son inofensivas.
 */

/** Fixture, not a credential. || Fixture, no una credencial. */
function fixture(): string {
  return `fixture-${randomUUID()}`
}

test("una contraseña correcta verifica", async () => {
  const plain = fixture()
  const hash = await hashPassword(plain)
  assert.equal(await verifyPassword(plain, hash), true)
})

test("una contraseña incorrecta no verifica", async () => {
  const hash = await hashPassword(fixture())
  assert.equal(await verifyPassword(fixture(), hash), false)
})

test("el hash no contiene la contraseña", async () => {
  const plain = fixture()
  const hash = await hashPassword(plain)
  assert.ok(!hash.includes(plain))
})

test("dos hashes de la misma contraseña difieren", async () => {
  // El salt va adentro del hash. Sin esto, dos cuentas con la misma
  // contraseña se reconocerían mirando la tabla.
  // || The salt lives inside the hash. Without it, two accounts sharing a
  // password would be recognisable from the table alone.
  const plain = fixture()
  const a = await hashPassword(plain)
  const b = await hashPassword(plain)
  assert.notEqual(a, b)
})

test("una cuenta sin contraseña no verifica, y no lanza", async () => {
  // Un usuario que solo entra por Google tiene `passwordHash = null`.
  // || A Google-only user has `passwordHash = null`.
  assert.equal(await verifyPassword(fixture(), null), false)
  assert.equal(await verifyPassword(fixture(), undefined), false)
})

test("una contraseña vacía no verifica contra un hash válido", async () => {
  const hash = await hashPassword(fixture())
  assert.equal(await verifyPassword("", hash), false)
})

test("hashear una contraseña vacía lanza", async () => {
  await assert.rejects(() => hashPassword(""))
})
