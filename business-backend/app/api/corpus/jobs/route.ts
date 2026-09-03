import type { NextRequest } from "next/server";

import { toErrorPayload } from "@/lib/ai-service/base-client";
import { jobs } from "@/lib/ai-service/corpus";

/** `GET /api/corpus/jobs` -- the recent jobs, newest first. || Los últimos jobs, el más nuevo primero. */
export async function GET(request: NextRequest) {
  const raw = request.nextUrl.searchParams.get("limit");
  const limit = raw ? Number(raw) : undefined;

  try {
    return Response.json(
      await jobs(Number.isFinite(limit) ? limit : undefined),
    );
  } catch (error) {
    const payload = toErrorPayload(error);
    return Response.json(payload, { status: payload.status });
  }
}
