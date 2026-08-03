import { test } from 'node:test';
import assert from 'node:assert/strict';
import { aggregateAvailabilityBatch, runAvailabilityAll, type AvailabilityBatchWindowResult } from '../../src/application/run-availability-all.js';
import { loadConfig } from '../../src/config/load-config.js';
import type { RunManifest } from '../../src/domain/types.js';

test('consulta todas las fechas configuradas en orden de prioridad', async () => {
  const config = await loadConfig();
  const profile = config.activeTrips.find((item) => item.profileId === 'wdw-nov-2027')!;
  const priorities: number[] = [];
  const previousProfile = process.env.SENTINEL_AVAILABILITY_PROFILE_ID;
  const previousPriority = process.env.SENTINEL_AVAILABILITY_WINDOW_PRIORITY;
  const previousValidation = process.env.SENTINEL_AVAILABILITY_VALIDATION;
  process.env.SENTINEL_AVAILABILITY_PROFILE_ID = profile.profileId;
  process.env.SENTINEL_AVAILABILITY_VALIDATION = 'true';
  process.env.SENTINEL_AVAILABILITY_WINDOW_PRIORITY = '99';
  let tick = 0;
  try {
    const result = await runAvailabilityAll(config, process.cwd(), {
      now: () => new Date(`2026-08-03T18:00:0${tick++}.000Z`),
      runSingle: async (): Promise<RunManifest> => {
        const priority = Number(process.env.SENTINEL_AVAILABILITY_WINDOW_PRIORITY);
        priorities.push(priority);
        return {
          schemaVersion: 1,
          runId: `run-${priority}`,
          workflow: 'Disney Sentinel - Disponibilidad',
          monitorKind: 'availability',
          startedAt: '2026-08-03T18:00:00.000Z',
          finishedAt: '2026-08-03T18:00:01.000Z',
          durationMs: 1000,
          status: priority === 2 ? 'SUCCESS_CHANGE' : 'SUCCESS_NO_CHANGE',
          sourceHealth: 'HEALTHY',
          attempts: 1,
          itemsObserved: 2,
          eventsCreated: priority === 2 ? 1 : 0,
          alertsSent: 0,
          estimatedMinutesMonth: 0,
          notes: [`prioridad ${priority}`]
        };
      }
    });
    assert.deepEqual(priorities, profile.dateWindows.map((window) => window.priority).sort((a, b) => a - b));
    assert.equal(result.windowsRequested, profile.dateWindows.length);
    assert.equal(result.windowsCompleted, profile.dateWindows.length);
    assert.equal(result.status, 'SUCCESS_CHANGE');
    assert.equal(result.itemsObserved, profile.dateWindows.length * 2);
    assert.equal(process.env.SENTINEL_AVAILABILITY_WINDOW_PRIORITY, '99');
  } finally {
    restore('SENTINEL_AVAILABILITY_PROFILE_ID', previousProfile);
    restore('SENTINEL_AVAILABILITY_WINDOW_PRIORITY', previousPriority);
    restore('SENTINEL_AVAILABILITY_VALIDATION', previousValidation);
  }
});

test('el lote informa la falla más severa sin perder resultados parciales', () => {
  const base = (status: RunManifest['status'], sourceHealth: AvailabilityBatchWindowResult['sourceHealth']): AvailabilityBatchWindowResult => ({
    priority: 1, checkIn: '2027-11-01', nights: 6, runId: 'run', status, sourceHealth,
    attempts: 1, itemsObserved: 0, eventsCreated: 0, alertsSent: 0, notes: []
  });
  const result = aggregateAvailabilityBatch([
    base('SUCCESS_NO_CHANGE', 'HEALTHY'),
    { ...base('FAILED_STRUCTURAL', 'ERROR_STRUCTURAL'), priority: 2 }
  ]);
  assert.deepEqual(result, { status: 'FAILED_STRUCTURAL', sourceHealth: 'ERROR_STRUCTURAL' });
});

function restore(name: string, value: string | undefined): void {
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
}
