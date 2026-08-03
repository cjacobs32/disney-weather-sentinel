import { loadConfig } from './config/load-config.js';
import { runAvailability } from './application/run-availability.js';
import { runAvailabilityAll } from './application/run-availability-all.js';
import { runPhase0 } from './application/run-phase0.js';
import { runPromotions } from './application/run-promotions.js';
import { runSummary, generateStatusOnly } from './application/run-summary.js';
import { runWatchdog } from './application/run-watchdog.js';
import { manageTripFromIssue } from './application/manage-trips.js';
import { renderTripsReport } from './application/status-report.js';
import { FileStateStore } from './adapters/git-state/file-state-store.js';
import { TelegramClient } from './adapters/telegram/telegram-client.js';
import { Logger } from './infrastructure/logging.js';

const logger = new Logger('cli');
const command = process.argv[2] ?? 'help';

async function main(): Promise<void> {
  const config = await loadConfig();
  switch (command) {
    case 'phase0': console.log(JSON.stringify(await runPhase0(config), null, 2)); break;
    case 'promotions': console.log(JSON.stringify(await runPromotions(config), null, 2)); break;
    case 'availability': console.log(JSON.stringify(await runAvailability(config), null, 2)); break;
    case 'availability-all': console.log(JSON.stringify(await runAvailabilityAll(config), null, 2)); break;
    case 'watchdog': console.log(JSON.stringify(await runWatchdog(config), null, 2)); break;
    case 'summary': console.log(JSON.stringify(await runSummary(config), null, 2)); break;
    case 'status': console.log(await generateStatusOnly(config)); break;
    case 'trips-report': {
      const report = renderTripsReport(config.trips);
      await new FileStateStore().writeTripsReport(report);
      console.log(report);
      break;
    }
    case 'trip-issue': console.log(JSON.stringify(await manageTripFromIssue(config), null, 2)); break;
    case 'telegram-test':
      await new TelegramClient().sendText('🏰 Disney Sentinel — prueba de Telegram correcta.');
      console.log('Telegram OK');
      break;
    case 'validate-config':
      console.log(JSON.stringify({
        valid: true,
        mode: config.monitoring.mode,
        activeTrips: config.activeTrips.map((trip) => ({ id: trip.profileId, name: trip.displayName, priority: trip.priority })),
        phase0ProfileId: config.phase0Trip.profileId
      }, null, 2));
      break;
    default:
      console.log(`Disney Sentinel\n\nComandos:\n  validate-config\n  telegram-test\n  phase0\n  promotions\n  availability\n  availability-all\n  watchdog\n  summary\n  status\n  trips-report\n  trip-issue`);
  }
}

main().catch((error) => {
  logger.error('Ejecución fallida', { command, error: (error as Error).stack ?? (error as Error).message });
  process.exitCode = 1;
});
