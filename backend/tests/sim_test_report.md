# Simulator test report (Phase 2 gate)

Date: 2026-10-24. Environment: Python 3.11 venv (`~/.venvs/provafair`), qiskit 2.6.1, qiskit-aer, qiskit-ibm-runtime 0.51.0. No IBM job was submitted; `scripts/submit.py --backend open` was only exercised with a missing account to prove it fails before submitting.

Run: `cd backend && python -m pytest tests/test_core.py tests/test_services.py tests/test_pipeline.py tests/test_api.py tests/test_ui.py -v`

**Result: 88 passed, 0 failed** (78 at the original gate, plus 10 added for auth, idempotency, rate limit and the rewired `/draw/*` endpoints). The pre-existing `tests/stress_test.py` (4 phases: rate limit, idempotency, webhooks/batching, Merkle) also still passes (run against a temporary database).

| File | Area | Tests | Result |
|---|---|---|---|
| test_core.py | core: stream, HKDF, CHSH (Aer, control, LHV, noisy fake backend) | 15 | all pass |
| test_services.py | services: IPO, Web3, Lottery, Keys algorithms and validation | 23 | all pass |
| test_pipeline.py | pipeline: modes, replay, verify + tamper, submit/collect scripts | 24 | all pass |
| test_api.py | HTTP API (/v3) and existing /v2 routes | 8 | all pass |
| test_ui.py | console: every service page, verify page, backend-down, navigation | 8 | all pass |

## What each area proved

- **Stream**: `randbelow` passes chi-square for n = 6, 7, 10, 100 (fixed seeds, p=0.001 thresholds); deterministic per seed+label; labels and seeds diverge; shuffle is a permutation and first-position uniform; HKDF matches the RFC 5869 test vector.
- **CHSH**: Aer entangled runs certify (S about 2.7-2.9); no-entanglement control is blocked (S <= 2); 20 classical LHV runs all blocked; noisy `FakeKingston` model gives S between 2 and 2.83 (about 2.65-2.70, so the honest, lower number); boundary S=2.0 is not certified.
- **IPO**: undersubscribed allots everyone; oversubscribed gives exactly `floor(retail/lot)` winners, no duplicates, waiting list completes the permutation; allotment fair over 2000 seeds (chi-square).
- **Web3**: no repeated validators; stake-weighted frequencies match stake shares (700/200/100 and 10 uneven validators, chi-square); epoch and label change the beacon; beacon is 32 bytes.
- **Lottery**: 6/49 sorted unique in range; bonus distinct; uniform over 3000 draws; 10,000-ticket prize draw has no duplicates.
- **Keys**: keys differ per index/purpose; same seed twice gives different keys (local entropy) but identical quantum-component fingerprints; no key material in any run file or the ledger; demo label present.
- **Verify**: all 5 checks tick for every service. Tampering with params -> check 1; one flipped bitstring -> checks 2 and 3; edited result -> 4 and 5; edited ledger entry -> 3 and 5; edited/deleted COMMIT entry -> 1 (and 5); swapping a blocked run's bits for quantum bits -> 2; injected output on a blocked run -> 4.
- **Fail-closed**: control and classical modes are BLOCKED for all four services, with no seed and no output, and still verify cleanly.
- **Replay**: uses the recorded bits and job ID, badge reads `SIMULATOR (replayed)` (never live), different scenario labels give different seeds, replay-of-replay points at the original run, replay with nothing recorded is a clean 404 and leaves no run folder.
- **Scripts**: `submit.py` on a fake provider writes `job_meta.json` immediately and the ledger COMMIT before results exist; `collect.py` then produces a run folder that passes all 5 checks; `--control` run is blocked.
- **API/UI**: every route returns the right codes (200/404/422); `backend` param can never reach real IBM through the API; each console page renders the mode badge before running, runs in sim, shows the verified badge and result, and its Verify button shows 5 ticks; classical/control pages show BLOCKED with no numbers; backend-down shows a clear error.

## Findings and limits (not test failures)

1. RESOLVED: `/draw/quantum` and `/draw/rigged` now run the real pipeline (Aer CHSH, certification, service) instead of returning hard-coded values. The old fake `ibm-q-job-*` id is gone; the response carries the real job id (`SIM-...`). `tests/stress_test.py` was updated to match.
2. RESOLVED: `/v3` now requires `X-API-Key` (from `API_KEY` in `.env`), has its own rate limit (120/min, `V3_RATE_LIMIT`) and honours `Idempotency-Key`. Demo keys are never cached. `/v2` remains unauthenticated.
3. The repo's committed `env/` has a broken scipy binary on this macOS, so `qiskit_ibm_runtime` cannot import there. Tests ran in a separate venv outside the repo. Phase 3 needs a working environment.
4. `qiskit_ibm_runtime.SamplerV2` (used in morework.md and `core/hardware.py`) is deprecated as of 0.50; it still works. Check IBM's current docs before Phase 3.
5. Fake-backend noise is a model, not hardware. Real S can differ.
6. UI tests check content and behavior via Streamlit AppTest, not visual layout/CSS. A human look at the console is still needed.

## Full test list

**test_core.py**

