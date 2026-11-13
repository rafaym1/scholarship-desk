"""Offline tests. Run:  python -m unittest discover -s tests"""
from __future__ import annotations

import copy
import http.client
import http.server
import json
import os
import shutil
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT))

from scholar import (applications, countries, doccheck, drafts, library, opportunity as opp,  # noqa: E402
                     profile as prof, queries, registry, store, timeline, watch)

TODAY = date.today().isoformat()
DEADLINE = (date.today() + timedelta(days=120)).isoformat()  # always in the future
FIXED_NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)  # only for tests that need a fixed clock


class TempHome(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="scholar-test-"))
        self._old = os.environ.get("SCHOLAR_HOME")
        os.environ["SCHOLAR_HOME"] = str(self.home)

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("SCHOLAR_HOME", None)
        else:
            os.environ["SCHOLAR_HOME"] = self._old
        shutil.rmtree(self.home, ignore_errors=True)

    # ------------------------------------------------------------- fixtures
    def base_profile(self, **values: str) -> dict:
        p = prof.load()
        defaults = {
            "identity.citizenships": "Pakistan", "identity.country_of_residence": "Canada",
            "identity.residence_status": "study permit", "target.levels": "masters, phd",
            "target.regions": "europe, scandinavia, north_america, australia",
            "target.fields": "Computer Science", "target.start_term": "2027-09",
        }
        defaults.update(values)
        for key, value in defaults.items():
            result = prof.set_value(p, key, value)
            assert result["ok"], (key, result)
        return p

    def record(self, **overrides) -> dict:
        rec = {
            "title": "Test Excellence Scholarship", "sponsor": "Test Foundation", "type": "scholarship",
            "levels": ["masters"], "region": "scandinavia", "host_countries": ["Sweden"],
            "source_kind": "official", "official_url": "https://test-foundation.example/award",
            "authority_url": "https://test-foundation.example/about",
            "apply_url": "https://test-foundation.example/apply", "verified_at": TODAY,
            "deadline": {"type": "fixed", "date": DEADLINE, "timezone": "Europe/Stockholm"},
            "fees": {"scholarship_fee": False, "is_loan": False, "is_lottery": False},
            "country_rule": {"basis": "citizenship", "exclude": ["@eea"], "quote": "Non-EU/EEA citizens."},
            "amount": {"text": "Full tuition", "full_funding": True},
            "application": {"method": "web_form", "documents": ["cv", "transcript"], "references": 1,
                            "questions": [{"prompt": "Why this programme?", "limit": 50}]},
        }
        for key, value in overrides.items():
            rec[key] = value
        return rec

    def evaluate(self, rec: dict, p: dict, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        clean, errors, _ = opp.validate(rec, now.date())
        self.assertEqual(errors, [], errors)
        return opp.evaluate(clean, p, now)


class ProfileTests(TempHome):
    def test_country_names_and_nationality_hint(self):
        p = prof.load()
        bad = prof.set_value(p, "identity.citizenships", "Pakistani")
        self.assertFalse(bad["ok"])
        self.assertIn("Pakistan", bad["error"])
        ok = prof.set_value(p, "identity.citizenships", "UK; Holland")
        self.assertEqual(ok["value"], ["United Kingdom", "Netherlands"])

    def test_sensitive_values_refused(self):
        p = prof.load()
        for text in ("SIN 123 456 789", "ssn 123-45-6789", "card 4111 1111 1111 1111",
                     "password: hunter2", "passport number AB1234567", "IBAN DE89370400440532013000"):
            result = prof.set_value(p, "narrative.other", text)
            self.assertFalse(result["ok"], text)
            self.assertIn("NOT SAVED", result["error"])

    def test_phone_numbers_are_not_mistaken_for_cards(self):
        p = prof.load()
        self.assertTrue(prof.set_value(p, "identity.phone", "+4915112345678")["ok"])
        self.assertTrue(prof.set_value(p, "identity.phone", "+1 250 555 0100")["ok"])

    def test_choices_and_synonyms(self):
        p = prof.load()
        self.assertEqual(prof.set_value(p, "target.levels", "Master's, Ph.D")["value"], ["masters", "phd"])
        self.assertEqual(prof.set_value(p, "target.regions", "Nordics, North America")["value"],
                         ["scandinavia", "north_america"])

    def test_derived_facts(self):
        p = self.base_profile(**{"identity.date_of_birth": "2000-06-15"})
        prof.list_add(p, "education", {"institution": "U", "degree": "BSc Computer Science",
                                       "status": "completed", "end": "2023-05", "gpa": "3.5", "gpa_scale": "4"})
        prof.list_add(p, "experience", {"organization": "A", "role": "Dev", "start": "2023-06",
                                        "end": "2024-06", "fte": "0.5"})
        prof.list_add(p, "experience", {"organization": "Lab", "role": "Intern", "start": "2023-01",
                                        "end": "2023-03"})  # during the degree
        prof.list_add(p, "experience", {"organization": "B", "role": "Engineer", "start": "2026-08"})
        prof.list_add(p, "tests", {"exam": "IELTS Academic", "score": "7.5"})
        f = prof.facts(p, date(2026, 11, 11))
        self.assertEqual(f["derived.age"], 26)
        self.assertEqual(f["derived.highest_degree"], "bachelors")
        self.assertFalse(f["derived.has_masters"])
        # 13 months x 0.5 (Jun 2023–Jun 2024 inclusive) + 3 (Jan–Mar) + 3 (Aug–Oct; November not finished)
        self.assertEqual(f["derived.work_months"], 12.5)
        self.assertEqual(f["derived.work_months_after_degree"], 9.5)  # the internship during the degree is left out
        self.assertEqual(f["derived.score.ielts"], 7.5)
        self.assertEqual(f["derived.gpa_percent"], 87.5)

    def test_application_fee_label(self):
        p = self.base_profile()
        base = self.record()
        self.assertEqual(self.evaluate(base, p)["fee"]["status"], "unknown")
        paid = self.record(fees={"scholarship_fee": False, "is_loan": False, "is_lottery": False,
                                 "application_fee": True, "application_fee_amount": "CAD 135",
                                 "application_fee_note": "University application"})
        fee = self.evaluate(paid, p)["fee"]
        self.assertEqual((fee["status"], fee["amount"], fee["note"]), ("fee", "CAD 135", "University application"))
        self.assertEqual(self.evaluate(paid, p)["bucket"], "eligible")  # a university fee is normal, not a red flag
        free = self.record(fees={"scholarship_fee": False, "is_loan": False, "is_lottery": False,
                                 "application_fee": False})
        self.assertEqual(self.evaluate(free, p)["fee"]["status"], "no_fee")
        _, errors, _ = opp.validate(self.record(fees={"application_fee": "yes"}), date.today())
        self.assertTrue(any("application_fee" in e for e in errors))

    def test_residence_months(self):
        p = self.base_profile()
        prof.list_add(p, "residence", {"country": "Sweden", "from": "2025-01", "to": "2025-07"})
        self.assertEqual(prof.residence_months(p, "Sweden", 3, date(2026, 11, 11)), 7)  # Jan–Jul inclusive
        prof.list_add(p, "residence", {"country": "Canada", "from": "2024-06", "to": "2024-08"})
        self.assertEqual(prof.residence_months(p, "Canada", 5, date(2026, 11, 11)), 3)
        self.assertEqual(prof.residence_months(p, "Canada", 2, date(2026, 11, 11)), 0)  # outside window
        self.assertEqual(prof.residence_months(p, "Norway", 3, date(2026, 11, 11)), 0)


class EligibilityTests(TempHome):
    def test_eligible_and_agent_mode(self):
        ev = self.evaluate(self.record(), self.base_profile())
        self.assertEqual(ev["bucket"], "eligible")
        self.assertEqual(ev["country"]["status"], "eligible")
        self.assertEqual(ev["apply_mode"], "agent")

    def test_unknown_fee_needs_confirmation(self):
        rec = self.record(fees={"scholarship_fee": None, "is_loan": False, "is_lottery": False})
        ev = self.evaluate(rec, self.base_profile())
        self.assertEqual(ev["bucket"], "needs_confirmation")

    def test_scholarship_fee_rejected(self):
        rec = self.record(fees={"scholarship_fee": True, "is_loan": False, "is_lottery": False})
        self.assertEqual(self.evaluate(rec, self.base_profile())["bucket"], "rejected")

    def test_country_allowlist_excludes(self):
        rec = self.record(country_rule={"basis": "citizenship", "include": ["India"], "quote": "Indian citizens."})
        ev = self.evaluate(rec, self.base_profile())
        self.assertEqual(ev["bucket"], "ineligible")
        self.assertEqual(ev["country"]["status"], "ineligible")

    def test_dual_citizenship_ambiguous_then_resolved(self):
        p = self.base_profile(**{"identity.citizenships": "Pakistan; Germany"})
        ev = self.evaluate(self.record(), p)
        self.assertEqual(ev["country"]["status"], "unclear")
        self.assertEqual(ev["bucket"], "needs_confirmation")
        strict = self.record(country_rule={"basis": "citizenship", "exclude": ["@eea"], "quote": "q",
                                           "dual_citizenship": "all_must_be_eligible"})
        self.assertEqual(self.evaluate(strict, p)["bucket"], "ineligible")
        lenient = self.record(country_rule={"basis": "citizenship", "exclude": ["@eea"], "quote": "q",
                                            "dual_citizenship": "any_eligible"})
        self.assertEqual(self.evaluate(lenient, p)["country"]["status"], "eligible")

    def test_residence_status_rule(self):
        rule = {"basis": "citizenship_or_residence", "include": ["Canada"],
                "residence_statuses": ["permanent_resident"], "quote": "Canadian citizens or PRs."}
        rec = self.record(country_rule=rule, region="north_america", host_countries=["Canada"])
        self.assertEqual(self.evaluate(rec, self.base_profile())["bucket"], "ineligible")
        pr = self.base_profile(**{"identity.residence_status": "permanent resident"})
        self.assertEqual(self.evaluate(rec, pr)["country"]["status"], "eligible")

    def test_host_residence_rule(self):
        rule = {"basis": "open", "host_residence": {"max_months": 12, "within_years": 3}, "quote": "q"}
        p = self.base_profile()
        self.assertEqual(self.evaluate(self.record(country_rule=rule), p)["country"]["status"], "unclear")
        prof.list_add(p, "residence", {"country": "Sweden", "from": "2024-01", "to": "2025-12"})
        self.assertEqual(self.evaluate(self.record(country_rule=rule), p)["bucket"], "ineligible")

    def test_near_miss_vs_ineligible(self):
        p = self.base_profile()
        prof.list_add(p, "tests", {"exam": "IELTS Academic", "score": "6.5"})
        fixable = self.record(requirements=[{"field": "derived.score.ielts", "op": "gte", "value": 7,
                                             "fixable": True, "text": "IELTS 7.0"}])
        ev = self.evaluate(fixable, p)
        self.assertEqual(ev["bucket"], "near_miss")
        self.assertEqual(ev["gaps"], ["IELTS 7.0"])
        hard = self.record(requirements=[{"field": "derived.age", "op": "lte", "value": 20,
                                          "fixable": False, "text": "Under 20"}])
        p2 = self.base_profile(**{"identity.date_of_birth": "2000-01-01"})
        self.assertEqual(self.evaluate(hard, p2)["bucket"], "ineligible")

    def test_level_mismatch(self):
        rec = self.record(levels=["postdoc"])
        self.assertEqual(self.evaluate(rec, self.base_profile())["bucket"], "ineligible")

    def test_deadline_uses_sponsor_timezone(self):
        p = self.base_profile()
        # At 12:00 UTC on 11 Nov it is already 12 Nov in Kiritimati but still 11 Nov in Los Angeles.
        east = self.record(deadline={"type": "fixed", "date": "2026-11-11", "timezone": "Pacific/Kiritimati"},
                           verified_at="2026-11-10")
        west = self.record(deadline={"type": "fixed", "date": "2026-11-11", "timezone": "America/Los_Angeles"},
                           verified_at="2026-11-10")
        self.assertEqual(self.evaluate(east, p, FIXED_NOW)["bucket"], "expired")
        self.assertNotEqual(self.evaluate(west, p, FIXED_NOW)["bucket"], "expired")

    def test_admission_deadline_passed_expires(self):
        rec = self.record(admission={"required": True, "deadline": "2026-10-01"})
        self.assertEqual(self.evaluate(rec, self.base_profile())["bucket"], "expired")

    def test_upcoming_and_discovery(self):
        p = self.base_profile()
        self.assertEqual(self.evaluate(self.record(deadline={"type": "not_open", "opens": "2027-01-10"}), p)["bucket"],
                         "upcoming")
        lead = self.record(source_kind="discovery", official_url="https://www.scholars4dev.com/x",
                           authority_url=None, country_rule=None)
        self.assertEqual(self.evaluate(lead, p)["bucket"], "unverified")

    def test_scope_notes(self):
        p = self.base_profile(**{"target.regions": "europe"})
        ev = self.evaluate(self.record(), p)
        self.assertFalse(ev["in_scope"])


class ValidationTests(TempHome):
    def test_missing_time_zone_data_is_named(self):
        from unittest import mock

        with mock.patch.object(opp, "ZoneInfo", side_effect=LookupError("no time zone data")):
            self.assertFalse(opp.tz_data_available())
            _, errors, _ = opp.validate(self.record())
        self.assertTrue(any("pip install tzdata" in e for e in errors), errors)
        _, errors, _ = opp.validate(self.record(deadline={"type": "fixed", "date": DEADLINE, "timezone": "Mars/Base"}))
        self.assertTrue(any("not an IANA zone" in e for e in errors), errors)

    def test_aggregator_cannot_be_official(self):
        rec = self.record(official_url="https://www.scholars4dev.com/123/award", authority_url=None)
        _, errors, _ = opp.validate(rec)
        self.assertTrue(any("aggregator" in e for e in errors))

    def test_registry_domain_proves_source(self):
        rec = self.record(official_url="https://si.se/en/apply/scholarships/", authority_url=None)
        clean, errors, _ = opp.validate(rec)
        self.assertEqual(errors, [])
        self.assertEqual(clean["source_proof"], "registry")

    def test_unknown_domain_needs_authority(self):
        rec = self.record(authority_url=None)
        _, errors, _ = opp.validate(rec)
        self.assertTrue(any("authority_url" in e for e in errors))

    def test_country_rule_required_and_names_checked(self):
        _, errors, _ = opp.validate(self.record(country_rule=None))
        self.assertTrue(any("country_rule is required" in e for e in errors))
        rule = {"basis": "citizenship", "include": ["Narnia"], "quote": "q"}
        _, errors, _ = opp.validate(self.record(country_rule=rule))
        self.assertTrue(any("Narnia" in e for e in errors))

    def test_add_is_idempotent_by_title_and_sponsor(self):
        first = opp.add([self.record()])
        second = opp.add([self.record(amount={"text": "Changed"})])
        self.assertTrue(second["results"][0]["updated"])
        self.assertEqual(first["results"][0]["id"], second["results"][0]["id"])
        self.assertEqual(len(opp.load_all()), 1)


class TimelineTests(TempHome):
    def test_start_by_from_admission_and_referees(self):
        p = self.base_profile()
        rec = self.record(admission={"required": True, "deadline": "2027-01-15"},
                          deadline={"type": "fixed", "date": "2027-02-20"})
        clean, errors, _ = opp.validate(rec)
        entry = {"id": "x", "record": clean, "evaluation": opp.evaluate(clean, p, FIXED_NOW)}
        plan = timeline.plan(entry, p, {}, date(2026, 11, 11))
        keys = {t["key"]: t["due"] for t in plan["tasks"]}
        self.assertEqual(keys["admission"], "2027-01-05")
        self.assertEqual(keys["references"], "2027-01-09")
        self.assertEqual(plan["start_by"], "2027-01-05")
        done = timeline.plan(entry, p, {"tasks_done": ["admission"]}, date(2026, 11, 11))
        self.assertEqual(done["start_by"], "2027-01-09")


class DraftsAndGatesTests(TempHome):
    def make_ready(self) -> tuple[str, dict]:
        docs = self.home / "documents"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "cv.pdf").write_bytes(b"%PDF-1.4\n<</Type /Page>>\n%%EOF")
        (docs / "transcript.pdf").write_bytes(b"%PDF-1.4\n<</Type /Page>>\n%%EOF")
        p = self.base_profile(**{
            "identity.first_name": "Test", "identity.last_name": "Person", "identity.date_of_birth": "2000-01-01",
            "identity.email": "test@example.org", "identity.phone": "+1 250 555 0100",
            "identity.address_line1": "1 Main St", "identity.city": "Example City",
            "identity.postal_code": "A1A 1A1", "identity.address_country": "Canada"})
        prof.list_add(p, "education", {"institution": "U", "degree": "BSc", "status": "completed"})
        prof.list_add(p, "references", {"name": "Dr Ref", "email": "ref@example.org"})
        self.assertTrue(prof.doc_add(p, "cv", str(docs / "cv.pdf"), "CV research")["ok"])
        self.assertTrue(prof.doc_add(p, "transcript", str(docs / "transcript.pdf"))["ok"])
        prof.save(p)
        opp.add([self.record(), self.record(title="Other Grand Award", sponsor="Other Org",
                                            official_url="https://other-org.example/a",
                                            authority_url="https://other-org.example/about")])
        opp_id = next(k for k, v in opp.load_all().items() if v["sponsor"] == "Test Foundation")
        library.add_facts([{"text": "Led a team of four", "source": "cv p1"}])
        brief = drafts.set_brief(opp_id, {"cv_choice": {"path": "documents/cv.pdf", "reason": "fits"}})
        self.assertTrue(brief["ok"], brief)
        return opp_id, p

    def test_draft_checks(self):
        opp_id, _ = self.make_ready()
        long_text = "word " * 60
        put = drafts.put_answer(opp_id, "q1", long_text, ["f1"])
        self.assertTrue(put["checks"]["over_limit"])
        self.assertFalse(drafts.approve(opp_id, "q1")["ok"])
        put = drafts.put_answer(opp_id, "q1", "I loved the Other Grand Award programme. [insert name]", ["f1"])
        self.assertIn("Other Grand Award", put["checks"]["other_scholarship_names"])
        self.assertTrue(put["blocking"])
        self.assertFalse(drafts.put_answer(opp_id, "q1", "text", ["f99"])["ok"])
        ok = drafts.approve(opp_id, "q1", edited_text="I want to study here because I led a team of four.")
        self.assertTrue(ok["ok"], ok)
        self.assertTrue(drafts.status(opp_id)["all_approved"])
        self.assertEqual(len(library.answers()), 1)

    def test_full_gate_sequence(self):
        opp_id, _ = self.make_ready()
        self.assertFalse(applications.start(opp_id)["ok"])  # drafts + doc check missing
        drafts.put_answer(opp_id, "q1", "I led a team of four and want to grow further.", ["f1"])
        self.assertTrue(drafts.approve(opp_id, "q1")["ok"])
        check = doccheck.check(opp_id)
        self.assertTrue(check["ok"], check)
        ready = applications.readiness(opp_id)
        self.assertTrue(ready["ready"], ready["blockers"])
        self.assertTrue(applications.start(opp_id)["ok"])
        self.assertFalse(applications.submitted(opp_id, "X")["ok"])  # not reviewed/approved
        self.assertTrue(applications.needs_you(opp_id, "Please log in")["ok"])
        self.assertTrue(applications.resume(opp_id)["ok"])
        review = self.home / "review.md"
        review.write_text("All sections filled. Answer q1: 10 words.", encoding="utf-8")
        result = applications.review(opp_id, str(review))
        self.assertTrue(result["ok"], result)
        self.assertFalse(applications.approve_submit(opp_id, "wronghash")["ok"])
        self.assertTrue(applications.approve_submit(opp_id, result["review_hash"])["ok"])
        done = applications.submitted(opp_id, "REF-123")
        self.assertTrue(done["ok"], done)
        snap = self.home / "submitted" / opp_id
        self.assertTrue((snap / "summary.json").exists())
        self.assertTrue((snap / "answers.md").exists())
        self.assertEqual(applications.user_action(opp_id, "outcome", {"result": "interview"})["ok"], True)
        self.assertEqual(applications.stats()["by_result"], {"interview": 1})

    def test_changes_after_start_block_submit(self):
        opp_id, _ = self.make_ready()
        drafts.put_answer(opp_id, "q1", "I led a team of four and want to grow further.", ["f1"])
        drafts.approve(opp_id, "q1")
        doccheck.check(opp_id)
        self.assertTrue(applications.start(opp_id)["ok"])
        review = self.home / "review.md"
        review.write_text("summary", encoding="utf-8")
        result = applications.review(opp_id, str(review))
        drafts.approve(opp_id, "q1", edited_text="A different approved answer about leading four people.")
        blocked = applications.approve_submit(opp_id, result["review_hash"])
        self.assertFalse(blocked["ok"])
        self.assertIn("changed", blocked["error"])

    def test_sensitive_log_refused(self):
        opp_id, _ = self.make_ready()
        self.assertFalse(applications.log_event(opp_id, "filled", "SIN 123 456 789")["ok"])

    def test_doccheck_limits(self):
        opp_id, _ = self.make_ready()
        opp.patch(opp_id, {"application": {"upload_rules": [
            {"slot": "CV", "type": "cv", "formats": ["docx"], "max_mb": 1},
            {"slot": "Passport", "type": "passport_scan"}]}})
        result = doccheck.check(opp_id)
        self.assertFalse(result["ok"])
        self.assertTrue(any("format .pdf" in e for e in result["errors"]))
        self.assertEqual(result["items"][1]["status"], "you_upload")

    def test_missing_transcript_blocks_only_calls_that_ask_for_it(self):
        opp_id, _ = self.make_ready()
        p = prof.load()
        p["lists"]["documents"] = [d for d in p["lists"]["documents"] if d["type"] != "transcript"]
        prof.save(p)
        self.assertEqual(prof.status(p)["missing_for_apply"], [])  # a CV is the only document always needed
        result = doccheck.check(opp_id)                             # this call asks for a transcript
        self.assertFalse(result["ok"])
        self.assertTrue(any("'transcript'" in e for e in result["errors"]), result["errors"])
        self.assertIn("document check failed", "; ".join(applications.readiness(opp_id)["blockers"]))


