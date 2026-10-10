/**
 * Telegram Notification and Job Alert Dispatcher
 * Connects directly to Telegram Bot API with zero external dependencies
 */

export function getTelegramConfig() {
  const token = process.env.BOT_TOKEN || '';
  const chatId = process.env.TELEGRAM_CHAT_ID || '';
  const channelId = process.env.CHANNEL_ID || '@myjob_tamilnadu';

  return {
    isConfigured: Boolean(token),
    tokenMasked: token ? `${token.slice(0, 5)}...${token.slice(-4)}` : 'Not Configured',
    chatId: chatId || 'Not set',
    channelId: channelId
  };
}

export async function checkTelegramBotHealth() {
  const token = process.env.BOT_TOKEN;
  if (!token) {
    return {
      configured: false,
      status: 'idle',
      message: 'BOT_TOKEN is not set in environment. Add BOT_TOKEN in .env to activate direct Telegram alerts.'
    };
  }

  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/getMe`, {
      signal: AbortSignal.timeout(5000)
    });
    const data = await res.json();
    if (data.ok) {
      return {
        configured: true,
        status: 'online',
        botName: data.result?.first_name,
        username: `@${data.result?.username}`
      };
    } else {
      return {
        configured: true,
        status: 'error',
        message: data.description
      };
    }
  } catch (err) {
    return {
      configured: true,
      status: 'offline',
      message: err.message
    };
  }
}

/**
 * Format a job into high-engagement Telegram message
 */
export function formatJobForTelegram(job) {
  const role = job.role || job.title || 'Software Engineer';
  const company = job.company || 'Tech Employer';
  const location = job.location || 'Chennai, Tamil Nadu';
  const city = job.city || 'Tamil Nadu';
  const link = job.apply_url || job.link || 'https://linkedin.com';
  const source = job.source || 'Tamil Nadu Job Radar';
  const skills = Array.isArray(job.skills) ? job.skills.slice(0, 5).join(', ') : (job.skills || 'Engineering');
  const batch = job.batch || 'All Batches';

  return `💼 *NEW VERIFIED TECH OPENING*

🏢 *Company:* ${company}
🎯 *Role:* ${role}
📍 *Location:* ${location} (⭐ ${city})
🎓 *Batch:* ${batch}
🏷️ *Key Skills:* ${skills}
📡 *Source:* ${source}

🔗 *Apply Official Link:*
${link}

━━━━━━━━━━━━━━━━━━━
_Shared via MyJob AI Radar — Tamil Nadu_`;
}

/**
 * Send a specific job to Telegram
 */
export async function sendJobToTelegram(job, destination) {
  const token = process.env.BOT_TOKEN;
  const target = destination || process.env.TELEGRAM_CHAT_ID || process.env.CHANNEL_ID;

  if (!token) {
    return {
      success: false,
      message: 'Telegram BOT_TOKEN is not configured in .env'
    };
  }
  if (!target) {
    return {
      success: false,
      message: 'Neither TELEGRAM_CHAT_ID nor destination chat provided.'
    };
  }

  const text = formatJobForTelegram(job);

  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: target,
        text: text,
        parse_mode: 'Markdown',
        disable_web_page_preview: false
      }),
      signal: AbortSignal.timeout(8000)
    });

    const data = await res.json();
    if (data.ok) {
      return {
        success: true,
        messageId: data.result?.message_id,
        chat: data.result?.chat?.title || data.result?.chat?.username || target
      };
    } else {
      return {
        success: false,
        error: data.description
      };
    }
  } catch (err) {
    return {
      success: false,
      error: err.message
    };
  }
}
