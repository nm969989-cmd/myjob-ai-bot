"""
test_features_verify.py - End-to-end verification suite for Job Bot upgrades:
1. AI Skill Match Score & Resume Fit Analyzer
2. Smart Dead-Link & Expired Job Filter
3. 1-Tap Interview Prep Cheat Sheet Generator
4. Live Career & Market Analytics Dashboard
5. RAG Memory & Salary Extraction
"""
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath("."))

from bot_optimizer import (
    calculate_skill_match_score,
    is_job_link_alive,
    generate_fast_interview_cheat_sheet,
    generate_market_analytics_report,
    extract_job_salary,
    extract_hr_email,
    generate_linkedin_outreach_note,
    extract_eligible_batch,
    extract_experience_level,
    format_eligibility_badge
)

def run_all_tests():
    print("==================================================")
    print("🚀 JOB BOT ENHANCEMENT VERIFICATION SUITE")
    print("==================================================")

    # 1. Skill Match Score & Resume Fit
    mock_profile = {"skills": "Python, SQL, React, Django, Git, REST API"}
    job_post_1 = """
    Software Engineer Fresher - Bangalore
    Requirements: Strong proficiency in Python and Django or FastAPI. Good knowledge of SQL and Git.
    Familiarity with AWS and Docker is a plus.
    """
    res1 = calculate_skill_match_score(job_post_1, mock_profile)
    assert res1['score'] >= 50
    assert "PYTHON" in [s.upper() for s in res1['matched']]
    assert "SQL" in [s.upper() for s in res1['matched']]
    print(f"✅ Skill Match Test: Score {res1['score']}% | Badge: {res1['badge']}")

    # 2. Dead-Link Probe
    live_ok = is_job_link_alive("https://t.me/s/tech_jobs_india", timeout=3.0)
    assert live_ok is True
    bad_ok = is_job_link_alive("not_a_valid_url")
    assert bad_ok is False
    print("✅ Dead-Link Filter Test: Verified live vs invalid handling.")

    # 3. 1-Tap Interview Prep
    sheet = generate_fast_interview_cheat_sheet("Razorpay", "Python Backend Developer", ["Python", "Django", "SQL"])
    assert "Razorpay" in sheet
    assert "Q1:" in sheet
    print("✅ 1-Tap Interview Prep Test: Generated tailored cheat sheet.")

    # 4. Live Market Analytics
    report = generate_market_analytics_report(".")
    assert "CAREER & MARKET INTELLIGENCE REPORT" in report
    assert "Python" in report
    print("✅ Live Market Analytics Test: Generated executive report with ASCII bars.")

    # 5. Salary & HR Email Extraction
    sample_text = "Urgent Hiring at TCS! Role: Associate Software Engineer. Expected CTC: 4.5 - 7.5 LPA. Send CV to careers@tcs.com"
    sal = extract_job_salary(sample_text)
    em = extract_hr_email(sample_text)
    assert "4.5" in sal
    assert "careers@tcs.com" in em
    print(f"✅ Salary & HR Email Test: Salary='{sal}', Email='{em}'")

    # 6. National Mass Off-Campus Drives Radar
    from bot_optimizer import get_national_drives, format_national_drives_report, format_single_drive_detail
    drives = get_national_drives("national_drives.json")
    assert len(drives) >= 15
    chunks = format_national_drives_report(drives)
    assert len(chunks) >= 1
    assert "TCS NQT" in chunks[0]
    assert "Zoho" in chunks[0]
    assert "Infosys" in chunks[0]

    # Test single drive syllabus and exam pattern
    tcs_card, tcs_link = format_single_drive_detail("tcs_nqt", "national_drives.json")
    assert "Syllabus" in tcs_card
    assert "http" in tcs_link.lower()

    # Test batch filtering
    filtered_2025 = format_national_drives_report(drives, query="2025")
    assert len(filtered_2025) >= 1
    assert "2025" in filtered_2025[0]

    filtered_zoho = format_national_drives_report(drives, query="zoho")
    assert len(filtered_zoho) >= 1
    assert "Zoho" in filtered_zoho[0]

    print(f"✅ National Mass Drives Test: Verified {len(drives)} drives, batch filtering, and single-drive syllabus breakdown.")

    # 7. Mass Drive Deadline & Countdown Radar Test
    from bot_optimizer import parse_drive_deadline, get_all_drive_deadlines, format_deadlines_radar_report, get_urgent_deadlines_summary
    sample_ref = "2026-09-27"
    deadlines = get_all_drive_deadlines("national_drives.json", ref_date=sample_ref)
    assert len(deadlines) >= 15
    # Closest should be cognizant (Sep 30 -> 3 days) or mindgate (Oct 1 -> 4 days)
    assert deadlines[0]["days_left"] <= 4
    assert deadlines[0]["urgency_tier"] == "critical"
    
    # Urgent filter report
    urgent_chunks = format_deadlines_radar_report("national_drives.json", urgent_only=True, ref_date=sample_ref)
    assert len(urgent_chunks) >= 1
    assert "CRITICAL" in urgent_chunks[0]

    # Full report
    all_chunks = format_deadlines_radar_report("national_drives.json", urgent_only=False, ref_date=sample_ref)
    assert len(all_chunks) >= 1
    assert "NATIONAL MASS DRIVES DEADLINE RADAR" in all_chunks[0]

    # Summary
    summary = get_urgent_deadlines_summary("national_drives.json", ref_date=sample_ref)
    assert "URGENT" in summary

    print(f"✅ Mass Drive Deadlines Radar Test: Verified {len(deadlines)} countdowns and urgency tiers.")

    # 8. Eligible Batch Year & Experience Level Tagging
    tcs_sample = "TCS Off Campus Drive 2025\nRole: Systems Engineer\nYear of Passing: 2024, 2025 & 2026 Batch\nExperience: Freshers (0-1 Years)"
    b1 = extract_eligible_batch(tcs_sample)
    e1 = extract_experience_level(tcs_sample)
    badge1 = format_eligibility_badge(b1, e1)
    assert "2024" in b1 and "2026" in b1
    assert "Freshers" in e1
    assert "🎓" in badge1 and "💼" in badge1

    cog_sample = "Cognizant GenC\nBatch: 2025 Passouts Only\nExp: 0 - 2 yrs"
    b2 = extract_eligible_batch(cog_sample)
    e2 = extract_experience_level(cog_sample)
    assert "2025" in b2
    assert "0-2" in e2

    print(f"✅ Eligible Batch & Experience Tag Test: Batch='{b1}', Exp='{e1}' | Badge: '{badge1}'")

    # 9. Tamil Nadu Job Radar & Telegram Formatting
    from job_radar import get_tamil_nadu_jobs, format_tamil_nadu_telegram_digest
    tn_jobs = get_tamil_nadu_jobs(limit=3, force_refresh=False)
    assert len(tn_jobs) > 0
    chunks, markup = format_tamil_nadu_telegram_digest(tn_jobs)
    assert len(chunks) > 0
    assert markup is not None
    assert "TAMIL NADU" in chunks[0]

    print(f"✅ Tamil Nadu Job Radar Test: Retrieved {len(tn_jobs)} TN jobs & verified card formatting.")

    # 10. Tamil Nadu Weekend Walk-In Tracker (/walkins)
    from bot_optimizer import get_walkin_drives, format_walkins_report, format_single_walkin_detail
    all_walkins = get_walkin_drives()
    assert len(all_walkins) >= 6, f"Expected at least 6 verified walk-in drives, got {len(all_walkins)}"
    
    # City filters
    chennai_walkins = get_walkin_drives(city="chennai")
    assert len(chennai_walkins) > 0
    coimbatore_walkins = get_walkin_drives(city="coimbatore")
    assert len(coimbatore_walkins) > 0
    
    # Report formatting
    w_chunks = format_walkins_report(all_walkins)
    assert len(w_chunks) > 0
    assert "WALK-IN" in w_chunks[0]
    assert "Tech Mahindra" in w_chunks[0]
    
    # Single drive detail
    single_detail = format_single_walkin_detail("tech_mahindra_sholinganallur")
    assert "Tech Mahindra" in single_detail
    assert "Google Maps" in single_detail
    assert "ELCOT SEZ" in single_detail

    print(f"✅ Weekend Walk-In Tracker Test: Verified {len(all_walkins)} drives (Chennai: {len(chennai_walkins)}, Coimbatore: {len(coimbatore_walkins)}) & Maps links.")

    # 11. Automated Walk-In Dispatch Test (Mock Bot)
    from unittest.mock import MagicMock
    from bot_optimizer import dispatch_walkin_alerts
    mock_bot = MagicMock()
    mock_chat_id = "test_chat_987"
    # Test dispatch with force (once_per_day=False)
    dispatch_success = dispatch_walkin_alerts(bot=mock_bot, chat_id=mock_chat_id, once_per_day=False, limit=3)
    assert dispatch_success is True
    assert mock_bot.send_message.called
    sent_args, sent_kwargs = mock_bot.send_message.call_args
    assert sent_args[0] == mock_chat_id
    assert "WALK-IN" in str(sent_args[1])
    print(f"✅ Automated Walk-In Dispatch Test: Successfully tested simulated bot delivery ({mock_bot.send_message.call_count} messages sent).")

    print("\n🎉 ALL VERIFICATION CHECKS PASSED WITH ZERO ERRORS!\n")

if __name__ == "__main__":
    run_all_tests()