class WatchTests(TempHome):
    def test_change_detection_and_inbox(self):
        pages = {"body": "<html><body><a href='/job/1'>PhD in Machine Learning</a><p>Posted 2 days ago</p></body></html>"}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                data = pages["body"].encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                return

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}/search"
        try:
            rows = [{"id": "w1", "url": url, "label": "test", "kind": "portal_search", "failures": 0}]
            watch._save_pages(rows)  # http is allowed only in tests; add() requires https
            first = watch.run()
            self.assertEqual(first["changed"], 1)  # first run reports existing links
            pages["body"] = pages["body"].replace("2 days ago", "3 days ago")
            self.assertEqual(watch.run()["changed"], 0)  # volatile line ignored
            pages["body"] += "<a href='/job/2'>PhD in Robotics</a>"
            third = watch.run()
            self.assertEqual(third["changed"], 1)
            latest = watch.changes()[-1]
            self.assertTrue(any("Robotics" in line for line in latest["added_lines"]))
            watch.mark_processed(["all"])
            self.assertEqual(watch.changes(), [])
        finally:
            server.shutdown()
            server.server_close()
        self.assertFalse(watch.add("http://insecure.example", "x", "funding_page")["ok"])
        self.assertFalse(watch.inbox_add("not a link")["ok"])
        self.assertTrue(watch.inbox_add("https://example.org/call")["ok"])
        self.assertEqual(len(watch.inbox()), 1)


