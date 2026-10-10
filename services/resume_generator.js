import { PDFDocument, rgb, StandardFonts } from 'pdf-lib';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');
const profilePath = path.join(rootDir, 'profile.json');

/**
 * Load candidate profile with sensible defaults
 */
export function loadCandidateProfile() {
  try {
    if (fs.existsSync(profilePath)) {
      const data = JSON.parse(fs.readFileSync(profilePath, 'utf8'));
      if (data && data.full_name) return data;
    }
  } catch (err) {
    console.error('[Resume Generator] Error loading profile.json:', err.message);
  }

  return {
    full_name: 'Karthik Subramanian',
    first_name: 'Karthik',
    email: 'karthik.subramanian@gmail.com',
    phone: '+91 98401 23456',
    location: 'Chennai, Tamil Nadu',
    degree: 'B.E. Computer Science & Engineering',
    batch: '2025 Batch',
    college: 'Anna University (CEG), Chennai',
    cgpa: '8.6 CGPA',
    experience_years: '0-1 Year (Fresher)',
    skills: 'Python, SQL, React, Node.js, REST APIs, Git, Tailwind CSS, Problem Solving',
    linkedin: 'https://linkedin.com/in/karthik-dev',
    github: 'https://github.com/karthik-tn',
    portfolio: 'https://karthik-dev.github.io',
    about: 'Passionate Software Engineer skilled in full-stack web applications, clean architecture, and problem solving. Eager to contribute to innovative tech teams in Tamil Nadu.'
  };
}

/**
 * Generate a pristine, 1-page ATS-compliant PDF resume from profile.json
 * @param {Object} options - Optional tailoring overrides (role, company, targetSkills)
 */
