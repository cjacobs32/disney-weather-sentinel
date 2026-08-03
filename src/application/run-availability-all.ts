import type { LoadedConfig } from '../config/load-config.js';
import type { RunManifest, SourceHealth } from '../domain/types.js';
import { newId } from '../infrastructure/ids.js';
import { readAvailabilityRunOverride, runAvailability } from './run-availability.js';

export interface AvailabilityBatchWindowResult {
  priority: number;
  checkIn: string;
  nights: number;
  runId: string;
  status: RunManifest['status'];
  sourceHealth: SourceHealth;
  attempts: number;
  itemsObserved: number;
  eventsCreated: number;
  alertsSent: number;
  notes: string[];
}

export interface AvailabilityBatchManifest {
  schemaVersion: 1;
  batchRunId: string;
  workflow: 'Disney Sentinel - Disponibilidad - Todas las fechas';
  monitorKind: 'availability-batch';
  profileId?: string;
  validationMode: boolean;
  startedAt: string;
  finishedAt: string;
  durationMs: number;
  status: RunManifest['status'];
  sourceHealth: SourceHealth;
  windowsRequested: number;
  windowsCompleted: number;
  itemsObserved: number;
  eventsCreated: number;
  alertsSent: number;
  results: AvailabilityBatchWindowResult[];
  notes: string[];
}

export interface AvailabilityBatchDependencies {
  runSingle?: typeof runAvailability;
  now?: () => Date;
}

export async function runAvailabilityAll(
  config: LoadedConfig,
  rootDir = process.cwd(),
  dependencies: AvailabilityBatchDependencies = {}
): Promise<AvailabilityBatchManifest> {
  const runSingle = dependencies.runSingle ?? runAvailability;
  const now = dependencies.now ?? (() => new Date());
  const started = now();
  const override = readAvailabilityRunOverride();
  const profileId = override.profileId;
  const profile = profileId
    ? config.activeTrips.find((candidate) => candidate.profileId === profileId && candidate.monitoring.availabilityEnabled !== false)
    : undefined;

  if (!profileId || !profile) {
    const finished = now();
    return {
      schemaVersion: 1,
      batchRunId: newId('batch'),
      workflow: 'Disney Sentinel - Disponibilidad - Todas las fechas',
      monitorKind: 'availability-batch',
      ...(profileId ? { profileId } : {}),
      validationMode: override.validationMode,
      startedAt: started.toISOString(),
      finishedAt: finished.toISOString(),
      durationMs: Math.max(0, finished.getTime() - started.getTime()),
      status: 'SKIPPED_DISABLED',
      sourceHealth: 'HEALTHY',
      windowsRequested: 0,
      windowsCompleted: 0,
      itemsObserved: 0,
      eventsCreated: 0,
      alertsSent: 0,
      results: [],
      notes: [profileId
        ? `No existe un viaje activo y habilitado para disponibilidad con profileId ${profileId}.`
        : 'La consulta de todas las fechas requiere SENTINEL_AVAILABILITY_PROFILE_ID.']
    };
  }

  const windows = [...profile.dateWindows].sort((a, b) => a.priority - b.priority);
  const originalPriority = process.env.SENTINEL_AVAILABILITY_WINDOW_PRIORITY;
  const originalAllWindows = process.env.SENTINEL_AVAILABILITY_ALL_WINDOWS;
  const results: AvailabilityBatchWindowResult[] = [];

  try {
    process.env.SENTINEL_AVAILABILITY_ALL_WINDOWS = 'false';
    for (const window of windows) {
      process.env.SENTINEL_AVAILABILITY_WINDOW_PRIORITY = String(window.priority);
      const manifest = await runSingle(config, rootDir);
      results.push({
        priority: window.priority,
        checkIn: window.checkIn,
        nights: window.nights,
        runId: manifest.runId,
        status: manifest.status,
        sourceHealth: manifest.sourceHealth,
        attempts: manifest.attempts,
        itemsObserved: manifest.itemsObserved,
        eventsCreated: manifest.eventsCreated,
        alertsSent: manifest.alertsSent,
        notes: manifest.notes
      });
    }
  } finally {
    restoreEnv('SENTINEL_AVAILABILITY_WINDOW_PRIORITY', originalPriority);
    restoreEnv('SENTINEL_AVAILABILITY_ALL_WINDOWS', originalAllWindows);
  }

  const finished = now();
  const aggregate = aggregateAvailabilityBatch(results);
  return {
    schemaVersion: 1,
    batchRunId: newId('batch'),
    workflow: 'Disney Sentinel - Disponibilidad - Todas las fechas',
    monitorKind: 'availability-batch',
    profileId,
    validationMode: override.validationMode,
    startedAt: started.toISOString(),
    finishedAt: finished.toISOString(),
    durationMs: Math.max(0, finished.getTime() - started.getTime()),
    status: aggregate.status,
    sourceHealth: aggregate.sourceHealth,
    windowsRequested: windows.length,
    windowsCompleted: results.length,
    itemsObserved: results.reduce((total, result) => total + result.itemsObserved, 0),
    eventsCreated: results.reduce((total, result) => total + result.eventsCreated, 0),
    alertsSent: results.reduce((total, result) => total + result.alertsSent, 0),
    results,
    notes: [
      `Viaje: ${profile.displayName} (${profile.profileId}).`,
      `Se verificaron ${results.length} de ${windows.length} fechas configuradas.`,
      ...(override.validationMode
        ? ['Modo validación técnica: Telegram y circuito productivo no se modifican.']
        : ['Modo productivo: se aplican las reglas normales de eventos, alertas y circuito.']),
      ...results.map((result) => `Prioridad ${result.priority}: ${result.checkIn}, ${result.nights} noches — ${result.status} / ${result.sourceHealth}.`)
    ]
  };
}