- StreamTests / test_deterministic_same_seed_and_label
- StreamTests / test_hkdf_rfc5869_vector
- StreamTests / test_labels_and_seeds_diverge
- StreamTests / test_randbelow_edges
- StreamTests / test_randbelow_uniform_chi_square
- StreamTests / test_sample_distinct_and_in_range
- StreamTests / test_shuffle_is_permutation_and_deterministic
- StreamTests / test_shuffle_position_uniform
- ChshTests / test_aer_entangled_certified
- ChshTests / test_bitstrings_are_per_shot_and_ordered
- ChshTests / test_classical_lhv_blocked_many_times
- ChshTests / test_control_no_entanglement_blocked
- ChshTests / test_missing_setting_rejected
- ChshTests / test_noisy_fake_backend_lower_but_honest
- ChshTests / test_pass_rule_boundary

**test_services.py**

- IpoTests / test_allotment_is_fair_over_many_seeds
- IpoTests / test_deterministic
- IpoTests / test_explicit_applicants_and_validation
- IpoTests / test_heavy_oversubscription_and_floor
- IpoTests / test_oversubscribed_exact_winners_no_duplicates_full_permutation
- IpoTests / test_undersubscribed_everyone_allotted
- Web3Tests / test_all_seats_selects_everyone
- Web3Tests / test_epoch_changes_beacon_label_changes_committee
- Web3Tests / test_no_repeats_right_size_and_beacon
- Web3Tests / test_stake_weighted_frequency
- Web3Tests / test_uneven_default_stakes_chi_square
- Web3Tests / test_validation
- LotteryTests / test_6_of_49
- LotteryTests / test_bonus_distinct_from_main
- LotteryTests / test_number_frequency_uniform
- LotteryTests / test_ticket_draw_10000_no_duplicates
- LotteryTests / test_validation
- KeysTests / test_formats_and_lengths
- KeysTests / test_keys_differ_by_index_and_purpose
- KeysTests / test_result_has_no_key_material_and_demo_label
- KeysTests / test_same_seed_twice_differs_because_of_local_entropy
- KeysTests / test_validation
- KeysPipelineTests / test_no_key_material_persisted_anywhere

**test_pipeline.py**

- PipelineTests / test_cannot_replay_a_blocked_run
- PipelineTests / test_commit_entry_precedes_result_in_ledger
- PipelineTests / test_control_and_classical_blocked_fail_closed
- PipelineTests / test_every_service_certifies_and_all_five_checks_tick
- PipelineTests / test_invalid_inputs
- PipelineTests / test_noisy_fake_backend_run_certifies_with_lower_S
- PipelineTests / test_replay_changed_params_reruns_algorithm_only
- PipelineTests / test_replay_uses_recorded_bits_and_is_never_live
- PipelineTests / test_replay_without_recording_is_a_clear_404_and_leaves_no_run
- PipelineTests / test_run_folder_contents
- TamperTests / test_blocked_run_with_injected_output_fails
- TamperTests / test_delete_commit_entry
- TamperTests / test_forged_certificate_on_blocked_run
- TamperTests / test_keys_receipt_tamper_detected
- TamperTests / test_missing_files_do_not_crash
- TamperTests / test_tamper_commit_entry
- TamperTests / test_tamper_ledger_entry
- TamperTests / test_tamper_one_bitstring
- TamperTests / test_tamper_params
- TamperTests / test_tamper_result
- TamperTests / test_untampered_after_other_activity_stays_valid
- ScriptTests / test_open_backend_without_credentials_fails_cleanly_before_any_job
- ScriptTests / test_submit_collect_on_fake_provider_produces_verifiable_run
- ScriptTests / test_submit_control_circuit_is_blocked_on_fake_provider

**test_api.py**

- ApiTests / test_backend_param_cannot_reach_ibm
- ApiTests / test_blocked_modes_over_http
- ApiTests / test_each_service_draw_runs_and_verifies_over_http
- ApiTests / test_error_codes
- ApiTests / test_existing_routes_still_work
- ApiTests / test_keys_returned_once_not_by_get
- ApiTests / test_mode_and_services_endpoints
- ApiTests / test_replay_over_http

**test_ui.py**

- UiTests / test_app_navigation_script_loads
- UiTests / test_classical_and_control_show_blocked_and_no_output
- UiTests / test_each_service_page_runs_in_sim_with_badge_and_verifies
- UiTests / test_replay_modes_in_ui
- UiTests / test_service_pages_render_with_mode_badge_before_running
- UiTests / test_ui_hides_nothing_when_backend_down
- UiTests / test_verify_page_lists_runs_and_verifies
- UiTests / test_verify_page_unknown_run_shows_error


## Addendum: live mode with replay fallback (tests: 22 in test_live.py, 1 in test_ui.py)
All with fakes, no IBM call. Covered: live runs when the queue is empty; queue over the limit -> saved hardware run, nothing submitted, reason shown; IBM unreachable or slow -> fallback, probe never raises or hangs, token never appears in an error; queued job cancelled after the timeout; failed/erroring hardware job -> fallback; submit exception -> fallback; no saved hardware run -> clear 503 and no stray run (a simulator recording is not an acceptable fallback); job cap; one live run at a time; a live result that fails the Bell test stays BLOCKED; parameters committed to the ledger before any live attempt; fallbacks are never labelled live; `/v3/live/status`; live as default mode; live page in the console.
Total after the addendum: 113 tests passing.