export async function generateResumePdf(options = {}) {
  const profile = { ...loadCandidateProfile(), ...options.profile };
  const targetRole = options.role || 'Software Engineer';
  const targetCompany = options.company || '';

  const doc = await PDFDocument.create();
  // Standard A4 dimensions in points: 595.28 x 841.89
  const page = doc.addPage([595.28, 841.89]);
  
  const fontRegular = await doc.embedFont(StandardFonts.Helvetica);
  const fontBold = await doc.embedFont(StandardFonts.HelveticaBold);
  const fontItalic = await doc.embedFont(StandardFonts.HelveticaOblique);

  // Palette: Clean Navy & Charcoal for maximum ATS readability
  const cNavy = rgb(0.08, 0.18, 0.36);
  const cDark = rgb(0.15, 0.15, 0.18);
  const cMuted = rgb(0.40, 0.42, 0.48);
  const cAccent = rgb(0.12, 0.45, 0.75);

  let y = 805;
  const leftX = 45;
  const contentWidth = 505;

  // ── HEADER SECTION ────────────────────────────────────────────────────────
  const name = (profile.full_name || 'Candidate Name').toUpperCase();
  page.drawText(name, {
    x: leftX,
    y,
    size: 20,
    font: fontBold,
    color: cNavy
  });

  y -= 16;
  const subTitle = targetCompany ? `${targetRole} Applicant · ${profile.degree}` : (profile.degree || 'Software Engineer');
  page.drawText(subTitle, {
    x: leftX,
    y,
    size: 10,
    font: fontBold,
    color: cAccent
  });

  y -= 15;
  const contactParts = [
    profile.location || 'Tamil Nadu, India',
    profile.phone || '+91 98401 23456',
    profile.email || 'applicant@example.com'
  ].filter(Boolean);
  page.drawText(contactParts.join('  •  '), {
    x: leftX,
    y,
    size: 9,
    font: fontRegular,
    color: cDark
  });

  y -= 13;
  const linkParts = [
    profile.linkedin ? `LinkedIn: ${profile.linkedin.replace(/^https?:\/\//, '')}` : '',
    profile.github ? `GitHub: ${profile.github.replace(/^https?:\/\//, '')}` : '',
    profile.portfolio ? `Portfolio: ${profile.portfolio.replace(/^https?:\/\//, '')}` : ''
  ].filter(Boolean);
  if (linkParts.length > 0) {
    page.drawText(linkParts.join('  •  '), {
      x: leftX,
      y,
      size: 8.5,
      font: fontRegular,
      color: cMuted
    });
  }

  // Divider line
  y -= 10;
  page.drawLine({
    start: { x: leftX, y },
    end: { x: leftX + contentWidth, y },
    thickness: 1,
    color: rgb(0.85, 0.88, 0.92)
  });

  // Helper for section header
  function drawSectionHeader(title) {
    y -= 18;
    page.drawText(title.toUpperCase(), {
      x: leftX,
      y,
      size: 10,
      font: fontBold,
      color: cNavy
    });
    y -= 4;
    page.drawLine({
      start: { x: leftX, y },
      end: { x: leftX + contentWidth, y },
      thickness: 0.75,
      color: cAccent
    });
    y -= 10;
  }

  // ── PROFESSIONAL SUMMARY ──────────────────────────────────────────────────
  drawSectionHeader('Professional Summary');
  const summaryText = profile.about || 
    `Results-driven ${targetRole} with strong foundations in software development, data structures, and modern web frameworks. Proven ability to build responsive applications and scalable backend APIs. Fast learner and active problem solver eager to bring technical dedication to innovative engineering teams.`;
  
  // Simple word-wrap helper
  function drawWrappedText(text, x, startY, maxWidth, fontSize, font, color, lineHeight = 12) {
    const words = text.split(' ');
    let line = '';
    let currY = startY;

    for (const word of words) {
      const testLine = line + (line ? ' ' : '') + word;
      const testWidth = font.widthOfTextAtSize(testLine, fontSize);
      if (testWidth > maxWidth && line) {
        page.drawText(line, { x, y: currY, size: fontSize, font, color });
        line = word;
        currY -= lineHeight;
      } else {
        line = testLine;
      }
    }
    if (line) {
      page.drawText(line, { x, y: currY, size: fontSize, font, color });
      currY -= lineHeight;
    }
    return currY;
  }

  y = drawWrappedText(summaryText, leftX, y, contentWidth, 9, fontRegular, cDark, 12);

  // ── TECHNICAL SKILLS ──────────────────────────────────────────────────────
  drawSectionHeader('Technical Skills');
  const rawSkills = profile.skills || 'Python, React, Node.js, SQL, JavaScript, Git, REST APIs';
  const skillList = rawSkills.split(',').map(s => s.trim()).filter(Boolean);

  const skillGroups = [
    { label: 'Core Languages', items: skillList.filter(s => /python|java|javascript|typescript|c\+\+|sql|go/i.test(s)) },
    { label: 'Frameworks & Web', items: skillList.filter(s => /react|node|express|django|flask|angular|vue|tailwind|html|css/i.test(s)) },
    { label: 'Tools & Practices', items: skillList.filter(s => /git|docker|rest|api|linux|cloud|aws|ci|cd|agile|testing/i.test(s)) }
  ];

  for (const grp of skillGroups) {
    const items = grp.items.length > 0 ? grp.items.join(', ') : skillList.slice(0, 4).join(', ');
    page.drawText(`•  ${grp.label}: `, { x: leftX, y, size: 8.5, font: fontBold, color: cDark });
    const labelW = fontBold.widthOfTextAtSize(`•  ${grp.label}: `, 8.5);
    page.drawText(items, { x: leftX + labelW, y, size: 8.5, font: fontRegular, color: cDark });
    y -= 12;
  }

  // ── PROJECTS & EXPERIENCE ─────────────────────────────────────────────────
  drawSectionHeader('Projects & Engineering Experience');
  
  const projects = [
    {
      title: 'Tamil Nadu Live Job Radar & Autonomous Applier System',
      role: 'Full-Stack Developer',
      tech: 'Node.js, Express, Firebase Firestore, Playwright, Tailwind CSS',
      bullets: [
        'Built an autonomous radar pipeline ingesting 350+ regional engineering vacancies across Tamil Nadu tech hubs.',
        'Engineered background scrapers with multi-district concurrency, exponential backoff, and Firestore persistence.',
        'Designed real-time ATS keyword relevance scoring and 1-click tailored application dispatch.'
      ]
    },
    {
      title: 'Enterprise Candidate Automation & Interview Tracker',
      role: 'Backend Engineer',
      tech: 'Python, REST APIs, IMAP Protocol, Regex, SQLite',
      bullets: [
        'Developed an autonomous inbox monitoring engine parsing interview invitations and status changes.',
        'Integrated dynamic PDF compilation adhering to strict ATS single-page parsing standards.'
      ]
    }
  ];

  for (const proj of projects) {
    page.drawText(proj.title, { x: leftX, y, size: 9.5, font: fontBold, color: cNavy });
    const roleText = `[${proj.role}]`;
    const rW = fontItalic.widthOfTextAtSize(roleText, 8.5);
    page.drawText(roleText, { x: leftX + contentWidth - rW, y, size: 8.5, font: fontItalic, color: cMuted });
    y -= 11;

    page.drawText(`Technologies: ${proj.tech}`, { x: leftX + 8, y, size: 8, font: fontItalic, color: cAccent });
    y -= 11;

    for (const b of proj.bullets) {
      page.drawText('•', { x: leftX + 8, y, size: 8.5, font: fontRegular, color: cMuted });
      y = drawWrappedText(b, leftX + 18, y, contentWidth - 18, 8.5, fontRegular, cDark, 11);
    }
    y -= 3;
  }

  // ── EDUCATION ─────────────────────────────────────────────────────────────
  drawSectionHeader('Education');
  page.drawText(profile.degree || 'Bachelor of Engineering in Computer Science', { x: leftX, y, size: 9.5, font: fontBold, color: cNavy });
  const batchText = profile.batch || '2025 Batch';
  const bW = fontRegular.widthOfTextAtSize(batchText, 8.5);
  page.drawText(batchText, { x: leftX + contentWidth - bW, y, size: 8.5, font: fontBold, color: cMuted });
  y -= 12;

  const eduDetail = `${profile.college || 'Anna University, Chennai'}  •  ${profile.cgpa || '8.6 CGPA'}`;
  page.drawText(eduDetail, { x: leftX, y, size: 8.5, font: fontRegular, color: cDark });
  y -= 12;

  // ── CERTIFICATIONS & ACHIEVEMENTS ─────────────────────────────────────────
  drawSectionHeader('Certifications & Key Strengths');
  const certs = [
    'Verified Problem Solving & Data Structures Foundations',
    'Full-Stack Web Development & Modern API Design',
    'Native Familiarity with Tamil Nadu Tech Corridor (Chennai OMR, Coimbatore Tidel Park)'
  ];
  for (const cert of certs) {
    page.drawText('•', { x: leftX + 8, y, size: 8.5, font: fontRegular, color: cAccent });
    page.drawText(cert, { x: leftX + 18, y, size: 8.5, font: fontRegular, color: cDark });
    y -= 11;
  }

  // Footer note
  y = 25;
  const footerNote = `ATS-Optimized Profile  •  Generated for ${targetCompany ? `${targetCompany} Application` : 'Tamil Nadu Tech Openings'}  •  ${profile.email}`;
  const fW = fontItalic.widthOfTextAtSize(footerNote, 7.5);
  page.drawText(footerNote, {
    x: leftX + (contentWidth - fW) / 2,
    y,
    size: 7.5,
    font: fontItalic,
    color: cMuted
  });

  const pdfBytes = await doc.save();
  return pdfBytes;
}
