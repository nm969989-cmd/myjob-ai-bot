import unittest
from bot_optimizer import (
    analyze_jd_skill_gap,
    calculate_skill_match_score,
    check_ats_liveness_api,
    format_skill_gap_report,
    store_gap_cache,
    get_gap_cache,
    is_job_link_alive
)

class TestCareerOpsIntegration(unittest.TestCase):

    def setUp(self):
        self.profile = {
            "name": "Manoj",
            "skills": "Python, SQL, React, Git, REST API",
            "experience": "Developed scalable microservices using Docker on AWS cloud.",
            "projects": "Full-stack web application using FastAPI and Tailwind CSS."
        }

    def test_3_bucket_skill_gap_analysis(self):
        jd = """
        Role: Associate Software Engineer
        Location: Chennai, Tamil Nadu
        Requirements:
        - Strong coding skills in Python and SQL.
        - Experience building applications with Docker and AWS.
        - Knowledge of Kubernetes and Redis is highly preferred.
        - Good understanding of Git.
        """
        analysis = analyze_jd_skill_gap(jd, self.profile)
        
        # 1. Existing skills (explicit in skills)
        self.assertIn("PYTHON", [s.upper() for s in analysis["existing"]])
        self.assertIn("SQL", [s.upper() for s in analysis["existing"]])
        self.assertIn("GIT", [s.upper() for s in analysis["existing"]])

        # 2. Supported by resume prose (experience/projects)
        self.assertIn("DOCKER", [s.upper() for s in analysis["supported"]])
        self.assertIn("AWS", [s.upper() for s in analysis["supported"]])

        # 3. Gaps (in JD but absent from profile)
        self.assertIn("KUBERNETES", [s.upper() for s in analysis["gap"]])
        self.assertIn("REDIS", [s.upper() for s in analysis["gap"]])

        # 4. Conviction metric
        self.assertGreaterEqual(analysis["star_rating"], 3.5)
        self.assertEqual(analysis["conviction"], "HIGH")
        self.assertIn("⭐", analysis["star_badge"])

    def test_backward_compatibility_calculate_skill_match_score(self):
        jd = "Hiring React and Node.js Developer in Chennai"
        res = calculate_skill_match_score(jd, self.profile)
        self.assertIn("score", res)
        self.assertIn("matched", res)
        self.assertIn("missing", res)
        self.assertIn("badge", res)
        self.assertIn("job_skills", res)
        self.assertIn("star_rating", res)
        self.assertIn("conviction", res)
        self.assertIn("existing", res)
        self.assertIn("supported", res)
        self.assertIn("gap", res)

    def test_format_skill_gap_report(self):
        analysis = {
            "existing": ["Python", "SQL"],
            "supported": ["Docker"],
            "gap": ["Kubernetes"],
            "star_badge": "⭐⭐⭐⭐ 4.2/5.0 Elite Fit",
            "conviction": "HIGH",
            "recommendation": "Great match! Apply immediately."
        }
        report = format_skill_gap_report("Freshworks", "Software Engineer", analysis)
        self.assertIn("Freshworks", report)
        self.assertIn("Existing Resume Skills", report)
        self.assertIn("Python", report)
        self.assertIn("Identified Skill Gaps", report)
        self.assertIn("Kubernetes", report)

    def test_shared_gap_cache(self):
        store_gap_cache("test_key_123", {"company": "Zoho", "score": 90})
        cached = get_gap_cache("test_key_123")
        self.assertEqual(cached.get("company"), "Zoho")

    def test_zero_token_ats_liveness(self):
        # Invalid / non-existent smartrecruiters posting returns False
        bad_sr = check_ats_liveness_api("https://jobs.smartrecruiters.com/Freshworks/invalid_fake_id_99999")
        self.assertFalse(bad_sr)

        # Non-ATS URL returns None (fall back to standard stream probe)
        non_ats = check_ats_liveness_api("https://t.me/s/tech_jobs_india")
        self.assertIsNone(non_ats)

        # Standard link check still succeeds
        is_live = is_job_link_alive("https://t.me/s/tech_jobs_india", timeout=3.0)
        self.assertTrue(is_live)

if __name__ == "__main__":
    unittest.main()