class QueriesTests(TempHome):
    def test_no_private_values_and_consent(self):
        p = self.base_profile(**{"identity.first_name": "Zainab"})
        prof.list_add(p, "tests", {"exam": "IELTS", "score": "7.5"})
        prof.list_add(p, "education", {"institution": "U", "degree": "BSc", "gpa": "3.91", "gpa_scale": "4"})
        prof.save(p)
        self.assertTrue(queries.generate(p)["ok"])
        texts = " ".join(q["text"] for q in queries.load()["queries"])
        for secret in ("Zainab", "3.91", "7.5", "Pakistan"):
            self.assertNotIn(secret, texts)
        prof.set_value(p, "consent.identity_search", "yes")
        queries.generate(p, max_queries=200)
        texts = " ".join(q["text"] for q in queries.load()["queries"])
        self.assertIn("Pakistan", texts)
        self.assertTrue(any(q["kind"] == "phd_jobs" for q in queries.load()["queries"]))


class RegistryTests(unittest.TestCase):
    def test_registry_helpers(self):
        self.assertTrue(registry.is_discovery("www.scholars4dev.com".removeprefix("www.")))
        self.assertTrue(registry.find_source("kth.se"))
        self.assertTrue(registry.find_job_portal("lu.varbi.com"))
        self.assertEqual(registry.base_domain("www.grad.ubc.ca"), "ubc.ca")
        self.assertEqual(registry.base_domain("scholarships.unimelb.edu.au"), "unimelb.edu.au")
        self.assertTrue(registry.same_site("www.ox.ac.uk", "rhodeshouse.ox.ac.uk"))
        names, unknown = countries.expand(["@nordic", "Holland"])
        self.assertIn("netherlands", names)
        self.assertIn("iceland", names)
        self.assertEqual(unknown, [])


