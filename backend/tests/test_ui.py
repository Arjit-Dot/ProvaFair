"""Console walkthrough: every service page and the verify page, against a live backend in sim mode."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import requests

import helpers

FRONTEND = helpers.BACKEND.parent / "frontend"
sys.path.insert(0, str(FRONTEND))
from streamlit.testing.v1 import AppTest  # noqa: E402


def md(at):
    return "\n".join(m.value for m in at.markdown)


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pf-ui-")
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        env = {**os.environ, "PROVAFAIR_DATA": f"{cls.tmp}/runs", "PROVAFAIR_LEDGER_DB": f"{cls.tmp}/chain.db",
               "DATABASE_URL": f"sqlite:///{cls.tmp}/audit.db",
               "PROVAFAIR_LIVE_BACKEND": "fake:FakeKingston"}   # live mode runs on a local noisy fake, no IBM call
        cls.proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(port)],
                                    cwd=helpers.BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.url = f"http://127.0.0.1:{port}"
        for _ in range(60):
            try:
                if requests.get(cls.url + "/v2/usecases", timeout=1).status_code == 200:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("backend did not start")
        from ui import api
        api.API_URL = cls.url

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, name):
        at = AppTest.from_file(str(FRONTEND / "views" / name), default_timeout=120)
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def run_draw(self, name, key, mode):
        at = self.page(name)
        at.radio(key=f"{key}_mode").set_value(mode)
        at.button(key=f"{key}_run").click()
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def test_service_pages_render_with_mode_badge_before_running(self):
        for name in ("ipo.py", "web3.py", "lottery.py", "keys.py"):
            at = self.page(name)
            self.assertIn("SIMULATOR", md(at), name)
            self.assertIn("Set parameters", md(at), name)

    def test_each_service_page_runs_in_sim_with_badge_and_verifies(self):
        expect = {"ipo": ("ipo.py", "Allottees"), "web3": ("web3.py", "Committee for epoch"),
                  "lottery": ("lottery.py", "Winning numbers"), "keys": ("keys.py", "DEMO KEYS, NOT FOR REAL USE")}
        for key, (name, marker) in expect.items():
            at = self.run_draw(name, key, "sim")
            text = md(at)
            self.assertIn("DRAW CERTIFIED", text, key)
            self.assertIn("SIMULATOR", text, key)
            self.assertIn(marker, text, key)
            at.button(key=f"{key}_verify").click()
            at.run()
            self.assertFalse(at.exception)
            text = md(at)
            self.assertIn("All 5 checks passed", text, key)
            self.assertEqual(text.count("pf-check ok"), 5, key)

    def test_live_mode_in_ui_shows_status_and_live_badge(self):
        at = self.page("lottery.py")
        at.radio(key="lottery_mode").set_value("live")
        at.run()
        self.assertIn("Live is available now", md(at))
        at.button(key="lottery_run").click()
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        text = md(at)
        self.assertIn("SIMULATOR (live, fake backend)", text)
        self.assertIn("DRAW CERTIFIED", text)

    def test_classical_and_control_show_blocked_and_no_output(self):
        for mode, badge in (("classical", "CLASSICAL"), ("control", "control, no entanglement")):
            at = self.run_draw("lottery.py", "lottery", mode)
            text = md(at)
            self.assertIn("DRAW BLOCKED", text, mode)
            self.assertIn("No output released", text, mode)
            self.assertNotIn("Winning numbers", text, mode)
            self.assertIn(badge, text, mode)

    def test_replay_modes_in_ui(self):
        at = self.run_draw("ipo.py", "ipo", "replay")      # nothing recorded yet for ipo in this fresh state? may exist
        text = md(at)
        if "No recorded" in text or "no recorded" in text:
            self.assertIn("Run in sim mode", text)
        self.run_draw("ipo.py", "ipo", "sim")
        at = self.run_draw("ipo.py", "ipo", "replay")
        text = md(at)
        self.assertIn("SIMULATOR (replayed)", text)
        self.assertNotIn("HARDWARE", text)

    def test_verify_page_lists_runs_and_verifies(self):
        self.run_draw("web3.py", "web3", "sim")
        at = self.page("verify_run.py")
        at.selectbox(key="vr_service").set_value("web3")
        at.run()
        runs = at.selectbox(key="vr_pick").options
        self.assertGreater(len(runs), 1)
        at.selectbox(key="vr_pick").set_value(runs[1])
        at.button[0].click()
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(md(at).count("pf-check ok"), 5)

    def test_verify_page_unknown_run_shows_error(self):
        at = self.page("verify_run.py")
        at.text_input(key="vr_typed").set_value("IPO-does-not-exist")
        at.button[0].click()
        at.run()
        self.assertIn("run not found", md(at))

    def test_ui_hides_nothing_when_backend_down(self):
        from ui import api
        old, api.API_URL = api.API_URL, "http://127.0.0.1:1"
        try:
            at = self.run_draw("ipo.py", "ipo", "sim")
            self.assertIn("Cannot reach the backend", md(at))
        finally:
            api.API_URL = old

    def test_app_navigation_script_loads(self):
        at = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=120)
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])


if __name__ == "__main__":
    unittest.main()
