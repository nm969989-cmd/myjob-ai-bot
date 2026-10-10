import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');
const trackerPath = path.join(rootDir, 'applied_jobs.json');

// In-memory state for scanner
const scannerState = {
  lastScanAt: null,
  status: 'idle',
  detectedUpdates: [],
  lastMessage: 'Scanner ready. Configure BOT_EMAIL and BOT_EMAIL_PASSWORD to enable automated IMAP scans.'
};

/**
 * Get current inbox scanner status
 */
export function getInboxScannerStatus() {
  const botEmail = process.env.BOT_EMAIL || '';
  const hasPassword = Boolean(process.env.BOT_EMAIL_PASSWORD || process.env.BOT_PASSWORD);
  
  return {
    isConfigured: Boolean(botEmail && hasPassword),
    botEmail: botEmail ? `${botEmail.slice(0, 3)}***@${botEmail.split('@')[1] || 'gmail.com'}` : 'Not Configured',
    status: scannerState.status,
    lastScanAt: scannerState.lastScanAt,
    lastMessage: scannerState.lastMessage,
    detectedCount: scannerState.detectedUpdates.length,
    recentDetections: scannerState.detectedUpdates.slice(0, 5)
  };
}

/**
 * Scan candidate inbox for interview responses and assessment links
 */
export async function scanCandidateInbox(options = {}) {
  const botEmail = process.env.BOT_EMAIL;
  const botPassword = process.env.BOT_EMAIL_PASSWORD || process.env.BOT_PASSWORD;

  scannerState.status = 'scanning';
  scannerState.lastScanAt = new Date().toISOString();

  if (!botEmail || !botPassword) {
    scannerState.status = 'idle';
    scannerState.lastMessage = 'IMAP credentials not set. Add BOT_EMAIL and BOT_EMAIL_PASSWORD in .env';
    
    // Check if there are existing applied jobs to simulate status audit
    let existingJobs = [];
    try {
      if (fs.existsSync(trackerPath)) {
        existingJobs = JSON.parse(fs.readFileSync(trackerPath, 'utf8'));
      }
    } catch (e) {}

    return {
      success: true,
      configured: false,
      message: 'Email credentials not configured in environment. Provide a Gmail App Password to enable live auto-monitoring.',
      detectedCount: 0,
      detections: []
    };
  }

  try {
    // If credentials are present, we can execute the Python imap scanner securely
    const { exec } = await import('child_process');
    const { promisify } = await import('util');
    const execAsync = promisify(exec);

    console.log('[Inbox Scanner] Connecting to IMAP server...');
    const script = `
import json, os
from imap_handler import scan_for_interview_invites
try:
    results = scan_for_interview_invites()
    print("RESULTS_JSON:" + json.dumps(results))
except Exception as e:
    print("ERROR:" + str(e))
`;
    const { stdout, stderr } = await execAsync(`python3 -c '${script}'`, { timeout: 25000 });
    
    if (stdout.includes('RESULTS_JSON:')) {
      const jsonStr = stdout.split('RESULTS_JSON:')[1].trim();
      const detected = JSON.parse(jsonStr);
      scannerState.status = 'idle';
      scannerState.detectedUpdates = detected;
      scannerState.lastMessage = `Scanned successfully. Detected ${detected.length} status updates.`;
      
      return {
        success: true,
        configured: true,
        detectedCount: detected.length,
        detections: detected
      };
    } else {
      scannerState.status = 'idle';
      scannerState.lastMessage = stdout.trim() || stderr.trim();
      return {
        success: true,
        configured: true,
        detectedCount: 0,
        detections: [],
        rawOutput: stdout.slice(0, 200)
      };
    }
  } catch (err) {
    console.error('[Inbox Scanner] Scan error:', err.message);
    scannerState.status = 'error';
    scannerState.lastMessage = `Connection error: ${err.message}`;
    return {
      success: false,
      error: err.message
    };
  }
}