class ServerTests(TempHome):
    def setUp(self) -> None:
        super().setUp()
        from scholar import server
        self.httpd = server.make_server(0)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"127.0.0.1:{self.port}"}
        h.update(headers or {})
        conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, data

    def test_drafts_endpoint_refuses_paths(self):
        for bad in ("..%2F..%2Fprofile", "..%5C..%5Cprofile", "Bad-ID", "a%2Fb"):
            status, _ = self.request("GET", f"/api/drafts/{bad}")
            self.assertEqual(status, 400, bad)
        self.assertFalse((self.home / "profile").exists())
        self.assertFalse((self.home / "data" / "drafts").exists())
        with self.assertRaises(ValueError):
            drafts.full("../outside")
        status, _ = self.request("GET", "/api/drafts/some-opportunity-1a2b3c")
        self.assertEqual(status, 200)

    def test_state_and_guards(self):
        status, data = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertIn("rows", json.loads(data))
        status, _ = self.request("GET", "/api/state", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/inbox", {"op": "add", "url": "https://example.org/x"},
                                 {"Content-Type": "application/json"})
        self.assertEqual(status, 403)  # missing X-Scholar header
        status, _ = self.request("POST", "/api/inbox", {"op": "add", "url": "https://example.org/x"},
                                 {"Content-Type": "application/json", "X-Scholar": "1",
                                  "Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        status, data = self.request("POST", "/api/inbox", {"op": "add", "url": "https://example.org/x"},
                                    {"Content-Type": "application/json", "X-Scholar": "1",
                                     "Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200, data)
        status, _ = self.request("GET", "/submitted/../data/profile.json")
        self.assertEqual(status, 404)
        status, data = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Scholarship Desk", data)

    def test_profile_editing_from_dashboard(self):
        hdrs = {"Content-Type": "application/json", "X-Scholar": "1"}
        status, data = self.request("GET", "/api/profile")
        self.assertEqual(status, 200)
        view = json.loads(data)
        self.assertIn("publications", view["schema"]["lists"])
        self.assertNotIn("documents", view["lists"])
        ok = lambda body: self.request("POST", "/api/profile", body, hdrs)
        status, data = ok({"op": "set", "key": "target.research_interests", "value": "AI for inclusive education"})
        self.assertEqual(status, 200, data)
        status, data = ok({"op": "set", "key": "target.levels", "value": ["masters", "phd"]})
        self.assertEqual(status, 200, data)
        status, data = ok({"op": "add", "list": "publications", "fields": {"title": "A paper", "year": "2026"}})
        self.assertEqual(status, 200, data)
        row_id = json.loads(data)["row"]["id"]
        status, data = ok({"op": "update", "list": "publications", "id": row_id,
                           "fields": {"authors": "A. One, B. Two", "year": ""}})
        self.assertEqual(status, 200, data)
        row = prof.load()["lists"]["publications"][0]
        self.assertEqual((row["authors"], row.get("year")), ("A. One, B. Two", None))  # cleared field removed
        # Same refusal rules as the chat: no ID numbers, no unknown keys.
        status, data = ok({"op": "set", "key": "narrative.other", "value": "My SIN is 046 454 286"})
        self.assertEqual(status, 400)
        self.assertIn("NOT SAVED", json.loads(data)["error"])
        status, _ = ok({"op": "set", "key": "identity.password", "value": "x"})
        self.assertEqual(status, 400)
        status, data = ok({"op": "remove", "list": "publications", "id": row_id})
        self.assertEqual(status, 200, data)
        self.assertEqual(prof.load()["lists"]["publications"], [])
        status, _ = ok({"op": "set", "key": "target.research_interests", "value": ""})  # clearing works
        self.assertEqual(status, 200)
        self.assertNotIn("target.research_interests", prof.load()["values"])

    def test_upload_saves_and_registers_document(self):
        import base64
        hdrs = {"Content-Type": "application/json", "X-Scholar": "1"}
        pdf = base64.b64encode(b"%PDF-1.4\n<</Type /Page>>\n%%EOF").decode()
        body = {"name": "..\\..\\My Transcript.PDF", "type": "transcript", "label": "Bachelor's transcript", "data": pdf}
        status, data = self.request("POST", "/api/upload", body, hdrs)
        self.assertEqual(status, 200, data)
        saved = json.loads(data)["document"]
        self.assertEqual(saved["path"], "documents/My Transcript.pdf")  # folders stripped, extension normalised
        self.assertTrue((self.home / "documents" / "My Transcript.pdf").exists())
        state = json.loads(self.request("GET", "/api/state")[1])
        self.assertEqual([(d["type"], d["status"]) for d in state["documents"]], [("transcript", "new")])
        # Same name again: asks before replacing, then replaces.
        status, data = self.request("POST", "/api/upload", body, hdrs)
        self.assertEqual(status, 400)
        self.assertTrue(json.loads(data)["exists"])
        status, data = self.request("POST", "/api/upload", {**body, "replace": True}, hdrs)
        self.assertEqual(status, 200, data)
        self.assertTrue(json.loads(data)["replaced"])
        self.assertEqual(len(prof.load()["lists"]["documents"]), 1)
        # A file whose content doesn't match its extension, or an unsupported type, is refused.
        fake = base64.b64encode(b"MZ\x90\x00 not a pdf").decode()
        status, _ = self.request("POST", "/api/upload", {**body, "name": "cv.pdf", "data": fake}, hdrs)
        self.assertEqual(status, 400)
        status, _ = self.request("POST", "/api/upload", {**body, "name": "setup.exe", "data": fake}, hdrs)
        self.assertEqual(status, 400)
        status, _ = self.request("POST", "/api/upload", {**body, "name": "x.pdf", "type": "banana"}, hdrs)
        self.assertEqual(status, 400)
        self.assertFalse((self.home / "documents" / "setup.exe").exists())


if __name__ == "__main__":
    unittest.main()
