"use client";

import { use, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  useStartLoopMutation,
  useStopLoopMutation,
  useGetLoopStatusQuery,
  type LoopRound,
} from "@/store/api/loop-api";

export default function LoopPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = use(params);
  const [startLoop, { data: loopResult, isLoading: isRunning }] =
    useStartLoopMutation();
  const [stopLoop] = useStopLoopMutation();
  const { data: loopStatus } = useGetLoopStatusQuery(jobId, {
    pollingInterval: 5000,
  });
  const [maxRounds, setMaxRounds] = useState(10);

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">
          Audit-Correct Loop — A2A Protocol
        </h1>
        <div className="flex items-center gap-4">
          <label className="text-sm">
            Max Rounds:
            <input
              type="number"
              value={maxRounds}
              onChange={(e) => setMaxRounds(Number(e.target.value))}
              min={1}
              max={50}
              className="ml-2 w-16 border rounded px-2 py-1"
            />
          </label>
          <Button
            onClick={() => startLoop({ jobId, maxRounds })}
            disabled={isRunning}
          >
            {isRunning ? "Running..." : "Start Loop"}
          </Button>
          <Button variant="destructive" onClick={() => stopLoop(jobId)}>
            Force Stop
          </Button>
        </div>
      </div>

      {/* Current Status */}
      {loopStatus && (
        <Card className="mb-4">
          <CardContent className="pt-4">
            <p className="text-sm">
              Status: <Badge>{loopStatus.status}</Badge> — Round:{" "}
              {loopStatus.current_round}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Round Timeline */}
      {loopResult && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Loop Result
              <Badge
                variant={
                  loopResult.status === "approved" ? "default" : "destructive"
                }
              >
                {loopResult.status}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 overflow-x-auto pb-4">
              {loopResult.rounds.map((round: LoopRound) => (
                <div
                  key={round.round}
                  className="flex flex-col items-center min-w-[180px] p-4 border rounded-lg"
                >
                  <span className="text-xs font-semibold mb-1">
                    Round {round.round}
                  </span>
                  <Badge
                    variant={
                      round.audit_issues === 0 ? "default" : "destructive"
                    }
                    className="mb-2"
                  >
                    {round.audit_issues} issues
                  </Badge>
                  <span className="text-xs text-muted-foreground mb-1">
                    Audit: {round.audit_task_state}
                  </span>
                  {round.correction_applied && (
                    <div className="text-xs text-center">
                      <p>{round.docs_corrected} docs fixed</p>
                      <p>{round.false_positives} false positives</p>
                      {round.correction_task_state && (
                        <p className="text-muted-foreground">
                          Correction: {round.correction_task_state}
                        </p>
                      )}
                    </div>
                  )}
                  {round.audit_status === "approved" && (
                    <span className="text-green-600 text-lg mt-1">✓</span>
                  )}
                </div>
              ))}
            </div>
            {loopResult.reason && (
              <p className="text-sm text-muted-foreground mt-2">
                ⚠️ {loopResult.reason}
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
