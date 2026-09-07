/**
 * Default window for `/usage`: the current calendar month in Argentina.
 * The console is es-AR and Argentina has no DST — offset is always −03:00.
 * || Ventana por defecto de `/usage`: el mes calendario en curso en
 * Argentina. La consola es es-AR y no hay DST: el offset es siempre −03:00.
 */

const TIME_ZONE = "America/Argentina/Buenos_Aires"
const OFFSET = "-03:00"

function pad(value: number): string {
  return String(value).padStart(2, "0")
}

function clockInArgentina(now: Date): { year: number; month: number } {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "numeric",
  }).formatToParts(now)
  const year = Number(parts.find((part) => part.type === "year")?.value)
  const month = Number(parts.find((part) => part.type === "month")?.value)
  return { year, month }
}

function lastDayOfMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate()
}

function toDateTimeLocal(year: number, month: number, day: number, hour: number, minute: number): string {
  return `${year}-${pad(month)}-${pad(day)}T${pad(hour)}:${pad(minute)}`
}

export function artLocalToIso(local: string): string | undefined {
  if (!local) return undefined
  const instant = new Date(`${local}:00${OFFSET}`)
  if (Number.isNaN(instant.getTime())) return undefined
  return instant.toISOString()
}

export function currentMonthRange(now = new Date()): {
  fromLocal: string
  toLocal: string
  from: string
  to: string
} {
  const { year, month } = clockInArgentina(now)
  const fromLocal = toDateTimeLocal(year, month, 1, 0, 0)
  const toLocal = toDateTimeLocal(year, month, lastDayOfMonth(year, month), 23, 59)
  const from = artLocalToIso(fromLocal)
  const to = artLocalToIso(toLocal)
  if (!from || !to) {
    throw new Error("current month range is not a valid instant")
  }
  return { fromLocal, toLocal, from, to }
}