export function aggregateAvailabilityBatch(results: AvailabilityBatchWindowResult[]): Pick<AvailabilityBatchManifest, 'status' | 'sourceHealth'> {
  if (results.length === 0) return { status: 'SKIPPED_DISABLED', sourceHealth: 'HEALTHY' };
  const failureOrder: RunManifest['status'][] = ['FAILED_BLOCKED', 'FAILED_STRUCTURAL', 'FAILED_TRANSIENT', 'FAILED_AMBIGUOUS'];
  for (const failure of failureOrder) {
    if (results.some((result) => result.status === failure)) {
      return { status: failure, sourceHealth: healthForFailure(failure) };
    }
  }
  if (results.some((result) => result.status === 'SUCCESS_CHANGE')) return { status: 'SUCCESS_CHANGE', sourceHealth: worstHealth(results) };
  if (results.some((result) => result.status === 'SUCCESS_NO_CHANGE')) return { status: 'SUCCESS_NO_CHANGE', sourceHealth: worstHealth(results) };
  if (results.some((result) => result.status === 'SKIPPED_BUDGET')) return { status: 'SKIPPED_BUDGET', sourceHealth: 'DISABLED_BUDGET' };
  if (results.some((result) => result.status === 'SKIPPED_SPACING')) return { status: 'SKIPPED_SPACING', sourceHealth: worstHealth(results) };
  return { status: 'SKIPPED_DISABLED', sourceHealth: worstHealth(results) };
}

function worstHealth(results: AvailabilityBatchWindowResult[]): SourceHealth {
  const order: SourceHealth[] = ['BLOCKED_CAPTCHA', 'ERROR_STRUCTURAL', 'DEGRADED_TRANSIENT', 'CIRCUIT_OPEN', 'DISABLED_BUDGET', 'HEALTHY'];
  return order.find((health) => results.some((result) => result.sourceHealth === health)) ?? 'HEALTHY';
}

function healthForFailure(status: RunManifest['status']): SourceHealth {
  if (status === 'FAILED_BLOCKED') return 'BLOCKED_CAPTCHA';
  if (status === 'FAILED_STRUCTURAL') return 'ERROR_STRUCTURAL';
  return 'DEGRADED_TRANSIENT';
}

function restoreEnv(name: string, value: string | undefined): void {
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
}
